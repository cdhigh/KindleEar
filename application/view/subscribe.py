#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Author: cdhigh <https://github.com/cdhigh>
#管理订阅页面
import datetime, json, re
from urllib.parse import urljoin, unquote, quote
from flask import Blueprint, render_template, request, redirect, url_for, current_app as app
from flask_babel import gettext as _
from ..base_handler import *
from ..back_end.db_models import *
from ..back_end.task_queue_adpt import create_notifynewsubs_task
from ..utils import str_to_bool, xml_escape, utcnow
from ..lib.urlopener import UrlOpener
from ..lib.recipe_helper import GetBuiltinRecipeInfo, GetBuiltinRecipeSource
from .library import LIBRARY_MGR, SUBSCRIBED_FROM_LIBRARY, LIBRARY_GETSRC, buildKeUrl

bpSubscribe = Blueprint('bpSubscribe', __name__)

#管理我的订阅和杂志列表
@bpSubscribe.route("/my", endpoint='MySubscription')
@login_required()
def MySubscription(user: KeUser):
    tips = ''
    share_key = user.share_links.get('key', '')
    args = request.args
    title_to_add = args.get('title_to_add', '').strip() #from Bookmarklet/browser extension
    url_to_add = args.get('url_to_add', '').strip()
    isfulltext = str_to_bool(args.get('isfulltext'))
    my_custom_rss = [item.to_dict(only=[Recipe.id, Recipe.title, Recipe.url, Recipe.isfulltext, 
        Recipe.translator, Recipe.tts, Recipe.summarizer, Recipe.custom]) for item in user.all_custom_rss()]

    my_uploaded_recipes = [item.to_dict(only=[Recipe.id, Recipe.title, Recipe.description, Recipe.needs_subscription, 
        Recipe.language, Recipe.translator, Recipe.summarizer, Recipe.tts]) for item in user.all_uploaded_recipe()]

    my_booked_recipes = [item.to_dict(exclude=[BookedRecipe.encrypted_pwd])
        for item in user.get_booked_recipe() if not item.recipe_id.startswith('custom:')]

    #使用不同的id前缀区分不同的rss类型，同时对其他数据进行适当处理
    for item in my_custom_rss:
        item['id'] = 'custom:{}'.format(item['id'])
        item['tr_enable'] = item['translator'].get('enable')
        item['tts_enable'] = item['tts'].get('enable')
        item['summary_enable'] = item['summarizer'].get('enable')
        item['separated'] = item['custom'].get('separated', False)
    for item in my_uploaded_recipes:
        item['id'] = 'upload:{}'.format(item['id'])
        item['language'] = item['language'].lower().replace('-', '_').split('_')[0]
        item['tr_enable'] = item['translator'].get('enable')
        item['tts_enable'] = item['tts'].get('enable')
        item['summary_enable'] = item['summarizer'].get('enable')
    for item in my_booked_recipes:
        if not isinstance(item['send_days'], dict): #处理以前版本的不兼容修改
            item['send_days'] = {}
        item['tr_enable'] = item['translator'].get('enable')
        item['tts_enable'] = item['tts'].get('enable')
        item['summary_enable'] = item['summarizer'].get('enable')
        
    my_custom_rss = json.dumps(my_custom_rss, separators=(',', ':'))
    my_uploaded_recipes=json.dumps(my_uploaded_recipes, separators=(',', ':'))
    my_booked_recipes = json.dumps(my_booked_recipes, separators=(',', ':'))
    subscribe_url = urljoin(app.config['APP_DOMAIN'], url_for("bpSubscribe.MySubscription"))
    url2book_url = urljoin(app.config['APP_DOMAIN'], url_for("bpUrl2Book.Url2BookRoute"))
    return render_template("my.html", tab="my", **locals())

#添加自定义RSS
@bpSubscribe.post("/my", endpoint='MySubscriptionPost')
@login_required()
def MySubscriptionPost(user: KeUser):
    form = request.form
    title = form.get('rss_title')
    url = form.get('url')
    isfulltext = bool(form.get('fulltext'))
    if not title or not url:
        return redirect(url_for("bpSubscribe.MySubscription"))

    if not url.lower().startswith('http'): #http and https
        url = ('https:/' if url.startswith('/') else 'https://') + url

    #判断是否重复
    if Recipe.get_or_none((Recipe.user == user.name) & (Recipe.title == title)):
        return redirect(url_for("bpSubscribe.MySubscription", tips=(_("Duplicated subscription!"))))
    else:
        Recipe.create(title=title, url=url, isfulltext=isfulltext, type_='custom', user=user.name)
        return redirect(url_for("bpSubscribe.MySubscription"))

#添加/删除自定义RSS订阅的AJAX处理函数
@bpSubscribe.post("/customrss/<actType>", endpoint='FeedsAjaxPost')
@login_required(forAjax=True)
def FeedsAjaxPost(actType: str, user: KeUser):
    form = request.form
    actType = actType.lower()

    if actType == 'delete':
        return DeleteCustomRss(user, form.get('id', ''))
    elif actType == 'add':
        return AddCustomRss(user, form)
    else:
        return {'status': 'Unknown command: {}'.format(actType)}

@bpSubscribe.route("/notifynewsubs", endpoint='NotifyNewSubscriptionRoute')
@login_required()
def NotifyNewSubscriptionRoute(user: KeUser):
    args = request.args
    if args.get('key') == app.config['DELIVERY_KEY']:
        title = args.get('title', '')
        url = args.get('url', '')
        recipeId = args.get('recipeId', '')
        return NotifyNewSubscription(title, url, recipeId)
    else:
        return 'key invalid'

#添加自定义RSS
#form: request.form 实例
def AddCustomRss(user: KeUser, form):
    title = form.get('title', '')
    url = form.get('url', '')
    isfulltext = str_to_bool(form.get('fulltext', ''))
    separated = str_to_bool(form.get('separated', ''))
    fromSharedLibrary = str_to_bool(form.get('fromsharedlibrary', ''))
    recipeId = form.get('recipeId', '')

    ret = {'status':'ok', 'title':title, 'url':url, 'isfulltext':isfulltext, 'recipeId': recipeId,
        'separated': separated}

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

            recipe = Recipe.get_by_id_or_none(params['dbId'])
            params.pop('dbId', None)
            ret.update(params)
            if recipe:
                SubscribeRecipe(user, params['id'], recipe, separated)
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
                custom={'separated': separated})
            ret['id'] = rss.recipe_id
            UpdateBookedCustomRss(user)
    
    #如果是从共享库中订阅的，则通知共享服务器，提供订阅数量信息，以便排序
    if fromSharedLibrary:
        key = app.config['DELIVERY_KEY']
        create_notifynewsubs_task({'title': title, 'url': quote(url), 'recipeId': recipeId, 'key': key})

    return ret

#删除自定义RSS
def DeleteCustomRss(user: KeUser, rssId: str):
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
    for dbInst in list(BookedRecipe.select()):
        recipeType, recipeId = Recipe.type_and_id(dbInst.recipe_id)
        if recipeType != 'builtin' and not Recipe.get_by_id_or_none(recipeId):
            dbInst.delete_instance()
    
    custom_rss = user.all_custom_rss()[::-1]
    if user.cfg('enable_send') == 'all': #添加自定义RSS的订阅
        for rss in custom_rss:
            BookedRecipe.get_or_create(recipe_id=rss.recipe_id, defaults={'user': userName, 
                'title': rss.title, 'description': rss.description, 'time': utcnow(),
                'translator': rss.translator, 'tts': rss.tts, 'summarizer': rss.summarizer, 'custom': rss.custom,
                'separated': rss.custom.get('separated', False)})
    elif custom_rss: #删除订阅
        ids = [rss.recipe_id for rss in custom_rss]
        BookedRecipe.delete().where(BookedRecipe.recipe_id.in_(ids)).execute()

#通知共享服务器，有一个新的订阅
def NotifyNewSubscription(title: str, url: str, recipeId: bool, key: str=''):
    path = LIBRARY_MGR + SUBSCRIBED_FROM_LIBRARY
    data = {'title': title, 'url': unquote(url), 'recipeId': recipeId}
    resp = UrlOpener().open(buildKeUrl(path), data=data)
    return f'{resp.status_code}'

#订阅/退订内置或上传Recipe的AJAX处理函数
@bpSubscribe.post("/recipe/<actType>", endpoint='RecipeAjaxPost')
@login_required(forAjax=True)
def RecipeAjaxPost(actType: str, user: KeUser):
    form = request.form
    if actType == 'upload': #上传Recipe
        return SaveUploadedRecipe(user, form.get('action_after_upload'))

    recipeId = form.get('id', '')
    recipeType, dbId = Recipe.type_and_id(recipeId)
    recipe = GetBuiltinRecipeInfo(recipeId) if recipeType == 'builtin' else Recipe.get_by_id_or_none(dbId)

    if not recipe:
        return {'status': _('The recipe does not exist.')}
    elif actType == 'unsubscribe': #退订
        return UnsubscribeRecipe(user, recipeId, recipe)
    elif actType == 'subscribe': #订阅
        separated = str_to_bool(form.get('separated', ''))
        return SubscribeRecipe(user, recipeId, recipe, separated)
    elif actType == 'delete': #删除已经上传的recipe
        force = str_to_bool(form.get('force'))
        return DeleteRecipe(user, recipeId, recipeType, recipe, force)
    elif actType == 'schedule': #设置某个recipe的自定义推送时间
        return ScheduleRecipe(user, recipeId, form)
    else:
        return {'status': _('Unknown command: {}').format(actType)}

#订阅某个Recipe
def SubscribeRecipe(user: KeUser, recipeId: str, recipe: Recipe, separated: bool):
    ret = {'recipe_id': recipeId, 'title': recipe.title, 'description': recipe.description,
        'needs_subscription': recipe.needs_subscription, 'separated': separated}
    
    dbInst = user.get_booked_recipe(recipeId)
    if dbInst: #不报错，更新separated属性
        dbInst.separated = separated #type:ignore
        dbInst.save() #type:ignore
    else:
        BookedRecipe.create(user=user.name, **ret)

    ret['status'] = 'ok'
    return ret

#退订某个Recipe
def UnsubscribeRecipe(user: KeUser, recipeId: str, recipe: Recipe):
    BookedRecipe.delete().where((BookedRecipe.user == user.name) & (BookedRecipe.recipe_id == recipeId)).execute()
    LastDelivered.delete().where((LastDelivered.user == user.name) & (LastDelivered.bookname == recipe.title)).execute()
    return {'status':'ok', 'id': recipeId, 'title': recipe.title, 'desc': recipe.description}

#删除某个Recipe
#recipe: 待删除的Recipe实例
#force: 如果为True，则不管是否已经被订阅都可以删除
def DeleteRecipe(user: KeUser, recipeId: str, recipeType: str, recipe: Recipe, force: bool):
    if recipeType == 'builtin':
        return {'status': _('You can only delete the uploaded recipe.')}
    
    if force:
        BookedRecipe.delete().where((BookedRecipe.user == user.name) & (BookedRecipe.recipe_id == recipeId)).execute()
    elif user.get_booked_recipe(recipeId):
        return {'status': _('The recipe have been subscribed, please unsubscribe it before delete.')}
    
    LastDelivered.delete().where((LastDelivered.user == user.name) & (LastDelivered.bookname == recipe.title)).execute()
    recipe.delete_instance()
    return {'status': 'ok', 'id': recipeId}

#设置某个Recipe的推送时间
#form: request.form实例
def ScheduleRecipe(user: KeUser, recipeId: str, form):
    dbInst = BookedRecipe.get_or_none((BookedRecipe.user == user.name) & (BookedRecipe.recipe_id == recipeId))
    if dbInst:
        type_ = form.get('type')
        if type_ in ('weekday', 'date'):
            days = [int(item) for item in form.get('days', '').replace(' ', '').split(',') if item.isdigit()]
            dbInst.send_days = {'type': type_, 'days': days}
        else:
            dbInst.send_days = {}
        dbInst.send_times = [int(item) for item in form.get('times', '').replace(' ', '').split(',') if item.isdigit()]
        dbInst.save()
        return {'status': 'ok', 'id': recipeId, 'send_days': dbInst.send_days, 'send_times': dbInst.send_times}
    else:
        return {'status': _('This recipe has not been subscribed to yet.')}

#将上传的Recipe保存到数据库，返回一个结果字典，里面是一些recipe的元数据
#将上传表单的文件保存为recipe
#actionAfterUpload: subscribe-上传后订阅，separated-上传后订阅（独立推送），空-上传后无动作
def SaveUploadedRecipe(user, actionAfterUpload):
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

    if actionAfterUpload:
        separated = (actionAfterUpload == 'separated')
        recipe = Recipe.get_by_id_or_none(params['dbId'])
        SubscribeRecipe(user, params['id'], recipe, separated)

    params.pop('dbId', None)
    params['status'] = 'ok'
    return params

#尝试编译recipe代码，如果成功并且数据库中不存在，则保存到数据库
#如果失败则抛出异常，否则返回一个元数据字典
def SaveRecipeIfCorrect(user: KeUser, src: str):
    from calibre.web.feeds.recipes import compile_recipe

    recipe = compile_recipe(src)
    if not recipe:
        raise Exception(_('Cannot find any subclass of BasicNewsRecipe.'))
    
    #判断是否重复
    oldRecipe = Recipe.get_or_none((Recipe.user == user.name) & (Recipe.title == recipe.title))
    if oldRecipe:
        raise Exception(_('The recipe is already in the library.'))

    params = {"title": recipe.title, "description": recipe.description, "type_": 'upload', 
        "needs_subscription": recipe.needs_subscription, "src": src, "time": utcnow(),
        "user": user.name, "language": recipe.language}
    dbInst = Recipe.create(**params)
    params.pop('src')
    params.pop('time')
    params.pop('type_')
    params['id'] = dbInst.recipe_id
    params['dbId'] = dbInst.id
    params['language'] = params['language'].lower().replace('-', '_').split('_')[0]

    LastDelivered.delete().where((LastDelivered.user == user.name) & (LastDelivered.bookname == recipe.title)).execute()

    return params

#修改Recipe的网站登陆信息
@bpSubscribe.post("/recipelogininfo", endpoint='RecipeLoginInfoPostAjax')
@login_required()
def RecipeLoginInfoPostAjax(user: KeUser):
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
def ViewRecipeSourceCode(id_: str, user: KeUser):
    htmlTpl = """<!DOCTYPE html>\n<html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/prism.css" type="text/css"/>
    <title>{title}</title></head><body class="line-numbers"><pre><code class="language-python">{body}</code></pre>
    <script type="text/javascript" src="/static/prism.js"></script></body></html>"""
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
