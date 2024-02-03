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

from .back_end.db_models import CreateDatabaseTable, ConnectToDatabase, CloseDatabase
from .utils import new_secret_key
from .routes import register_routes
from .view import setting
from config import *

#将config.py里面的部分配置信息写到 os.environ
def set_env():
    if not TEMP_DIR:
        os.environ['TEMP_DIR'] = ''
    elif os.path.isabs(TEMP_DIR):
        os.environ['TEMP_DIR'] = TEMP_DIR
    else:
        os.environ['TEMP_DIR'] = os.path.join(appDir, TEMP_DIR)
    os.environ['DOWNLOAD_THREAD_NUM'] = str(DOWNLOAD_THREAD_NUM)

set_env()

#创建并初始化Flask wsgi对象
def init_app(name, debug=False):
    thisDir = os.path.dirname(os.path.abspath(__file__))
    template_folder = os.path.join(thisDir, 'templates')
    static_folder = os.path.join(thisDir, 'static')
    i18n_folder = os.path.join(thisDir, 'translations')
    app = Flask(name, template_folder=template_folder, static_folder=static_folder)
    app.config['SECRET_KEY'] = '12345678' if debug else new_secret_key()
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = i18n_folder
    babel = Babel(app)
    babel.init_app(app, locale_selector=setting.get_locale)

    CreateDatabaseTable()

    if TASK_QUEUE_SERVICE == 'celery':
        from .back_end.task_queue_adpt import celery_init_app
        app.config.from_mapping(
            CELERY={'broker_url': CELERY_BROKER_URL,
                'result_backend': CELERY_RESULT_BACKEND,
                'task_ignore_result': True,
            },
        )
        app.config.from_prefixed_env()
        celery_init_app(app)

    @app.before_request
    def BeforeRequest():
        g.version = __Version__
        g.now = datetime.datetime.utcnow
        ConnectToDatabase()

    @app.teardown_request
    def TeardownRequest(exc=None):
        CloseDatabase()

    register_routes(app)
    return app
