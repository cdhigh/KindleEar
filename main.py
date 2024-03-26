#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# KindleEar web application entrance
# Visit <https://github.com/cdhigh/KindleEar> for the latest version
# Author: cdhigh <https://github.com/cdhigh>

__Version__ = '3.0.0b'

import os, sys, builtins, logging
from config import *

appDir = os.path.dirname(os.path.abspath(__file__))
#logName = None if (DATABASE_URL == 'datastore') else 'gunicorn.error'
log = logging.getLogger()

builtins.__dict__['default_log'] = log
builtins.__dict__['appDir'] = appDir
builtins.__dict__['appVer'] = __Version__
sys.path.insert(0, os.path.join(appDir, 'application', 'lib'))

#将config.py里面的部分配置信息写到 os.environ ，因为有些部分可能不依赖flask运行
def set_env():
    if not TEMP_DIR:
        os.environ['TEMP_DIR'] = ''
    elif os.path.isabs(TEMP_DIR):
        os.environ['TEMP_DIR'] = TEMP_DIR
    else:
        os.environ['TEMP_DIR'] = os.path.join(appDir, TEMP_DIR)
    os.environ['DOWNLOAD_THREAD_NUM'] = str(int(DOWNLOAD_THREAD_NUM))
    os.environ['DATABASE_URL'] = DATABASE_URL
    os.environ['TASK_QUEUE_SERVICE'] = TASK_QUEUE_SERVICE
    os.environ['TASK_QUEUE_BROKER_URL'] = TASK_QUEUE_BROKER_URL
    os.environ['APP_ID'] = APP_ID
    os.environ['APP_DOMAIN'] = APP_DOMAIN
    os.environ['SERVER_LOCATION'] = SERVER_LOCATION
    os.environ['ADMIN_NAME'] = ADMIN_NAME
    os.environ['HIDE_MAIL_TO_LOCAL'] = '1' if HIDE_MAIL_TO_LOCAL else ''

set_env()

from application import init_app
app = init_app(__name__, debug=False)
celery_app = app.extensions.get("celery", None)
log.setLevel(logging.INFO)   #logging.DEBUG, WARNING

def main():
    if len(sys.argv) == 2 and sys.argv[1] == 'debug':
        #os.environ['DATASTORE_DATASET'] = app.config['APP_ID']
        #os.environ['DATASTORE_EMULATOR_HOST'] = 'localhost:8081'
        #os.environ['DATASTORE_EMULATOR_HOST_PATH'] = 'localhost:8081/datastore'
        #os.environ['DATASTORE_HOST'] = 'http://localhost:8081'
        #os.environ['DATASTORE_PROJECT_ID'] = app.config['APP_ID']
        #cmd to start datastore emulator: gcloud beta emulators datastore start
        default_log.setLevel(logging.DEBUG)
        app.run(host='0.0.0.0', debug=False)
        return 0
    elif len(sys.argv) >= 3:
        act = sys.argv[1]
        param = sys.argv[2]
        if (act == 'deliver') and (param == 'check'):
            from application.view.deliver import MultiUserDelivery
            print(MultiUserDelivery())
            return 0
        elif (act == 'deliver') and (param == 'now'):
            from application.work.worker import WorkerAllNow
            print(WorkerAllNow())
            return 0
        elif (act == 'db') and (param == 'create'):
            from application.back_end.db_models import create_database_tables
            print(create_database_tables())
            return 0
        elif (act == 'log') and (param == 'purge'):
            from application.view.logs import RemoveLogs
            print(RemoveLogs())
            return 0


    print(f'\nKindleEar Application {appVer}')
    print('\nUsage: main.py commands')
    print('\ncommands:')
    print('  debug        \t    Run the application in debug mode')
    print('  db create    \t    Create database tables')
    print('  deliver check\t    Start delivery if time set is matched')
    print('  deliver now  \t    Force start delivery task')
    print('  log purge    \t    remove logs older than one month')
    print('\n')

if __name__ == "__main__":
    sys.exit(main())
    