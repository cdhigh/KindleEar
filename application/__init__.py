#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# KindleEar web application
# Author: cdhigh <https://github.com/cdhigh>
__Author__ = "cdhigh"

__Version__ = '3.0.0'

import os, builtins, datetime
from flask import Flask, render_template, session, request, g
from flask_babel import Babel, gettext
builtins.__dict__['_'] = gettext
builtins.__dict__['appVer'] = __Version__

#创建并初始化Flask wsgi对象
def init_app(name, debug=False):
    thisDir = os.path.dirname(os.path.abspath(__file__))
    rootDir = os.path.abspath(os.path.join(thisDir, '..'))
    template_folder = os.path.join(thisDir, 'templates')
    static_folder = os.path.join(thisDir, 'static')
    i18n_folder = os.path.join(thisDir, 'translations')
    
    app = Flask(name, template_folder=template_folder, static_folder=static_folder)
    app.config.from_pyfile(os.path.join(rootDir, 'config.py'))
    
    from .utils import new_secret_key
    
    app.config['SECRET_KEY'] = '12345678' # if debug else new_secret_key()
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024 #32MB

    from .view import setting
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = i18n_folder
    babel = Babel(app)
    babel.init_app(app, locale_selector=setting.get_locale)

    app.config.from_prefixed_env()

    from .back_end.task_queue_adpt import init_task_queue_service
    init_task_queue_service(app)

    from .back_end.db_models import connect_database, close_database

    @app.before_request
    def BeforeRequest():
        g.version = __Version__
        g.now = datetime.datetime.utcnow
        g.allowSignup = app.config['ALLOW_SIGNUP']
        connect_database()

    @app.teardown_request
    def TeardownRequest(exc=None):
        close_database()

    from .routes import register_routes
    register_routes(app)

    return app
