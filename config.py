#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""For KindleEar configuration, the first several variables need to be modified.
If some configurations need to be obtained through environment variables,
you can use the form os.environ['name']
"""
import os

APP_ID = os.getenv("APP_ID") or "kindleear"
APP_DOMAIN = os.getenv("APP_DOMAIN") or "https://kindleear.appspot.com"

#Need for google taskqueue only, Refers to <https://cloud.google.com/appengine/docs/locations>
#Find it at Upper right corner of <https://console.cloud.google.com/appengine?project=your_app_id>
#Or get by cmd: gcloud beta app describe
#Two exceptions: europe-west should be europe-west1, us-central should be us-central1
SERVER_LOCATION = "us-central1"

#Choose the database
#Supports: "datastore", "sqlite", "mysql", "postgresql", "cockroachdb", "mongodb", "redis", "pickle"
#DATABASE_URL = "mongodb://127.0.0.1:27017/"
#DATABASE_URL = 'sqlite:////home/ubuntu/site/kindleear/database.db'
#DATABASE_URL = 'sqlite:///database.db'
DATABASE_URL = os.getenv('DATABASE_URL') or 'datastore'

#Email receiving service, "gae", ""
INBOUND_EMAIL_SERVICE = ""

#Select the type of task queue, "gae", "apscheduler", "celery", "rq", ""
TASK_QUEUE_SERVICE = os.getenv('TASK_QUEUE_SERVICE') or "apscheduler"

#If task queue service is apscheduler, celery, rq
#Options: 'redis://', 'mongodb://', 'sqlite://', 'mysql://', 'postgresql://'
#For apscheduler, it can be a empty str '' if a memory store is used
#For rq, only 'redis://' is supported
TASK_QUEUE_BROKER_URL = os.getenv('TASK_QUEUE_BROKER_URL') or "redis://127.0.0.1:6379/"
#TASK_QUEUE_BROKER_URL = ''

#If this option is empty, temporary files will be stored in memory
#Setting this option can reduce memory consumption, supports both relative and absolute paths
TEMP_DIR = "/tmp" if os.getenv("TEMP_DIR") is None else os.getenv("TEMP_DIR")

#If the depolyment plataform supports multi-threads, set this option will boost the download speed
DOWNLOAD_THREAD_NUM = 1

#If the website allow visitors to signup or not
ALLOW_SIGNUP = False

#For security reasons, it's suggested to change the secret key.
SECRET_KEY = "n7ro8QJI1qfe"

#------------------------------------------------------------------------------------
#Configurations below this line generally do not need to be modified
#------------------------------------------------------------------------------------

#The administrator's login name
ADMIN_NAME = "admin"

#You can use this public key or apply for your own key
POCKET_CONSUMER_KEY = "50188-e221424f1c9ed0c010058aef"

#Hide the option 'local (debug)' of 'Send Mail Service' setting or not
HIDE_MAIL_TO_LOCAL = False
