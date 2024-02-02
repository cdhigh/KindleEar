#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# KindleEar web application entrance
# Visit <https://github.com/cdhigh/KindleEar> for the latest version
# Author: cdhigh <https://github.com/cdhigh>
import os, sys, builtins, logging

__Version__ = '3.0.0'

appDir = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger()
log.setLevel(logging.WARN) #logging.DEBUG
builtins.__dict__['default_log'] = log
builtins.__dict__['appDir'] = appDir
builtins.__dict__['appVersion'] = __Version__
sys.path.insert(0, os.path.join(appDir, 'application/lib'))

from application import init_app
app = init_app(debug=False)

#调试目的
if __name__ == "__main__":
    from config import APP_ID
    os.environ['DATASTORE_DATASET'] = APP_ID
    os.environ['DATASTORE_EMULATOR_HOST'] = 'localhost:8081'
    os.environ['DATASTORE_EMULATOR_HOST_PATH'] = 'localhost:8081/datastore'
    os.environ['DATASTORE_HOST'] = 'http://localhost:8081'
    os.environ['DATASTORE_PROJECT_ID'] = APP_ID
    #cmd to start datastore emulator: gcloud beta emulators datastore start
    default_log.setLevel(logging.DEBUG)
    app.run(host='0.0.0.0', debug=False)
