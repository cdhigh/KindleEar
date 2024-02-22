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
APP_DOMAIN = "https://kindleear.appspot.com"  #Your domain of app

#Need for google taskqueue only, Refers to <https://cloud.google.com/appengine/docs/locations>
#Find it at Upper right corner of <https://console.cloud.google.com/appengine?project=your_app_id>
SERVER_LOCATION = "us-central1"

#Choose the database engine, you can also set Database URL to DATABASE_NAME
#Supports: "datastore", "sqlite", "mysql", "postgresql", "cockroachdb", "mongodb", "redis"
DATABASE_ENGINE = "redis"
DATABASE_NAME = "test.db"  # or "mongodb://localhost:27017/", for redis it is db number
DATABASE_HOST = "127.0.0.1"
DATABASE_PORT = 6379
DATABASE_USERNAME = ""
DATABASE_PASSWORD = ""

#Email receiving service, "gae" | ""
INBOUND_EMAIL_SERVICE = ""

#Select the type of task queue, "gae" | "apscheduler" | "celery" | "rq"
TASK_QUEUE_SERVICE = "apscheduler"

#If task queue service is celery | rq
TASK_QUEUE_BROKER_URL = "redis://127.0.0.1:6379/"
TASK_QUEUE_RESULT_BACKEND = "redis://127.0.0.1:6379/"

#If this option is empty, temporary files will be stored in memory
#Setting this option can reduce memory consumption, supports both relative and absolute paths
TEMP_DIR = ""

#If the depolyment plataform supports multi-threads, set this option will boost the download speed
DOWNLOAD_THREAD_NUM = 1

#If the website allow visitors to signup or not
ALLOW_SIGNUP = True

#------------------------------------------------------------------------------------
#Configurations below this line generally do not need to be modified
#------------------------------------------------------------------------------------

#The administrator's login name
ADMIN_NAME = "admin"

TIMEZONE = 8  #Default timezone, you can modify it in webpage after deployed

#You can use this public key or apply for your own key
POCKET_CONSUMER_KEY = '50188-e221424f1c9ed0c010058aef'
