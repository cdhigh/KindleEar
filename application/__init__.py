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
    randomize_keys(app)
    from .lib.recipe_helper import ClearStaleBuiltinCache
    ClearStaleBuiltinCache()

    @app.before_request
    def BeforeRequest():
        session.permanent = True
        app.permanent_session_lifetime = datetime.timedelta(days=31)
        #appVer: KindleEar代码版本，appBuildDate: 更多的反映recipe库的最新版本日期
        g.version = f'{appVer}({appBuildDate})'
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

#如果用户没有修改预定义的登录和推送密钥, 这里生成随机密钥并保存到数据库
#需要在create_database_tables()之后调用, 保证数据库表结构有效
#'n7ro8QJI1qfe'/'cY9gKC' 是3.5.1及之前版本预置的密钥
def randomize_keys(app):
    secret_key = app.config.get('SECRET_KEY')
    if not secret_key or secret_key == 'n7ro8QJI1qfe':
        from .back_end.db_models import AppInfo
        secret_key = AppInfo.get_value(AppInfo.secretKey)
        if not secret_key:
            from .ke_utils import new_secret_key
            secret_key = new_secret_key(20)
            AppInfo.set_value(AppInfo.secretKey, secret_key)
        app.config['SECRET_KEY'] = secret_key
        os.environ['SECRET_KEY'] = secret_key

    delivery_key = app.config.get('DELIVERY_KEY')
    if not delivery_key or delivery_key == 'cY9gKC':
        delivery_key = AppInfo.get_value(AppInfo.deliveryKey)
        if not delivery_key:
            from .ke_utils import new_secret_key
            delivery_key = new_secret_key(6)
            AppInfo.set_value(AppInfo.deliveryKey, delivery_key)
        app.config['DELIVERY_KEY'] = delivery_key
        os.environ['DELIVERY_KEY'] = delivery_key

