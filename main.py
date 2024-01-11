#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#KindleEar入口
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Author:
# cdhigh <https://github.com/cdhigh>

__Author__ = "cdhigh"

import os, sys, logging, builtins
from flask import Flask, render_template, session, request, g
from flask_babel import Babel, gettext

__Version__ = '3.0'

# for debug
# 本地启动调试服务器：python.exe dev_appserver.py c:\kindleear
IsRunInLocal = (os.environ.get('SERVER_SOFTWARE', '').startswith('Development'))
log = logging.getLogger()
log.setLevel(logging.INFO if IsRunInLocal else logging.WARN)
builtins.__dict__['default_log'] = log
builtins.__dict__['IsRunInLocal'] = IsRunInLocal
builtins.__dict__['_'] = gettext

sys.path.insert(0, 'lib')
from books import RegisterBuiltinBooks
from apps.view.login import bpLogin  #Blueprints
from apps.view.admin import bpAdmin
from apps.view.adv import bpAdv
from apps.view.deliver import bpDeliver
from apps.view.library import bpLibrary
from apps.view.logs import bpLogs
from apps.view.setting import bpSetting
from apps.view.share import bpShare
from apps.view.subscribe import bpSubscribe
from apps.work.worker import bdWorker
from apps.work.url2book import bpUrl2Book

RegisterBuiltinBooks() #添加内置书籍到数据库

app = Flask(_name__)
babel = Babel(app)
app.secret_key = 'fdjlkdfjx32QLL2'

#使用GAE来接收邮件
if USE_GAE_INBOUND_EMAIL:
    from google.appengine.api import wrap_wsgi_app
    from apps.view.inbound_email import bpInBoundEmail
    app.wsgi_app = wrap_wsgi_app(app.wsgi_app)  #启用GAE邮件服务
    app.register_blueprint(bpInBoundEmail)

#多语种支持
@babel.localeselector
def GetLocale():
    #手动设置过要显示的语种有限
    langCode = session.get('langCode')
    if langCode:
        return langCode
    #根据浏览器自动设置
    return request.accept_languages.best_match(['zh_cn', 'tr_tr', 'en'])

@app.route('/')
def Home():
    return render_page('home.html', "Home")

@app.before_request
def BeforeRequest():
    g.version = __Version__

@app.route('/env')
def Test():
    strEnv = []
    for d in os.environ:
        strEnv.append("<pre><p>" + str(d).rjust(28) + " | " + str(os.environ[d]) + "</p></pre>")
    return ''.join(strEnv)

app.register_blueprint(bpLogin)
app.register_blueprint(bpAdmin)
app.register_blueprint(bpAdv)
app.register_blueprint(bpDeliver)
app.register_blueprint(bpLibrary)
app.register_blueprint(bpLogs)
app.register_blueprint(bpSetting)
app.register_blueprint(bpShare)
app.register_blueprint(bpSubscribe)
app.register_blueprint(bpWorker)
app.register_blueprint(bpUrl2Book)
