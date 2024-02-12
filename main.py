#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# KindleEar web application entrance
# Visit <https://github.com/cdhigh/KindleEar> for the latest version
# Author: cdhigh <https://github.com/cdhigh>
import os, sys, builtins, logging

appDir = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger()
log.setLevel(logging.WARN) #logging.DEBUG
builtins.__dict__['default_log'] = log
builtins.__dict__['appDir'] = appDir
sys.path.insert(0, os.path.join(appDir, 'application', 'lib'))

from config import *

#将config.py里面的部分配置信息写到 os.environ ，因为有些部分可能不依赖flask运行
def set_env():
    if not TEMP_DIR:
        os.environ['TEMP_DIR'] = ''
    elif os.path.isabs(TEMP_DIR):
        os.environ['TEMP_DIR'] = TEMP_DIR
    else:
        os.environ['TEMP_DIR'] = os.path.join(appDir, TEMP_DIR)
    os.environ['DOWNLOAD_THREAD_NUM'] = str(int(DOWNLOAD_THREAD_NUM))
    os.environ['DATABASE_NAME'] = DATABASE_NAME
    if '://' in DATABASE_NAME:
        os.environ['DATABASE_ENGINE'] = DATABASE_NAME.split('://', 1)[0]
    else:
        os.environ['DATABASE_ENGINE'] = DATABASE_ENGINE
    os.environ['DATABASE_HOST'] = DATABASE_HOST
    os.environ['DATABASE_PORT'] = str(int(DATABASE_PORT))
    os.environ['DATABASE_USERNAME'] = DATABASE_USERNAME
    os.environ['DATABASE_PASSWORD'] = DATABASE_PASSWORD

    os.environ['TASK_QUEUE_SERVICE'] = TASK_QUEUE_SERVICE
    os.environ['CELERY_BROKER_URL'] = CELERY_BROKER_URL
    os.environ['CELERY_RESULT_BACKEND'] = CELERY_RESULT_BACKEND
    os.environ['KE_DOMAIN'] = KE_DOMAIN

set_env()

from application import init_app
app = init_app(__name__, debug=False)
celery_app = app.extensions["celery"]

from application.back_end.db_models import create_database_tables
create_database_tables()

#调试目的
if __name__ == "__main__":
    os.environ['DATASTORE_DATASET'] = app.config['APP_ID']
    os.environ['DATASTORE_EMULATOR_HOST'] = 'localhost:8081'
    os.environ['DATASTORE_EMULATOR_HOST_PATH'] = 'localhost:8081/datastore'
    os.environ['DATASTORE_HOST'] = 'http://localhost:8081'
    os.environ['DATASTORE_PROJECT_ID'] = app.config['APP_ID']
    #cmd to start datastore emulator: gcloud beta emulators datastore start
    default_log.setLevel(logging.DEBUG)
    app.run(host='0.0.0.0', debug=False)
