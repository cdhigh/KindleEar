#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#主页和其他路由
import os
from flask import Blueprint, render_template, send_from_directory, current_app
from .view import (login, admin, adv, deliver, library, library_offical, logs, settings, share, 
    subscribe, inbound_email, translator, extension, reader)
from .work import worker, url2book

bpHome = Blueprint('bpHome', __name__)

@bpHome.route('/')
def Home():
    demoMode = (current_app.config['DEMO_MODE'] == 'yes')
    return render_template('home.html', demoMode=demoMode)

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
        app.register_blueprint(settings.bpSettings)
        app.register_blueprint(share.bpShare)
        app.register_blueprint(subscribe.bpSubscribe)
        app.register_blueprint(translator.bpTranslator)
        app.register_blueprint(extension.bpExtension)
        app.register_blueprint(reader.bpReader)
        app.register_blueprint(worker.bpWorker)
        app.register_blueprint(url2book.bpUrl2Book)
        app.register_blueprint(library_offical.bpLibraryOffical)
        app.register_blueprint(inbound_email.bpInBoundEmail)

        #如果部署在GAE平台，启用GAE邮件服务
        if app.config['DATABASE_URL'] == 'datastore':
            from google.appengine.api import wrap_wsgi_app
            app.wsgi_app = wrap_wsgi_app(app.wsgi_app)
        
