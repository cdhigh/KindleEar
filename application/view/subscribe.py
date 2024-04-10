#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#管理订阅页面

import datetime, json, io, re, zipfile
from operator import attrgetter
from urllib.parse import urljoin
from flask import Blueprint, render_template, request, redirect, url_for, send_file, current_app as app
from flask_babel import gettext as _
from ..base_handler import *
from ..back_end.db_models import *
from ..utils import str_to_bool, xml_escape
from ..lib.urlopener import UrlOpener
from ..lib.recipe_helper import GetBuiltinRecipeInfo, GetBuiltinRecipeSource
from .library import LIBRARY_MGR, SUBSCRIBED_FROM_LIBRARY, LIBRARY_GETSRC, buildKeUrl
from ebook_translator import get_trans_engines, HtmlTranslator

bpSubscribe = Blueprint('bpSubscribe', __name__)

#管理我的订阅和杂志列表
@bpSubscribe.route("/my", endpoint='MySubscription')
@login_required()
def MySubscription(tips=None):
    user = get_login_user()
    share_key = user.share_links.get('key', '')
    title_to_add = request.args.get('title_to_add') #from Bookmarklet
    url_to_add = request.args.get('url_to_add')
    my_custom_rss = [item.to_dict(only=[Recipe.id, Recipe.title, Recipe.url, Recipe.isfulltext]) 
        for item in user.all_custom_rss()]
    my_uploaded_recipes = [item.to_dict(only=[Recipe.id, Recipe.title, Recipe.description, Recipe.needs_subscription, Recipe.language]) 
        for item in user.all_uploaded_recipe()]
    #使用不同的id前缀区分不同的rss类型
    for item in my_custom_rss:
        item['id'] = 'custom:{}'.format(item['id'])
    for item in my_uploaded_recipes:
        item['id'] = 'upload:{}'.format(item['id'])
        item['language'] = item['language'].lower().replace('-', '_').split('_')[0]

    my_booked_recipes = json.dumps([item.to_dict(exclude=[BookedRecipe.encrypted_pwd])
        for item in user.get_booked_recipe() if not item.recipe_id.startswith('custom:')], 
        separators=(',', ':'))

    my_custom_rss = json.dumps(my_custom_rss)
    my_uploaded_recipes=json.dumps(my_uploaded_recipes)
    subscribe_url = urljoin(app.config['APP_DOMAIN'], url_for("bpSubscribe.MySubscription"))
    url2book_url = urljoin(app.config['APP_DOMAIN'], url_for("bpUrl2Book.Url2BookRoute"))
    return render_template("my.html", tab="my", **locals())

#添加自定义RSS
@bpSubscribe.post("/my", endpoint='MySubscriptionPost')
@login_required()
def MySubscriptionPost():
    user = get_login_user()
    form = request.form
    title = form.get('rss_title')
    url = form.get('url')
    isfulltext = bool(form.get('fulltext'))
    if not title or not url:
        return redirect(url_for("bpSubscribe.MySubscription", tips=(_("Title or url is empty!"))))

    if not url.lower().startswith('http'): #http and https
        url = ('https:/' if url.startswith('/') else 'https://') + url

    #判断是否重复
    if Recipe.get_or_none((Recipe.user == user.name) & (Recipe.title == title)):
        return redirect(url_for("bpSubscribe.MySubscription", tips=(_("Duplicated subscription!"))))
    else:
        Recipe.create(title=title, url=url, isfulltext=isfulltext, type_='custom', user=user.name,
            time=datetime.datetime.utcnow())
        return redirect(url_for("bpSubscribe.MySubscription"))

#添加/删除自定义RSS订阅的AJAX处理函数
@bpSubscribe.post("/customrss/<actType>", endpoint='FeedsAjaxPost')
@login_required(forAjax=True)
def FeedsAjaxPost(actType):
    user = get_login_user()
    form = request.form
    actType = actType.lower()

    if actType == 'delete':
        return DeleteCustomRss(user, form.get('id', ''))
    elif actType == 'add':
        return AddCustomRss(user, form)
    else:
        return {'status': 'Unknown command: {}'.format(actType)}

#添加自定义RSS
def AddCustomRss(user, form):
    title = form.get('title', '')
    url = form.get('url', '')
    isfulltext = str_to_bool(form.get('fulltext', ''))
    fromSharedLibrary = str_to_bool(form.get('fromsharedlibrary', ''))
    recipeId = form.get('recipeId', '')

    ret = {'status':'ok', 'title':title, 'url':url, 'isfulltext':isfulltext, 'recipeId': recipeId}

    if not title or not (url or recipeId):
        ret['status'] = _("The Title or Url is empty.")
        return ret

    #如果url不存在，则可能是分享的recipe，需要连接服务器获取recipe代码
    if not url:
        opener = UrlOpener()
        if recipeId.startswith('http'):
            resp = opener.open(recipeId)
        else:
            path = LIBRARY_MGR + LIBRARY_GETSRC
            resp = opener.open(buildKeUrl(path), {'recipeId': recipeId})

        if resp.status_code != 200:
            ret['status'] = _("Failed to fetch the recipe.")
            return ret

        if recipeId.startswith('http'):
            src = resp.text
        else:
            data = resp.json()
            if data.get('status') != 'ok':
                ret['status'] = data.get('status', '')
                return ret
            src = data.get('src', '')
            try:
                params = SaveRecipeIfCorrect(user, src)
            except Exception as e:
                return {'status': _("Failed to save the recipe. Error:") + str(e)}
            ret.update(params)
    else: #自定义RSS
        if not url.lower().startswith('http'):
            url = ('https:/' if url.startswith('/') else 'https://') + url
            ret['url'] = url

        #判断是否重复
        if Recipe.get_or_none((Recipe.user == user.name) & (Recipe.title == title)):
            ret['status'] = _("Duplicated subscription!")
            return ret
        else:
            rss = Recipe.create(title=title, url=url, isfulltext=isfulltext, type_='custom', user=user.name,
                time=datetime.datetime.utcnow())
            ret['id'] = rss.recipe_id
            UpdateBookedCustomRss(user)
    
    #如果是从共享库中订阅的，则通知共享服务器，提供订阅数量信息，以便排序
    if fromSharedLibrary:
        SendNewSubscription(title, url, recipeId)

    return ret

#删除自定义RSS
def DeleteCustomRss(user, rssId):
    tips = {'status': 'ok'}
    if rssId == '#all_custom_rss#': #删除所有当前的自定义RSS
        Recipe.delete().where((Recipe.user == user.name) & (Recipe.type_ == 'custom')).execute()
        UpdateBookedCustomRss(user)
    else:
        recipeType, rssId = Recipe.type_and_id(rssId)
        rss = Recipe.get_by_id_or_none(rssId)
        if (recipeType == 'custom') and rss:
            rss.delete_instance()
            UpdateBookedCustomRss(user)
        else:
            tips = {'status': _('The Rss does not exist.')}
    return tips

#根据特定用户的自定义RSS推送使能设置，更新已订阅列表
def UpdateBookedCustomRss(user: KeUser):
    userName = user.name
    #删除孤立的BookedRecipe
    for dbInst in list(BookedRecipe.get_all()):
        recipeType, recipeId = Recipe.type_and_id(dbInst.recipe_id)
        if recipeType != 'builtin' and not Recipe.get_by_id_or_none(recipeId):
            dbInst.delete_instance()
            
    if user.enable_custom_rss: #添加订阅
        for rss in user.all_custom_rss()[::-1]:
            BookedRecipe.get_or_create(recipe_id=rss.recipe_id, defaults={'separated': False, 'user': userName, 
                'title': rss.title, 'description': rss.description, 'time': datetime.datetime.utcnow(),
                'translator': rss.translator})
    else: #删除订阅
        ids = [rss.recipe_id for rss in user.all_custom_rss()]
        if ids:
            BookedRecipe.delete().where(BookedRecipe.recipe_id.in_(ids)).execute()

#通知共享服务器，有一个新的订阅
def SendNewSubscription(title, url, recipeId):
    opener = UrlOpener()
    path = LIBRARY_MGR + SUBSCRIBED_FROM_LIBRARY
    #只管杀不管埋，不用管能否成功了
    opener.open(buildKeUrl(path), {'title': title, 'url': url, 'recipeId': recipeId})

#书籍翻译器
@bpSubscribe.route("/translator/<recipeId>", endpoint='BookTranslatorRoute')
@login_required()
def BookTranslatorRoute(recipeId):
    user = get_login_user()
    tips = ''
    recipeId = recipeId.replace('__', ':')
    recipeType, dbId = Recipe.type_and_id(recipeId)
    recipe = GetBuiltinRecipeInfo(recipeId) if recipeType == 'builtin' else Recipe.get_by_id_or_none(dbId)
    if not recipe:
        tips = _('The recipe does not exist.')
        return render_template('tipsback.html', tips=tips, urltoback=url_for('bpSubscribe.MySubscription'))
        
    bkRecipe = user.get_booked_recipe(recipeId)
    if recipeType == 'custom':
        params = recipe.translator #自定义RSS的Recipe和BookedRecipe的translator属性一致
    elif bkRecipe:
        params = bkRecipe.translator
    else:
        tips = _('This recipe has not been subscribed to yet.')
        params = {}

    engines = json.dumps(get_trans_engines(), separators=(',', ':'))
    return render_template('book_translator.html', tab="my", tips=tips, params=params, title=recipe.title,
        recipeId=recipeId, engines=engines)

#修改书籍翻译器的设置
@bpSubscribe.post("/translator/<recipeId>", endpoint='BookTranslatorPost')
@login_required()
def BookTranslatorPost(recipeId):
    user = get_login_user()
    tips = ''
    recipeId = recipeId.replace('__', ':')
    recipeType, dbId = Recipe.type_and_id(recipeId)
    recipe = GetBuiltinRecipeInfo(recipeId) if recipeType == 'builtin' else Recipe.get_by_id_or_none(dbId)
    if not recipe:
        tips = _('The recipe does not exist.')
        return render_template('tipsback.html', tips=tips, urltoback=url_for('bpSubscribe.MySubscription'))
    
    #构建配置参数
    form = request.form
    engineName = form.get('engine', '')
    apiHost = form.get('api_host', '')
    apiKeys = form.get('api_keys', '')
    apiKeys = apiKeys.split('\n') if apiKeys else []
    params = {'enable': str_to_bool(form.get('enable', '')), 'engine': engineName,
        'api_host': apiHost, 'api_keys': apiKeys, 'src_lang': form.get('src_lang', ''), 
        'dst_lang': form.get('dst_lang', 'en'), 'position': form.get('position', 'below'),
        'orig_style': form.get('orig_style', ''), 'trans_style': form.get('trans_style', '')}

    engines = get_trans_engines()
    engine = engines.get(engineName, None)
    if engine and engine.get('need_api_key'):
        if not apiKeys:
            tips = _('The api key is required.')
            return render_template('book_translator.html', tab="my", tips=tips, params=params, title=recipe.title,
                recipeId=recipeId, engines=json.dumps(engines, separators=(',', ':')))
    else:
        params['api_host'] = ''

    tips = _("Settings Saved!")
    apply_all = str_to_bool(form.get('apply_all', ''))
    if apply_all: #所有的Recipe使用同样的配置
        for item in [*user.all_custom_rss(), *user.get_booked_recipe()]:
            item.translator = params
            item.save()
    else:
        bkRecipe = user.get_booked_recipe(recipeId)
        if recipeType == 'custom': #自定义RSS先保存到Recipe，需要的时候再同步到BookedRecipe
            recipe.translator = params
            recipe.save()

        if bkRecipe:
            bkRecipe.translator = params
            bkRecipe.save()
        elif recipeType != 'custom':
            tips = _('This recipe has not been subscribed to yet.')
        
    return render_template('book_translator.html', tab="my", tips=tips, params=params, title=recipe.title,
        recipeId=recipeId, engines=json.dumps(engines, separators=(',', ':')))

#测试Recipe的翻译器设置是否正确
@bpSubscribe.post("/translator/test", endpoint='BookTranslatorTestPost')
@login_required(forAjax=True)
def BookTranslatorTestPost():
    user = get_login_user()
    tips = ''
    recipeId = request.form.get('recipeId', '')
    recipeType, dbId = Recipe.type_and_id(recipeId)
    recipe = GetBuiltinRecipeInfo(recipeId) if recipeType == 'builtin' else Recipe.get_by_id_or_none(dbId)
    if not recipe:
        return {'status': _('The recipe does not exist.')}

    bkRecipe = recipe if recipeType == 'custom' else user.get_booked_recipe(recipeId)
    if not bkRecipe:
        return {'status': _('This recipe has not been subscribed to yet.')}

    text = request.form.get('text')
    if not text:
        return {'status': _('The text is empty.')}

    translator = HtmlTranslator(bkRecipe.translator)
    data = translator.translate_text(text)
    status = data['error'] if data['error'] else 'ok'
    return {'status': status, 'text': data['translated']}

#订阅/退订内置或上传Recipe的AJAX处理函数
@bpSubscribe.post("/recipe/<actType>", endpoint='RecipeAjaxPost')
@login_required(forAjax=True)
def RecipeAjaxPost(actType):
    user = get_login_user()
    form = request.form

    if actType == 'upload': #上传Recipe
        return SaveUploadedRecipe(user)
    
    recipeId = form.get('id', '')
    recipeType, dbId = Recipe.type_and_id(recipeId)
    recipe = GetBuiltinRecipeInfo(recipeId) if recipeType == 'builtin' else Recipe.get_by_id_or_none(dbId)
    if not recipe:
        return {'status': _('The recipe does not exist.')}

    if actType == 'unsubscribe': #退订
        return UnsubscribeRecipe(user, recipeId, recipe)
    elif actType == 'subscribe': #订阅
        separated = str_to_bool(form.get('separated', ''))
        return SubscribeRecipe(user, recipeId, recipe, separated)
    elif actType == 'delete': #删除已经上传的recipe
        return DeleteRecipe(user, recipeId, recipeType, recipe)
    elif actType == 'schedule': #设置某个recipe的自定义推送时间
        return ScheduleRecipe(recipeId, form)
    else:
        return {'status': _('Unknown command: {}').format(actType)}


#订阅某个Recipe
def SubscribeRecipe(user, recipeId, recipe, separated):
    ret = {'recipe_id': recipeId, 'title': recipe.title, 'description': recipe.description,
        'needs_subscription': recipe.needs_subscription, 'separated': separated}
    
    dbInst = user.get_booked_recipe(recipeId)
    if dbInst: #不报错，更新separated属性
        dbInst.separated = separated
        dbInst.save()
    else:
        BookedRecipe.create(user=user.name, **ret)

    ret['status'] = 'ok'
    return ret

#退订某个Recipe
def UnsubscribeRecipe(user, recipeId, recipe):
    BookedRecipe.delete().where((BookedRecipe.user == user.name) & (BookedRecipe.recipe_id == recipeId)).execute()
    return {'status':'ok', 'id': recipeId, 'title': recipe.title, 'desc': recipe.description}

#删除某个Recipe
def DeleteRecipe(user, recipeId, recipeType, recipe):
    if recipeType == 'builtin':
        return {'status': _('You can only delete the uploaded recipe.')}
    else:
        bkRecipe = user.get_booked_recipe(recipeId)
        if bkRecipe:
            return {'status': _('The recipe have been subscribed, please unsubscribe it before delete.')}
        else:
            recipe.delete_instance()
            return {'status': 'ok', 'id': recipeId}

#设置某个Recipe的推送时间
def ScheduleRecipe(recipeId, form):
    dbInst = BookedRecipe.get_or_none(BookedRecipe.recipe_id == recipeId)
    if dbInst:
        allDays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        dbInst.send_days = [weekday for weekday, day in enumerate(allDays) if str_to_bool(form.get(day, ''))]
        dbInst.send_times = [tm for tm in range(24) if str_to_bool(form.get(str(tm), ''))]
        dbInst.save()
        return {'status': 'ok', 'id': recipeId, 'send_days': dbInst.send_days, 'send_times': dbInst.send_times}
    else:
        return {'status': _('This recipe has not been subscribed to yet.')}

#将上传的Recipe保存到数据库，返回一个结果字典，里面是一些recipe的元数据
def SaveUploadedRecipe(user):
    tips = ''
    try:
        data = request.files.get('recipe_file').read()
    except Exception as e:
        data = None
        tips = str(e)
        
    if not data:
        return {'status': _("Can not read uploaded file, Error:") + '\n' + tips}

    #尝试解码
    match = re.search(br'coding[:=]\s*([-\w.]+)', data[:200])
    enc = match.group(1).decode('utf-8') if match else 'utf-8'
    try:
        src = data.decode(enc)
    except:
        return {'status': _("Failed to decode the recipe. Please ensure that your recipe is saved in utf-8 encoding.")}

    try:
        params = SaveRecipeIfCorrect(user, src)
    except Exception as e:
        return {'status': _("Failed to save the recipe. Error:") + str(e)}

    params['status'] = 'ok'
    return params

#尝试编译recipe代码，如果成功并且数据库中不存在，则保存到数据库
#如果失败则抛出异常，否则返回一个元数据字典
def SaveRecipeIfCorrect(user: KeUser, src: str):
    from calibre.web.feeds.recipes import compile_recipe

    recipe = compile_recipe(src)
    
    #判断是否重复
    oldRecipe = Recipe.get_or_none((Recipe.user == user.name) & (Recipe.title == recipe.title))
    if oldRecipe:
        raise Exception(_('The recipe is already in the library.'))

    params = {"title": recipe.title, "description": recipe.description, "type_": 'upload', 
        "needs_subscription": recipe.needs_subscription, "src": src, "time": datetime.datetime.utcnow(),
        "user": user.name, "language": recipe.language}
    dbInst = Recipe.create(**params)
    params.pop('src')
    params.pop('time')
    params.pop('type_')
    params['id'] = dbInst.recipe_id
    params['language'] = params['language'].lower().replace('-', '_').split('_')[0]
    return params

#修改Recipe的网站登陆信息
@bpSubscribe.post("/recipelogininfo", endpoint='RecipeLoginInfoPostAjax')
@login_required()
def RecipeLoginInfoPostAjax():
    user = get_login_user()
    id_ = request.form.get('id', '')
    account = request.form.get('account')
    password = request.form.get('password')
    recipe = BookedRecipe.get_or_none(BookedRecipe.recipe_id == id_)
    if not recipe:
        return {'status': _('The recipe does not exist.')}

    #任何一个留空则删除登陆信息
    ret = {'status': 'ok'}
    if not account or not password:
        recipe.account = ''
        recipe.password = ''
        ret['result'] = _('The login information for this recipe has been cleared.')
    else:
        recipe.account = account
        recipe.password = password
        ret['result'] =  _('The login information for this recipe has been saved.')
    recipe.save()
    return ret

#查看特定recipe的源码，将python源码转换为html返回
@bpSubscribe.route("/viewsrc/<id_>", endpoint='ViewRecipeSourceCode')
@login_required()
def ViewRecipeSourceCode(id_):
    htmlTpl = """<!DOCTYPE html>\n<html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/prism.css" type="text/css"/>
    <title>{title}</title></head><body><pre><code class="language-python">{body}</code></pre><script type="text/javascript" src="/static/prism.js"></script></body></html>"""
    recipeId = id_.replace('__', ':')
    recipeType, dbId = Recipe.type_and_id(recipeId)
    if recipeType == 'upload':
        recipe = Recipe.get_by_id_or_none(dbId)
        if recipe and recipe.src:
            return htmlTpl.format(title=recipe.title, body=xml_escape(recipe.src))
        else:
            return htmlTpl.format(title="Error", body=_('The recipe does not exist.'))
    else: #内置recipe
        recipe = GetBuiltinRecipeInfo(recipeId)
        src = GetBuiltinRecipeSource(recipeId)
        if recipe and src:
            return htmlTpl.format(title=recipe.get('title'), body=xml_escape(src))
        else:
            return htmlTpl.format(title="Error", body=_('The recipe does not exist.'))
