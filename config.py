#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""Configures for KindleEar, the First some variable is must to modify.
KindleEar配置文件，请务必修改开始几个配置
如果有的配置是从环境变量获取，也可以使用os.envrion['name']方式
"""

SRC_EMAIL = "akindleear@gmail.com"  #Your gmail account for sending mail to Kindle
KE_DOMAIN = "https://kindleear.appspot.com" #Your domain of app
#Need for taskqueue, Refers to <https://cloud.google.com/appengine/docs/locations>
#Upper right corner at <https://console.cloud.google.com/appengine?project=your_app_id>
APP_ID = "kindleear"
SERVER_LOCATION = "us-central1"

#Choose the database engine, you can also set Database URL to DATABASE_NAME
DATABASE_ENGINE = "sqlite"  #"datastore", "mysql", "sqlite", "postgresql", "cockroachdb"
DATABASE_NAME = "test.db"
DATABASE_HOST = "localhost"
DATABASE_PORT = 0
DATABASE_USERNAME = ""
DATABASE_PASSWORD = ""

#Choose the backend service for sending emails, either "gae", "sendgrid", "smtp"
SEND_MAIL_SERVICE = "gae"

#If SEND_MAIL_SERVICE is configured as sendgrid, these properties need to be set correctly
#SENDGRID_APIKEY = ""

#If SEND_MAIL_SERVICE is configured as smtp, these properties need to be set correctly
#SMTP_HOST = "smtp.gmail.com"
#SMTP_HOST_USER = "your_name@gmail.com"
#SMTP_HOST_PASSWORD = "password"
#SMTP_PORT = 587
#SMTP_USE_TLS = True

#If you need to use google appengine email receiving service, please set it to True
USE_GAE_INBOUND_EMAIL = True

#Select the type of task queue, "gae", "celery", "cron"
TASK_QUEUE_TYPE = "gae"

#If this option is empty, temporary files will be stored in memory
#Setting this option can reduce memory consumption and supports both relative and absolute paths
TEMP_DIR = ''

#If the depolyment plataform supports multi threads, set this option will boost the download speed
DOWNLOAD_THREAD_NUM = 1

TIMEZONE = 8  #Default timezone, you can modify it in webpage after deployed

#------------------------------------------------------------------------------------
#Configurations below this line generally do not need to be modified
#------------------------------------------------------------------------------------

#The administrator's login name
ADMIN_NAME = "admin"

DEFAULT_MASTHEAD = "mh_default.gif" #default masthead
DEFAULT_COVER = "cv_default.jpg" #default cover, leave it empty will not add cover to book
DEFAULT_COVER_BV = DEFAULT_COVER #default cover for merged-book, None indicates paste all covers into one, =DEFAULT_COVER enable the using of uploaded image.

#generate brief description for toc item or not.
GENERATE_TOC_DESC = True
TOC_DESC_WORD_LIMIT = 500

#if convert color image to gray or not, good for reducing size of book if you read it in Kindle only
COLOR_TO_GRAY = True

#Split long image(height of image is bigger than some value) to multiple images or not?
#This feature is disabled if it be set to None or 0.
THRESHOLD_SPLIT_LONG_IMAGE = 750

#reduce dimension of image to (Width,Height)
#or you can set it to None, and choose device type in webpage 'setting'
REDUCE_IMAGE_TO = None #(600,800)

#text for link to share or archive
SAVE_TO_EVERNOTE = "Save to Evernote"
SAVE_TO_WIZ = "Save to Wiz"
SAVE_TO_POCKET = "Save to Pocket"
SAVE_TO_INSTAPAPER = "Save to Instapaper"
SHARE_ON_XWEIBO = "Share on Sina Weibo"
SHARE_ON_TWEIBO = "Share on Tencent Weibo"
SHARE_ON_FACEBOOK = "Share on Facebook"
SHARE_ON_TWITTER = "X (Tweet) it"
SHARE_ON_TUMBLR = "Share on Tumblr"
OPEN_IN_BROWSER = "Open in Browser"

POCKET_CONSUMER_KEY = '50188-e221424f1c9ed0c010058aef'

