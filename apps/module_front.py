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
#from google.appengine.api import mail
#from google.appengine.api import taskqueue
from google.appengine.api import memcache

from lib.memcachestore import MemcacheStore
from books import BookClasses

from apps.View import *

from apps.dbModels import Book
from apps.BaseHandler import BaseHandler
from apps.utils import fix_filesizeformat

#reload(sys)
#sys.setdefaultencoding('utf-8')

for book in BookClasses():  #添加内置书籍
    if memcache.get(book.title): #使用memcache加速
        continue
    b = Book.all().filter("title = ", book.title).get()
    if not b:
        b = Book(title=book.title, description=book.description, builtin=True, 
            needs_subscription=book.needs_subscription, separate=False)
        b.put()
        memcache.add(book.title, book.description, 86400)

class Test(BaseHandler):
    def GET(self):
        s = ''
        for d in os.environ:
            s += "<pre><p>" + str(d).rjust(28) + " | " + str(os.environ[d]) + "</p></pre>"
        return s

main.urls += ["/test", "Test",]

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