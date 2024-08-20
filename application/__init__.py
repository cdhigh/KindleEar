#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# 创建app对象
# Author: cdhigh <https://github.com/cdhigh>
__Author__ = "cdhigh"

import os, builtins, datetime
from flask import Flask, session, g
from flask_babel import Babel, gettext
builtins.__dict__['_'] = gettext

#创建并初始化Flask wsgi对象
#name: 创建Flask的名字
#cfgMap: 配置字典
#set_env: 重新设置环境变量的函数
#debug: 是否调式Flask
def init_app(name, cfgMap, set_env, debug=False):
    thisDir = os.path.dirname(os.path.abspath(__file__))
    rootDir = os.path.abspath(os.path.join(thisDir, '..'))
    template_folder = os.path.join(thisDir, 'templates')
    static_folder = os.path.join(thisDir, 'static')
    i18n_folder = os.path.join(thisDir, 'translations')
    
    app = Flask(name, template_folder=template_folder, static_folder=static_folder)
    app.config.from_mapping(cfgMap)
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024 #32MB
    
    from .view import settings
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = i18n_folder
    babel = Babel(app)
    babel.init_app(app, locale_selector=settings.get_locale)

    app.config.from_prefixed_env()

    from .back_end.task_queue_adpt import init_task_queue_service
    set_env() #如果部署在gae平台，重新设置被gae模块覆盖的环境变量
    init_task_queue_service(app)

    from .back_end.db_models import create_database_tables, connect_database, close_database
    create_database_tables()

    @app.before_request
    def BeforeRequest():
        session.permanent = True
        app.permanent_session_lifetime = datetime.timedelta(days=31)
        g.version = appVer
        g.now = lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        g.allowSignup = (app.config['ALLOW_SIGNUP'] == 'yes')
        g.allowReader = app.config['EBOOK_SAVE_DIR']
        
        connect_database()

    @app.teardown_request
    def TeardownRequest(exc=None):
        close_database()

    from .routes import register_routes
    register_routes(app)

    return app
