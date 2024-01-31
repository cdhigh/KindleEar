#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#KindleEar 入口文件，向外提供 app 实例
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Author: cdhigh <https://github.com/cdhigh>

__Author__ = "cdhigh"

import os, sys, logging, builtins, datetime
from flask import Flask, render_template, session, request, g, send_from_directory
from flask_babel import Babel, gettext
#from jinja2 import Environment, FileSystemLoader

__Version__ = '3.0'

# for debug
# 本地启动调试服务器：python.exe dev_appserver.py c:\kindleear
IsRunInLocal = (os.environ.get('SERVER_SOFTWARE', '').startswith('Development'))
log = logging.getLogger()
log.setLevel(logging.INFO if IsRunInLocal else logging.WARN)
builtins.__dict__['default_log'] = log
builtins.__dict__['IsRunInLocal'] = IsRunInLocal
builtins.__dict__['_'] = gettext
appDir = os.path.dirname(os.path.abspath(__file__))
builtins.__dict__['appDir'] = appDir
sys.path.insert(0, 'lib') #for calibre

from apps.view.login import bpLogin  #Blueprints
from apps.view.admin import bpAdmin
from apps.view.adv import bpAdv
from apps.view.deliver import bpDeliver
from apps.view.library import bpLibrary
from apps.view.library_offical import bpLibraryOffical, KINDLEEAR_SITE
from apps.view.logs import bpLogs
from apps.view.setting import bpSetting, supported_languages
from apps.view.share import bpShare
from apps.view.subscribe import bpSubscribe
from apps.work.worker import bpWorker
from apps.work.url2book import bpUrl2Book
from apps.back_end.db_models import ConnectToDatabase, CloseDatabase
from apps.utils import new_secret_key
from config import *

#将config.py里面的部分配置信息写到 os.environ
def SetOsEnvByConfigPy():
    if not TEMP_DIR:
        os.environ['TEMP_DIR'] = ''
    elif os.path.isabs(TEMP_DIR):
        os.environ['TEMP_DIR'] = TEMP_DIR
    else:
        os.environ['TEMP_DIR'] = os.path.join(appDir, TEMP_DIR)
    os.environ['DOWNLOAD_THREAD_NUM'] = str(DOWNLOAD_THREAD_NUM)

SetOsEnvByConfigPy()

#多语种支持
def GetLocale():
    #如果手动设置过要显示的语种有限
    langCode = session.get('langCode')
    if langCode:
        return langCode
    #根据浏览器自动设置
    return request.accept_languages.best_match(supported_languages)

app = Flask(__name__)
#H对Flask的一个Hack，全局关闭autoescape
#app.jinja_env = Environment(loader=FileSystemLoader([os.path.join(appDir, 'templates')]), autoescape=False)
#jinja_environment = app.jinja_env
babel = Babel(app)
app.config['SECRET_KEY'] = 'fdjlkdfjx32QLL2' #new_secret_key()
app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000
babel.init_app(app, locale_selector=GetLocale)
app.config["BABEL_TRANSLATION_DIRECTORIES"] = os.path.abspath('translations/')

#使用GAE来接收邮件
if USE_GAE_INBOUND_EMAIL:
    from google.appengine.api import wrap_wsgi_app
    from apps.view.inbound_email import bpInBoundEmail
    app.wsgi_app = wrap_wsgi_app(app.wsgi_app)  #启用GAE邮件服务
    app.register_blueprint(bpInBoundEmail)

@app.route('/')
def Home():
    return render_template('home.html')

@app.route('/images/<path:image_file>')
def ImageFileRoute(image_file):
    return send_from_directory('images', image_file)
@app.route('/favicon.ico')
def FaviconIcon():
    return send_from_directory('static', 'favicon.ico')

@app.before_request
def BeforeRequest():
    g.version = __Version__
    g.now = datetime.datetime.utcnow
    ConnectToDatabase()

@app.teardown_request
def TeardownRequest(exc=None):
    CloseDatabase()

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
if KINDLEEAR_SITE == KE_DOMAIN:
    app.register_blueprint(bpLibraryOffical)

#调试目的
if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)