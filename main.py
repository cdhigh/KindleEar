#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# KindleEar web application entrance
# Visit <https://github.com/cdhigh/KindleEar> for the latest version
# Author: cdhigh <https://github.com/cdhigh>
import os, sys, builtins, logging
from flask import Flask, render_template, session, request
from flask_babel import Babel, gettext

__Version__ = '3.0.0'

sys.path.insert(0, 'lib') #for calibre
appDir = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger()
log.setLevel(logging.WARN) #logging.DEBUG
builtins.__dict__['default_log'] = log
builtins.__dict__['appDir'] = appDir
builtins.__dict__['_'] = gettext

from apps.back_end.db_models import CreateDatabaseTable, ConnectToDatabase, CloseDatabase
from apps.utils import new_secret_key
from apps.routes import *

app = Flask(__name__)
babel = Babel(app)
app.config['SECRET_KEY'] = new_secret_key()
app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000
babel.init_app(app, locale_selector=setting.get_locale)
app.config["BABEL_TRANSLATION_DIRECTORIES"] = os.path.abspath('translations/')

CreateDatabaseTable()

register_routes(app)

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

#调试目的
if __name__ == "__main__":
    default_log.setLevel(logging.DEBUG)
    app.run(host='0.0.0.0', debug=True)