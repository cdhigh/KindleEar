#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#主页和其他路由
import os
from flask import Blueprint, render_template, send_from_directory, current_app
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
    imgDir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images'))
    return send_from_directory(imgDir, image_file)

@bpHome.route('/recipes/<path:recipes_file>')
def RecipesFileRoute(recipes_file):
    recipesDir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'recipes'))
    return send_from_directory(recipesDir, recipes_file)

@bpHome.route('/favicon.ico')
def FaviconIcon():
    return send_from_directory(current_app.static_folder, 'favicon.ico')

@bpHome.route('/robots.txt')
def RobotsTxt():
    return send_from_directory(current_app.static_folder, 'robots.txt')

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
        if app.config['APP_DOMAIN'] == library_offical.KINDLEEAR_SITE:
            app.register_blueprint(library_offical.bpLibraryOffical)

        #使用GAE来接收邮件
        if app.config['INBOUND_EMAIL_SERVICE'] == 'gae':
            from google.appengine.api import wrap_wsgi_app
            from application.view.inbound_email import bpInBoundEmail
            app.wsgi_app = wrap_wsgi_app(app.wsgi_app)  #启用GAE邮件服务
            app.register_blueprint(bpInBoundEmail)
