#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# KindleEar configuration.
# All configuration variables in this file can be set via environment variables too.
# Values from this file are only used if the environment variables are not present.
#
# 这个文件里面的所有配置变量都可以通过环境变量来设置。
# 程序会优先使用环境变量，只有环境变量不存在时才使用此文件中的数值。
#

APP_ID = "kindleear"
APP_DOMAIN = "https://kindleear.appspot.com"

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
DATABASE_URL = "sqlite:////data/kindleear.db"

#Select the type of task queue, "gae", "apscheduler", "celery", "rq", ""
TASK_QUEUE_SERVICE = "apscheduler"

#If task queue service is apscheduler, celery, rq
#Options: 'redis://', 'mongodb://', 'sqlite://', 'mysql://', 'postgresql://'
#For apscheduler, it can be 'memory'. (Only if gunicorn have one worker)
#For rq, only 'redis://' is supported
#TASK_QUEUE_BROKER_URL = "redis://127.0.0.1:6379/"
TASK_QUEUE_BROKER_URL = "memory"

#If this option is empty, temporary files will be stored in memory
#Setting this option can reduce memory consumption, supports both relative and absolute paths
KE_TEMP_DIR = "/tmp"

#If online reading is required, this directory is used to store the generated e-books.
EBOOK_SAVE_DIR = ""

#Offline dictionaries for online reading
DICTIONARY_DIR = ""

#If the depolyment plataform supports multi-threads, set this option will boost the download speed
DOWNLOAD_THREAD_NUM = "3"

#If the website allow visitors to signup or not, "yes"|"no"
ALLOW_SIGNUP = "no"

#The secret key for browser session.
SECRET_KEY = "n7ro8QJI1qfe"

#The secret key for starting delivery
DELIVERY_KEY = "cY9gKC"

#The administrator's login name
ADMIN_NAME = "admin"

#You can use this public key or apply for your own key
POCKET_CONSUMER_KEY = "50188-e221424f1c9ed0c010058aef"

#Hide the option 'local (debug)' of 'Send Mail Service' setting or not, "yes"|"no"
HIDE_MAIL_TO_LOCAL = "yes"

#'debug', 'info', 'warning', 'error', 'critical'
LOG_LEVEL = "warning"

#if in demo mode
DEMO_MODE = 'no'
