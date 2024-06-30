#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# KindleEar web application entrance
# Visit <https://github.com/cdhigh/KindleEar> for the latest version
# Author: cdhigh <https://github.com/cdhigh>

__Version__ = '3.1.3'

import os, sys, builtins, logging
from application.lib import clogging

appDir = os.path.dirname(os.path.abspath(__file__))

#setup log system
root_log = logging.getLogger() #root
logging.Logger.manager.setLoggerClass(clogging.CalibreLogger)
calibre_log = logging.getLogger('calibre') #campat for calibre
logging.Logger.manager.loggerClass = None #restore
if not root_log.handlers:
    root_log.addHandler(logging.StreamHandler(sys.stdout))
if not calibre_log.handlers:
    calibre_log.addHandler(root_log.handlers[0])

builtins.__dict__['default_log'] = calibre_log
builtins.__dict__['appDir'] = appDir
builtins.__dict__['appVer'] = __Version__
sys.path.insert(0, os.path.join(appDir, 'application', 'lib'))

#合并config.py配置信息到os.environ，如果对应环境变量存在，则不会覆盖
def set_env():
    import config
    cfgMap = {}
    keys = ['APP_ID', 'APP_DOMAIN', 'SERVER_LOCATION', 'DATABASE_URL', 'TASK_QUEUE_SERVICE',
        'TASK_QUEUE_BROKER_URL', 'KE_TEMP_DIR', 'DOWNLOAD_THREAD_NUM', 'ALLOW_SIGNUP',
        'SECRET_KEY', 'DELIVERY_KEY', 'ADMIN_NAME', 'POCKET_CONSUMER_KEY', 'HIDE_MAIL_TO_LOCAL', 
        'LOG_LEVEL', 'EBOOK_SAVE_DIR', 'DICTIONARY_DIR', 'DEMO_MODE']
    for key in keys:
        cfgMap[key] = os.getenv(key) if key in os.environ else getattr(config, key)
        if (key == 'APP_DOMAIN') and not cfgMap[key].startswith('http'):
            cfgMap[key] = 'https://' + cfgMap[key]
        os.environ[key] = cfgMap[key]
    return cfgMap

cfgMap = set_env()

from application import init_app
app = init_app(__name__, cfgMap, set_env, debug=False)
celery_app = app.extensions.get("celery", None)
clogging.set_log_level(cfgMap.get('LOG_LEVEL'))

def main():
    if len(sys.argv) == 2 and sys.argv[1] == 'debug':
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
        elif (act == 'log') and (param == 'purge'):
            from application.view.logs import RemoveLogs
            print(RemoveLogs())
            return 0


    print(f'\nKindleEar Application {appVer}')
    print('\nUsage: main.py commands')
    print('\ncommands:')
    print('  debug        \t    Run the application in debug mode')
    print('  deliver check\t    Start delivery if time set is matched')
    print('  deliver now  \t    Force start delivery task')
    print('  log purge    \t    remove logs older than one month')
    print('\n')

if __name__ == "__main__":
    sys.exit(main())
