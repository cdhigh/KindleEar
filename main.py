#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#KindleEar入口
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Author:
# cdhigh <https://github.com/cdhigh>

__Author__ = "cdhigh"

import os, sys, datetime, logging, builtins, hashlib, time

__Version__ = '3.1'

sys.path.insert(0, 'lib')

# for debug
# 本地启动调试服务器：python.exe dev_appserver.py c:\kindleear
IsRunInLocal = (os.environ.get('SERVER_SOFTWARE', '').startswith('Development'))
log = logging.getLogger()
builtins.__dict__['__Version__'] = __Version__
builtins.__dict__['default_log'] = log
builtins.__dict__['IsRunInLocal'] = IsRunInLocal

supported_languages = ('en', 'zh-cn', 'tr-tr') #不支持的语种则使用第一个语言
builtins.__dict__['supported_languages'] = supported_languages
#gettext.install('lang', 'i18n', unicode=True) #for calibre startup

log.setLevel(logging.INFO if IsRunInLocal else logging.WARN)

from bottle import default_app, route, run, hook
import jinja2
from bottle.ext import beaker

from books import BookClasses

from apps.base_handler import set_session_lang
from apps.view import *

from apps.dbModels import Book
from apps.BaseHandler import BaseHandler

for book in BookClasses():  #添加内置书籍
    if memcache.get(book.title): #使用memcache加速
        continue
    b = Book.all().filter("title = ", book.title).get()
    if not b:
        b = Book(title=book.title, description=book.description, builtin=True, 
            needs_subscription=book.needs_subscription, separate=False)
        b.put()
        memcache.add(book.title, book.description, 86400)

#让jinja2到工程根目录下的templates子目录加载模板
jinja2Env = jinja2.Environment(loader=jinja2.FileSystemLoader('templates'),
                            extensions=["jinja2.ext.do", "jinja2.ext.i18n"])
builtins.__dict__['jinja2Env'] = jinja2Env

#Bottle session configuration
sessionOpts = {
    'session.type': 'file',
    'session.cookie_expires': 300,
    'session.data_dir': '/tmp',  #Cloud 平台只有这个目录是可写的
    'session.auto': True
}

hook.add_hook('before_request', set_session_lang)
app = beaker.middleware.SessionMiddleware(default_app(), sessionOpts) #app为Cloud需要的接口名字

#print(str(os.environ))
#reload(sys)
#sys.setdefaultencoding('utf-8')

@route('/test')
def Test():
    s = ''
    for d in os.environ:
        s += "<pre><p>" + str(d).rjust(28) + " | " + str(os.environ[d]) + "</p></pre>"
    return s

#run(host='localhost', port=8080, debug=True)