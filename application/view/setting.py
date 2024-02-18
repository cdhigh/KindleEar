#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#设置页面
import locale, os
from flask import Blueprint, render_template, request, redirect, session
from flask import current_app as app
from flask_babel import gettext as _
from ..base_handler import *
from ..utils import str_to_bool, str_to_int, ke_encrypt
from ..back_end.db_models import *
from ..back_end.send_mail_adpt import avaliable_sm_services
from .subscribe import UpdateBookedCustomRss

bpSetting = Blueprint('bpSetting', __name__)

supported_languages = ['zh', 'tr_TR', 'en']

@bpSetting.route("/setting", endpoint='Setting')
@login_required()
def Setting(tips=None):
    user = get_login_user()
    sm_services = avaliable_sm_services()
    return render_template('setting.html', tab='set', user=user, tips=tips, src_mail=app.config['SRC_EMAIL'], 
        langMap=LangMap(), sm_services=sm_services)

@bpSetting.post("/setting", endpoint='SettingPost')
@login_required()
def SettingPost():
    user = get_login_user()
    form = request.form
    keMail = form.get('kindle_email', '').strip(';, ')
    myTitle = form.get('rss_title')

    #service==admin 说明和管理员的设置一致
    sm_srv_need = False
    sm_srv_type = ''
    if user.name == os.getenv('ADMIN_NAME') or user.send_mail_service.get('service') != 'admin':
        sm_srv_need = True
        sm_srv_type = form.get('sm_service')
        sm_apikey = form.get('sm_apikey', '')
        sm_host = form.get('sm_host', '')
        sm_port = str_to_int(form.get('sm_port'))
        sm_username = form.get('sm_username', '')
        sm_password = form.get('sm_password', '')
        sm_save_path = form.get('sm_save_path', '')
        send_mail_service = {'service': sm_srv_type, 'apikey': sm_apikey, 'host': sm_host,
            'port': sm_port, 'username': sm_username, 'password': '', 
            'save_path': sm_save_path}
        #只有处于smtp模式并且密码存在才更新，空或几个星号则不更新
        if sm_srv_type == 'smtp':
            if sm_password and sm_password.strip('*'):
                send_mail_service['password'] = ke_encrypt(sm_password, user.secret_key)
            else:
                send_mail_service['password'] = user.send_mail_service.get('password', '')
    
    if not keMail:
        tips = _("Kindle E-mail is requied!")
    elif not myTitle:
        tips = _("Title is requied!")
    elif sm_srv_type == 'sendgrid' and not sm_apikey:
        tips = _("Some parameters are missing or wrong.")
    elif sm_srv_type == 'smtp' and not all((sm_host, sm_port, sm_username, sm_password)):
        tips = _("Some parameters are missing or wrong.")
    elif sm_srv_type == 'local' and not sm_save_path:
        tips = _("Some parameters are missing or wrong.")
    else:
        enable_send = form.get('enable_send', '')
        if enable_send == 'all':
            user.enable_send = True
            user.enable_custom_rss = True
        elif enable_send == 'recipes':
            user.enable_send = True
            user.enable_custom_rss = False
        else:
            user.enable_send = False
            user.enable_custom_rss = False

        user.kindle_email = keMail
        user.timezone = int(form.get('timezone', app.config['TIMEZONE']))
        user.send_time = int(form.get('send_time', '0'))
        user.book_type = form.get('book_type', 'epub')
        user.device = form.get('device_type', 'kindle')
        user.title_fmt = form.get('title_fmt', '')
        allDays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        user.send_days = [weekday for weekday, day in enumerate(allDays) if str_to_bool(form.get(day, ''))]
        user.book_mode = form.get('book_mode', '')
        user.remove_hyperlinks = form.get('remove_hyperlinks', '')
        user.author_format = form.get('author_format', '')
        user.book_title = myTitle
        user.book_language = form.get("book_language", "en")
        user.oldest_article = int(form.get('oldest', 7))
        user.time_fmt = form.get('time_fmt', '')
        if sm_srv_need:
            user.send_mail_service = send_mail_service
        user.save()
        tips = _("Settings Saved!")

        #根据自定义RSS的使能设置，将自定义RSS添加进订阅列表或从订阅列表移除
        UpdateBookedCustomRss(user)
    
    sm_services = avaliable_sm_services()
    return render_template('setting.html', tab='set', user=user, tips=tips, src_mail=app.config['SRC_EMAIL'], 
        langMap=LangMap(), sm_services=sm_services)

#设置国际化语种
@bpSetting.route("/setlocale/<langCode>")
def SetLang(langCode):
    global supported_languages
    if langCode not in supported_languages:
        langCode = "en"
    session['langCode'] = langCode
    return redirect('/')

#Babel选择显示哪种语言的回调函数
def get_locale():
    try:
        langCode = session.get('langCode')
    except: #Working outside of request context
        langCode = 'en'
    return langCode if langCode else request.accept_languages.best_match(supported_languages)

#各种语言的语种代码和文字描述的对应关系
def LangMap():
    return {"zh-cn": _("Chinese"),
        "en-us": _("English"),
        "fr-fr": _("French"),
        "es-es": _("Spanish"),
        "pt-br": _("Portuguese"),
        "de-de": _("German"),
        "it-it": _("Italian"),
        "ja-jp": _("Japanese"),
        "ru-ru": _("Russian"),
        "tr-tr": _("Turkish"),
        "ko-kr": _("Korean"),
        "ar": _("Arabic"),
        "cs": _("Czech"),
        "nl": _("Dutch"),
        "el": _("Greek"),
        "hi": _("Hindi"),
        "ms": _("Malaysian"),
        "bn": _("Bengali"),
        "fa": _("Persian"),
        "ur": _("Urdu"),
        "sw": _("Swahili"),
        "vi": _("Vietnamese"),
        "pa": _("Punjabi"),
        "jv": _("Javanese"),
        "tl": _("Tagalog"),
        "ha": _("Hausa"),}
