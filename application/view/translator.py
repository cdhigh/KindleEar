#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#文本翻译器和文本转语音
import json, base64
from functools import wraps
from flask import Blueprint, render_template, request, url_for
from flask_babel import gettext as _
from ..utils import str_to_bool
from ..base_handler import *
from ..back_end.db_models import *
from ..lib.recipe_helper import GetBuiltinRecipeInfo
from ebook_translator import get_trans_engines, HtmlTranslator
from ebook_tts import get_tts_engines, HtmlAudiolator

bpTranslator = Blueprint('bpTranslator', __name__)

#翻译路由每个函数校验recipe有效性都是一样的，使用此装饰器避免重复代码
def translator_route_preprocess(forAjax=False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            recipeId = kwargs.get('recipeId')
            user = get_login_user()
            recipeId = recipeId.replace('__', ':')
            kwargs['recipeId'] = recipeId
            recipeType, dbId = Recipe.type_and_id(recipeId)
            recipe = GetBuiltinRecipeInfo(recipeId) if recipeType == 'builtin' else Recipe.get_by_id_or_none(dbId)
            if not recipe:
                tips = _('The recipe does not exist.')
                if forAjax:
                    return {'status': tips}
                else:
                    return render_template('tipsback.html', tips=tips, urltoback=url_for('bpSubscribe.MySubscription'))
            return func(recipeType, recipe, user, *args, **kwargs)
        return wrapper
    return decorator

#书籍文本翻译器
@bpTranslator.route("/translator/<recipeId>", endpoint='BookTranslatorRoute')
@login_required()
@translator_route_preprocess()
def BookTranslatorRoute(recipeType, recipe, user, recipeId):
    tips = ''
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

#修改书籍文本翻译器的设置
@bpTranslator.post("/translator/<recipeId>", endpoint='BookTranslatorPost')
@login_required()
@translator_route_preprocess()
def BookTranslatorPost(recipeType, recipe, user, recipeId):
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

#测试Recipe的文本翻译器设置是否正确
@bpTranslator.post("/translator/test/<recipeId>", endpoint='BookTranslatorTestPost')
@login_required(forAjax=True)
@translator_route_preprocess(forAjax=True)
def BookTranslatorTestPost(recipeType, recipe, user, recipeId):
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

#书籍文本转语音TTS
@bpTranslator.route("/tts/<recipeId>", endpoint='BookTTSRoute')
@login_required()
@translator_route_preprocess()
def BookTTSRoute(recipeType, recipe, user, recipeId):
    tips = ''
    bkRecipe = user.get_booked_recipe(recipeId)
    if recipeType == 'custom':
        params = recipe.tts #自定义RSS的Recipe和BookedRecipe的tts属性一致
    elif bkRecipe:
        params = bkRecipe.tts
    else:
        tips = _('This recipe has not been subscribed to yet.')
        params = {}

    engines = json.dumps(get_tts_engines(), separators=(',', ':'))
    return render_template('book_audiolator.html', tab="my", tips=tips, params=params, title=recipe.title,
        recipeId=recipeId, engines=engines)

#修改书籍TTS的设置
@bpTranslator.post("/tts/<recipeId>", endpoint='BookTTSPost')
@login_required()
@translator_route_preprocess()
def BookTTSPost(recipeType, recipe, user, recipeId):
    #构建配置参数
    form = request.form
    paramNames = ['engine', 'enable', 'api_host', 'api_key', 'language', 'style', 'role', 'speed', 'send_to']
    params = {item: form.get(item, '') for item in paramNames}

    engines = get_tts_engines()
    engine = engines.get(params.get('engine'))
    if engine and engine.get('need_api_key'):
        if not params.get('api_key'):
            tips = _('The api key is required.')
            return render_template('book_audiolator.html', tab="my", tips=tips, params=params, title=recipe.title,
                recipeId=recipeId, engines=json.dumps(engines, separators=(',', ':')))
    else:
        params['api_host'] = ''

    tips = _("Settings Saved!")
    apply_all = str_to_bool(form.get('apply_all', ''))
    if apply_all: #所有的Recipe使用同样的配置
        for item in [*user.all_custom_rss(), *user.get_booked_recipe()]:
            item.tts = params
            item.save()
    else:
        bkRecipe = user.get_booked_recipe(recipeId)
        if recipeType == 'custom': #自定义RSS先保存到Recipe，需要的时候再同步到BookedRecipe
            recipe.tts = params
            recipe.save()

        if bkRecipe:
            bkRecipe.tts = params
            bkRecipe.save()
        elif recipeType != 'custom':
            tips = _('This recipe has not been subscribed to yet.')
        
    return render_template('book_audiolator.html', tab="my", tips=tips, params=params, title=recipe.title,
        recipeId=recipeId, engines=json.dumps(engines, separators=(',', ':')))

#测试Recipe的文本转语音TTS设置是否正确
@bpTranslator.post("/tts/test/<recipeId>", endpoint='BookTTSTestPost')
@login_required(forAjax=True)
@translator_route_preprocess(forAjax=True)
def BookTTSTestPost(recipeType, recipe, user, recipeId):
    bkRecipe = recipe if recipeType == 'custom' else user.get_booked_recipe(recipeId)
    if not bkRecipe:
        return {'status': _('This recipe has not been subscribed to yet.')}

    text = request.form.get('text')
    if not text:
        return {'status': _('The text is empty.')}

    audiolator = HtmlAudiolator(bkRecipe.tts)
    data = audiolator.audiofy_text(text)
    if data['error']:
        data['status'] = data['error']
    else:
        data['status'] = 'ok'
        data['audiofied'] = base64.b64encode(data['audiofied']).decode('utf-8')
        
    return data
