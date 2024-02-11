#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""For KindleEar configuration, the first several variables need to be modified.
If some configurations need to be obtained through environment variables,
you can use the form os.environ['name'] (import os firstly)

KindleEar配置文件，请务必修改开始几个配置
如果有的配置是从环境变量获取，也可以使用os.envrion['name']方式。（在开头增加一行: import os）
"""
APP_ID = "kindleear"
SRC_EMAIL = "akindleear@gmail.com"  #Your gmail account for sending mail to Kindle
KE_DOMAIN = "https://kindleear.appspot.com" #Your domain of app

#Need for google taskqueue, Refers to <https://cloud.google.com/appengine/docs/locations>
#Find it at Upper right corner of <https://console.cloud.google.com/appengine?project=your_app_id>
SERVER_LOCATION = "us-central1"

#Choose the database engine, you can also set Database URL to DATABASE_NAME
DATABASE_ENGINE = "sqlite"  #"datastore", "mysql", "sqlite", "postgresql", "cockroachdb", "mongodb"
DATABASE_NAME = "test.db"
DATABASE_HOST = "localhost"
DATABASE_PORT = 0
DATABASE_USERNAME = ""
DATABASE_PASSWORD = ""

#If you need to use google appengine email receiving service, please set it to True
USE_GAE_INBOUND_EMAIL = False

#Select the type of task queue, "gae", "celery", "cron"
TASK_QUEUE_SERVICE = "celery"

#If task queue service is celery
CELERY_BROKER_URL = "redis://127.0.0.1:6379/"
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/"

#If this option is empty, temporary files will be stored in memory
#Setting this option can reduce memory consumption, supports both relative and absolute paths
TEMP_DIR = 'd:/temp'

#If the depolyment plataform supports multi-threads, set this option will boost the download speed
DOWNLOAD_THREAD_NUM = 1

#------------------------------------------------------------------------------------
#Configurations below this line generally do not need to be modified
#------------------------------------------------------------------------------------

#The administrator's login name
ADMIN_NAME = "admin"

TIMEZONE = 8  #Default timezone, you can modify it in webpage after deployed

#You can use this public key or apply for your own key
POCKET_CONSUMER_KEY = '50188-e221424f1c9ed0c010058aef'
