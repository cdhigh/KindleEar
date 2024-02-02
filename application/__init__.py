#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Author: cdhigh <https://github.com/cdhigh>
__Author__ = "cdhigh"

import os, builtins, datetime
from flask import Flask, render_template, session, request, g
from flask_babel import Babel, gettext
builtins.__dict__['_'] = gettext

from .back_end.db_models import CreateDatabaseTable, ConnectToDatabase, CloseDatabase
from .utils import new_secret_key
from .routes import register_routes
from .view import setting
from config import APP_ID, TEMP_DIR, DOWNLOAD_THREAD_NUM

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

def init_app(debug=False):
    app = Flask(__name__)
    babel = Babel(app)
    app.config['SECRET_KEY'] = new_secret_key() if debug else '12345678'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000
    babel.init_app(app, locale_selector=setting.get_locale)
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = os.path.abspath('translations/')

    CreateDatabaseTable()

    @app.before_request
    def BeforeRequest():
        g.version = appVersion
        g.now = datetime.datetime.utcnow
        ConnectToDatabase()

    @app.teardown_request
    def TeardownRequest(exc=None):
        CloseDatabase()

    register_routes(app)
    return app
