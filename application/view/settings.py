#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#设置页面
#Author: cdhigh <https://github.com/cdhigh>
import os, textwrap
from urllib.parse import urlparse
from flask import Blueprint, render_template, request, redirect, session, current_app as app
from flask_babel import gettext as _
from calibre.customize.profiles import output_profiles
from ..base_handler import *
from ..utils import str_to_bool, str_to_int
from ..back_end.db_models import *
from ..back_end.send_mail_adpt import avaliable_sm_services, send_mail
from .subscribe import UpdateBookedCustomRss

bpSettings = Blueprint('bpSettings', __name__)

supported_languages = ['zh', 'tr_TR', 'en']

all_timezones = {'UTC-12:00': -12, 'UTC-11:00': -11, 'UTC-10:00': -10, 'UTC-9:30': -9.5,
    'UTC-9:00': -9, 'UTC-8:00': -8, 'UTC-7:00': -7, 'UTC-6:00': -6, 'UTC-5:00': -5,
    'UTC-4:00': -4, 'UTC-3:30': -3.5, 'UTC-3:00': -3, 'UTC-2:00': -2, 'UTC-1:00': -1,
    'UTC': 0, 'UTC+1:00': 1, 'UTC+2:00': 2, 'UTC+3:00': 3, 'UTC+3:30': 3.5,
    'UTC+4:00': 4, 'UTC+4:30': 4.5, 'UTC+5:00': 5, 'UTC+5:30': 5.5, 'UTC+5:45': 5.75, 
    'UTC+6:00': 6, 'UTC+6:30': 6.5, 'UTC+7:00': 7, 'UTC+8:00': 8, 'UTC+8:45': 8.75, 
    'UTC+9:00': 9, 'UTC+9:30': 9.5, 'UTC+10:00': 10, 'UTC+10:30': 10.5, 'UTC+11:00': 11,
    'UTC+12:00': 12, 'UTC+12:45': 12.75, 'UTC+13:00': 13, 'UTC+14:00': 14}

@bpSettings.route("/settings", endpoint='Settings')
@login_required()
def Settings(user: KeUser):
    sm_services = avaliable_sm_services()
    return render_template('settings.html', tab='set', user=user, tips='', langMap=LangMap(), 
        sm_services=sm_services, all_timezones=all_timezones, output_profiles=output_profiles)

@bpSettings.post("/settings", endpoint='SettingsPost')
@login_required()
def SettingsPost(user: KeUser):
    form = request.form
    keMail = form.get('kindle_email', '').strip(';, ')
    myTitle = form.get('rss_title')

    send_mail_service = BuildSmSrvDict(user, form)
    if not keMail:
        tips = _("Kindle E-mail is requied!")
    elif not myTitle:
        tips = _("Title is requied!")
    elif not send_mail_service:
        tips = _("Some parameters are missing or wrong.")
    else:
        base_config = user.base_config
        book_config = user.book_config

        enable_send = form.get('enable_send')
        base_config['enable_send'] = enable_send if enable_send in ('all', 'recipes') else ''
        base_config['kindle_email'] = keMail
        base_config['delivery_mode'] = form.get('delivery_mode', 'email') if app.config['EBOOK_SAVE_DIR'] else 'email'
        base_config['webshelf_days'] = str_to_int(form.get('webshelf_days', '7'))
        base_config['timezone'] = float(form.get('timezone', '0'))
        user.send_time = int(form.get('send_time', '0'))
        book_config['type'] = form.get('book_type', 'epub')
        book_config['device'] = form.get('device_type', 'kindle')
        book_config['title_fmt'] = form.get('title_fmt', '')
        allDays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        user.send_days = [weekday for weekday, day in enumerate(allDays) if str_to_bool(form.get(day, ''))]
        book_config['mode'] = form.get('book_mode', '')
        book_config['rm_links'] = form.get('remove_hyperlinks', '')
        book_config['author_fmt'] = form.get('author_format', '') #修正Kindle 5.9.x固件的bug【将作者显示为日期】
        book_config['title'] = myTitle
        book_config['language'] = form.get("book_language", "en")
        book_config['oldest_article'] = int(form.get('oldest', 7))
        book_config['time_fmt'] = form.get('time_fmt', '')
        user.base_config = base_config
        user.book_config = book_config
        user.send_mail_service = send_mail_service
        user.save()
        tips = _("Settings Saved!")

        #根据自定义RSS的使能设置，将自定义RSS添加进订阅列表或从订阅列表移除
        UpdateBookedCustomRss(user)
    
    sm_services = avaliable_sm_services()
    return render_template('settings.html', tab='set', user=user, tips=tips, langMap=LangMap(), 
        sm_services=sm_services, all_timezones=all_timezones, output_profiles=output_profiles)

#构建发送邮件服务配置字典，返回空字典表示出错
#form: request.form 实例
def BuildSmSrvDict(user: KeUser, form):
    srv = user.send_mail_service.copy()
    srvType = form.get('sm_service', '')
    #service==admin 说明和管理员的设置一致
    if user.name == os.getenv('ADMIN_NAME') or srv.get('service') != 'admin':
        srv['service'] = srvType
        srv['apikey'] = form.get('sm_apikey', '')
        srv['secret_key'] = form.get('sm_secret_key', '')
        srv['host'] = form.get('sm_host', '')
        srv['port'] = str_to_int(form.get('sm_port', '587'))
        srv['username'] = form.get('sm_username', '')
        srv['password'] = user.encrypt(form.get('sm_password', ''))
        srv['save_path'] = form.get('sm_save_path', '')
        validations = {
            'sendgrid': lambda srv: srv['apikey'],
            'mailjet': lambda srv: srv['apikey'] and srv['secret_key'],
            'smtp': lambda srv: all((srv['host'], srv['port'], srv['password'])), #部分smtp不需要账号名
            'local': lambda srv: srv['save_path']
        }
        if not validations.get(srvType, lambda _: True)(srv):
            srv = {}
    return srv

@bpSettings.post("/send_test_email", endpoint='SendTestEmailPost')
@login_required()
def SendTestEmailPost(user: KeUser):
    srcUrl = request.form.get('url', '')
    body = textwrap.dedent(f"""\
    Dear {user.name}, 

    This is a test email from KindleEar, sent to verify the accuracy of the email sending configuration.  
    Please do not reply it.   

    Receiving this email confirms that your KindleEar web application can send emails successfully.   
    Thank you for your attention to this matter.   

    Best regards,
    [KindleEar]
    [From {srcUrl}]
    """)

    emails = user.cfg('kindle_email').split(',') if user.cfg('kindle_email') else []
    userEmail = user.cfg('email')
    if userEmail and userEmail not in emails:
        emails.append(userEmail)
    
    if emails:
        status = 'ok'
        try:
            send_mail(user, emails, 'Test email from KindleEar', body, attachments=[('test.txt', body.encode('utf-8'))])
        except Exception as e:
            status = str(e)
    else:
        status = _("You have not yet set up your email address. Please go to the 'Admin' page to add your email address firstly.")

    return {'status': status, 'emails': emails}

#高危险函数，调试使用，有时候需要了解目标平台的具体信息，发布时直接屏蔽
# @bpSettings.route('/debugcmd')
# @login_required()
# def DebugcmdRoute(user: KeUser):
#     return render_template('debug_cmd.html')
# @bpSettings.post('/debugcmd')
# @login_required(forAjax=True)
# def DebugcmdPost(user: KeUser):
#     import sys, locale, json, subprocess
#     cmd = request.form.get('cmd', '')
#     type_ = request.form.get('type', '')
#     encodes = set([sys.getfilesystemencoding(), sys.getdefaultencoding(), locale.getpreferredencoding(),
#         'utf-8', 'latin-1', 'cp936'])
#     def serialize(obj):
#         if isinstance(obj, (int, float, str, bool, type(None))):
#             return obj
#         elif isinstance(obj, (list, tuple)):
#             return [serialize(item) for item in obj]
#         else:
#             return str(obj)
#     try:
#         if type_ == 'shell':
#             result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
#             for encode in encodes:
#                 try:
#                     result = result.decode(encode).rstrip('\n')
#                     break
#                 except UnicodeDecodeError:
#                     pass
#         else:
#             result = {}
#             try:
#                 exec(cmd, globals(), result)
#             except Exception as e:
#                 result = str(e)
#             result = json.dumps(serialize(result))
#         response = {'status': 'ok', 'result': result}
#     except subprocess.CalledProcessError as e:
#         response = {'status': e.output.decode('utf-8').rstrip('\n')}
#     # 返回 JSON 格式的结果给网页
#     return response

#显示环境变量的值
@bpSettings.route('/env')
@login_required()
def DisplayEnv(user: KeUser):
    strEnv = []
    for d in os.environ:
        strEnv.append("<pre><p>" + str(d).rjust(28) + " | " + str(os.environ[d]) + "</p></pre>")
    strEnv.append("<pre><p>" + 'appDir'.rjust(28) + " | " + appDir + "</p></pre>")
    return ''.join(strEnv)

#设置国际化语种
@bpSettings.route("/setlocale/<langCode>")
def SetLang(langCode):
    global supported_languages
    if langCode not in supported_languages:
        langCode = "en"
    session['langCode'] = langCode
    url = request.args.get('next', '/').replace('\\', '')
    parts = urlparse(url)
    if parts.netloc or parts.scheme:
        url = '/'
    return redirect(url)
    
#Babel选择显示哪种语言的回调函数
def get_locale():
    try:
        langCode = session.get('langCode') or request.accept_languages.best_match(supported_languages)
    except: #Working outside of request context
        langCode = 'en'
    return langCode or ''

#各种语言的语种代码和文字描述的对应关系
def LangMap():
    return {"en-us": _("English"),
        "zh-cn": _("Chinese"),
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
        "ha": _("Hausa"),
        "th-th": _("Thai"),
        "pl-pl": _("Polish"),
        "ro-ro": _("Romanian"),
        "hu-hu": _("Hungarian"),
        "sv-se": _("Swedish"),
        "he-il": _("Hebrew"),
        "no-no": _("Norwegian"),
        "fi-fi": _("Finnish"),
        "da-dk": _("Danish"),
        "uk-ua": _("Ukrainian"),
        "ta": _("Tamil"),
        "mr": _("Marathi"),
        "my": _("Burmese"),
        "am": _("Amharic"),
        "az": _("Azerbaijani"),
        "kk": _("Kazakh"),}
