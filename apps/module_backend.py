#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Author:
# cdhigh <https://github.com/cdhigh>
#Contributors:
# rexdf <https://github.com/rexdf>

__Author__ = "cdhigh"

import os, datetime, logging, __builtin__, hashlib, time

# for debug
# 本地启动调试服务器：python.exe dev_appserver.py c:\kindleear
IsRunInLocal = (os.environ.get('SERVER_SOFTWARE', '').startswith('Development'))
log = logging.getLogger()
__builtin__.__dict__['default_log'] = log
__builtin__.__dict__['IsRunInLocal'] = IsRunInLocal

supported_languages = ['en','zh-cn','tr-tr'] #不支持的语种则使用第一个语言
#gettext.install('lang', 'i18n', unicode=True) #for calibre startup

class Main_Var:
    urls = []
    session = None
    jjenv = None
    supported_languages = None
    log = None
    __Version__ = None

__builtin__.__dict__['main'] = Main_Var
main.supported_languages = supported_languages
main.log = log
main.__Version__ = __Version__
log.setLevel(logging.INFO if IsRunInLocal else logging.WARN)

import web
import jinja2
from google.appengine.api import memcache

from lib.memcachestore import MemcacheStore

from apps.Work import *

from apps.utils import fix_filesizeformat

application = web.application(main.urls, globals())
store = MemcacheStore(memcache)
session = web.session.Session(application, store, initializer={'username':'', 'login':0, 'lang':'', 'pocket_request_token':''})
jjenv = jinja2.Environment(loader=jinja2.FileSystemLoader('templates'),
                            extensions=["jinja2.ext.do",'jinja2.ext.i18n'])
jjenv.filters['filesizeformat'] = fix_filesizeformat

app = application.wsgifunc()

web.config.debug = IsRunInLocal

main.session = session
main.jjenv = jjenv