#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#包含 文本翻译器，文本转语音，文章摘要总结 的路由
#Author: cdhigh <https://github.com/cdhigh>
import json, base64, secrets
from functools import wraps
from flask import Blueprint, render_template, request, url_for
from flask_babel import gettext as _
from ..ke_utils import str_to_bool, str_to_int
from ..base_handler import *
from ..back_end.db_models import *
from ..lib.recipe_helper import GetBuiltinRecipeInfo
from ebook_translator import get_trans_engines, HtmlTranslator
from ebook_tts import get_tts_engines, HtmlAudiolator
from ebook_summarizer import get_summarizer_engines, HtmlSummarizer

bpTranslator = Blueprint('bpTranslator', __name__)

#翻译路由每个函数校验recipe有效性都是一样的，使用此装饰器避免重复代码
def translator_route_preprocess(forAjax=False, user=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            recipeId = kwargs.get('recipeId', '')
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
            return func(recipeType, recipe, *args, **kwargs)
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
        recipeId=recipeId, engines=engines, famous=secrets.choice(famous_quotes))

#修改书籍文本翻译器的设置
@bpTranslator.post("/translator/<recipeId>", endpoint='BookTranslatorPost')
@login_required()
@translator_route_preprocess()
def BookTranslatorPost(recipeType, recipe, user, recipeId):
    #构建配置参数
    form = request.form
    engineName = form.get('engine', '')
    apiHost = form.get('api_host', '')
    apiHost = f'https://{apiHost}' if apiHost and not apiHost.startswith('http') else apiHost
    apiKeys = form.get('api_keys', '')
    apiKeys = apiKeys.split('\n') if apiKeys else []
    origStyle = form.get('orig_style', '').replace('{', '').replace('}', '').replace('\n', '')
    transStyle = form.get('trans_style', '').replace('{', '').replace('}', '').replace('\n', '')
    params = {'enable': str_to_bool(form.get('enable', '')), 'engine': engineName,
        'api_host': apiHost, 'api_keys': apiKeys, 'src_lang': form.get('src_lang', ''), 
        'dst_lang': form.get('dst_lang', 'en'), 'position': form.get('position', 'below'),
        'orig_style': origStyle, 'trans_style': transStyle}

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
        recipeId=recipeId, engines=json.dumps(engines, separators=(',', ':')),
        famous=secrets.choice(famous_quotes))

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
    status = data['error'] if data['error'] else 'ok' #type:ignore
    return {'status': status, 'text': data['translated']} #type:ignore

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
        recipeId=recipeId, engines=engines, famous=secrets.choice(famous_quotes))

#修改书籍TTS的设置
@bpTranslator.post("/tts/<recipeId>", endpoint='BookTTSPost')
@login_required()
@translator_route_preprocess()
def BookTTSPost(recipeType, recipe, user, recipeId):
    #构建配置参数
    form = request.form
    #enable: 'both'/'audio_only'/''
    paramNames = ['engine', 'enable', 'api_host', 'api_key', 'language', 'speed', 'send_to',
        'region', 'voice', 'rate', 'pitch', 'volume']
    params = {item: form.get(item, '') for item in paramNames}
    apiHost = params['api_host']
    params['api_host'] = f'https://{apiHost}' if apiHost and not apiHost.startswith('http') else apiHost

    engines = get_tts_engines()
    engine = engines.get(params.get('engine'))
    if engine and engine.get('need_api_key'):
        if not params.get('api_key'):
            tips = _('The api key is required.')
            return render_template('book_audiolator.html', tab="my", tips=tips, params=params, title=recipe.title,
                recipeId=recipeId, engines=json.dumps(engines, separators=(',', ':')),
                famous=secrets.choice(famous_quotes))
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
        recipeId=recipeId, engines=json.dumps(engines, separators=(',', ':')),
        famous=secrets.choice(famous_quotes))

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
    if data['error']: #type: ignore
        data['status'] = data['error'] #type: ignore
    else:
        data['status'] = 'ok' #type: ignore
        data['audio'] = base64.b64encode(data['audio']).decode('utf-8') #type: ignore
        
    return data

#文章摘要总结的配置页面
@bpTranslator.route("/summarizer/<recipeId>", endpoint='BookSummarizerRoute')
@login_required()
@translator_route_preprocess()
def BookSummarizerRoute(recipeType, recipe, user, recipeId):
    from .settings import LangMap
    tips = ''
    bkRecipe = user.get_booked_recipe(recipeId)
    if recipeType == 'custom':
        params = recipe.summarizer #自定义RSS的Recipe和BookedRecipe的summarizer属性一致
    elif bkRecipe:
        params = bkRecipe.summarizer
    else:
        tips = _('This recipe has not been subscribed to yet.')
        params = {}

    engines = json.dumps(get_summarizer_engines(), separators=(',', ':'))
    return render_template('book_summarizer.html', tab="my", tips=tips, params=params, title=recipe.title,
        recipeId=recipeId, engines=engines, langMap=LangMap())

#修改书籍AI文章摘要总结的设置
@bpTranslator.post("/summarizer/<recipeId>", endpoint='BookSummarizerPost')
@login_required()
@translator_route_preprocess()
def BookSummarizerPost(recipeType, recipe, user, recipeId):
    #构建配置参数
    from .settings import LangMap
    form = request.form
    engineName = form.get('engine', '')
    apiHost = form.get('api_host', '')
    apiHost = f'https://{apiHost}' if apiHost and not apiHost.startswith('http') else apiHost
    style = form.get('summary_style', '').replace('{', '').replace('}', '').replace('\n', '')
    params = {'enable': str_to_bool(form.get('enable', '')),  'engine': engineName, 
        'model': form.get('model', ''), 'api_host': apiHost, 'api_key': form.get('api_key', ''), 
        'summary_lang': form.get('summary_lang', ''), 'custom_prompt': form.get('custom_prompt', '').strip(),
        'summary_words': str_to_int(form.get('summary_words', ''), 100), 'summary_style': style,}

    tips = _("Settings Saved!")
    apply_all = str_to_bool(form.get('apply_all', ''))
    if apply_all: #所有的Recipe使用同样的配置
        for item in [*user.all_custom_rss(), *user.get_booked_recipe()]:
            item.summarizer = params
            item.save()
    else:
        bkRecipe = user.get_booked_recipe(recipeId)
        if recipeType == 'custom': #自定义RSS先保存到Recipe，需要的时候再同步到BookedRecipe
            recipe.summarizer = params
            recipe.save()

        if bkRecipe:
            bkRecipe.summarizer = params
            bkRecipe.save()
        elif recipeType != 'custom':
            tips = _('This recipe has not been subscribed to yet.')
    
    engines = json.dumps(get_summarizer_engines(), separators=(',', ':'))
    return render_template('book_summarizer.html', tab="my", tips=tips, params=params, title=recipe.title,
        recipeId=recipeId, engines=engines, langMap=LangMap())

#测试Recipe的AI文章摘要总结设置是否正确
@bpTranslator.post("/summarizer/test/<recipeId>", endpoint='BookSummarizerTestPost')
@login_required(forAjax=True)
@translator_route_preprocess(forAjax=True)
def BookSummarizerTestPost(recipeType, recipe, user, recipeId):
    bkRecipe = recipe if recipeType == 'custom' else user.get_booked_recipe(recipeId)
    if not bkRecipe:
        return {'status': _('This recipe has not been subscribed to yet.')}

    text = request.form.get('text')
    if not text:
        return {'status': _('The text is empty.')}

    summarizer = HtmlSummarizer(bkRecipe.summarizer)
    data = summarizer.summarize_text(text)
    status = data['error'] if data['error'] else 'ok' #type:ignore
    return {'status': status, 'summary': data['summary']} #type:ignore

famous_quotes = [
    "I have a dream. - Martin Luther King Jr.",
    "Be the change that you wish to see in the world. - Mahatma Gandhi",
    "To be, or not to be, that is the question. - William Shakespeare",
    "I think, therefore I am. - René Descartes",
    "Give me liberty, or give me death! - Patrick Henry",
    "The only thing we have to fear is fear itself. - Franklin D. Roosevelt",
    "Injustice anywhere is a threat to justice everywhere. - Martin Luther King Jr.",
    "Ask not what your country can do for you; ask what you can do for your country. - John F. Kennedy",
    "The only way to do great work is to love what you do. - Steve Jobs",
    "Float like a butterfly, sting like a bee. - Muhammad Ali",
    "I am the master of my fate, I am the captain of my soul. - William Ernest Henley",
    "I have nothing to declare except my genius. - Oscar Wilde",
    "You miss 100% of the shots you don't take. - Wayne Gretzky",
    "All men are created equal. - Thomas Jefferson",
    "The unexamined life is not worth living. - Socrates",
    "To infinity and beyond! - Buzz Lightyear",
    "The only thing that is constant is change. - Heraclitus",
    "It does not do to dwell on dreams and forget to live. - J.K. Rowling",
    "Love all, trust a few, do wrong to none. - William Shakespeare",
    "Life is what happens when you're busy making other plans. - John Lennon",
    "The greatest glory in living lies not in never falling, but in rising every time we fall. - Nelson Mandela",
    "The only true wisdom is in knowing you know nothing. - Socrates",
    "In the end, it's not the years in your life that count. It's the life in your years. - Abraham Lincoln",
    "Darkness cannot drive out darkness; only light can do that. Hate cannot drive out hate; only love can do that. - Martin Luther King Jr.",
    "The journey of a thousand miles begins with one step. - Lao Tzu",
    "Imagination is more important than knowledge. - Albert Einstein",
    "We must learn to live together as brothers or perish together as fools. - Martin Luther King Jr.",
    "Do not dwell in the past, do not dream of the future, concentrate the mind on the present moment. - Buddha",
    "Happiness is not something ready-made. It comes from your own actions. - Dalai Lama",
    "Life is like riding a bicycle. To keep your balance, you must keep moving. - Albert Einstein"
]
