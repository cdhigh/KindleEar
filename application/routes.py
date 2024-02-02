#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#主页和其他路由
import os
from flask import Blueprint, render_template, send_from_directory
from .view import login
from .view import admin
from .view import adv
from .view import deliver
from .view import library
from .view import library_offical
from .view import logs
from .view import setting
from .view import share
from .view import subscribe
from .work import worker
from .work import url2book
from config import KE_DOMAIN, USE_GAE_INBOUND_EMAIL

bpHome = Blueprint('bpHome', __name__)

@bpHome.route('/')
def Home():
    return render_template('home.html')

@bpHome.route('/env')
def Test():
    strEnv = []
    for d in os.environ:
        strEnv.append("<pre><p>" + str(d).rjust(28) + " | " + str(os.environ[d]) + "</p></pre>")
    return ''.join(strEnv)

@bpHome.route('/images/<path:image_file>')
def ImageFileRoute(image_file):
    return send_from_directory('images', image_file)

@bpHome.route('/favicon.ico')
def FaviconIcon():
    return send_from_directory('static', 'favicon.ico')

def register_routes(app):
    with app.app_context():
        app.register_blueprint(bpHome)
        app.register_blueprint(login.bpLogin)
        app.register_blueprint(admin.bpAdmin)
        app.register_blueprint(adv.bpAdv)
        app.register_blueprint(deliver.bpDeliver)
        app.register_blueprint(library.bpLibrary)
        app.register_blueprint(logs.bpLogs)
        app.register_blueprint(setting.bpSetting)
        app.register_blueprint(share.bpShare)
        app.register_blueprint(subscribe.bpSubscribe)
        app.register_blueprint(worker.bpWorker)
        app.register_blueprint(url2book.bpUrl2Book)
        if library_offical.KINDLEEAR_SITE == KE_DOMAIN:
            app.register_blueprint(library_offical.bpLibraryOffical)

        #使用GAE来接收邮件
        if USE_GAE_INBOUND_EMAIL:
            from google.appengine.api import wrap_wsgi_app
            from apps.view.inbound_email import bpInBoundEmail
            app.wsgi_app = wrap_wsgi_app(app.wsgi_app)  #启用GAE邮件服务
            app.register_blueprint(bpInBoundEmail)
