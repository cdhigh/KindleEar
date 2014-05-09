#!/usr/bin/env python
# -*- coding:utf-8 -*-

__all__ = []

import pkgutil
import inspect

#import main

#Load all class with __url__ attribute in the directory

for loader, name, is_pkg in pkgutil.walk_packages(__path__):
    module = loader.find_module(name).load_module(name)

    for name, value in inspect.getmembers(module):
        if name.startswith('__') or not inspect.isclass(value):
            continue
        url=getattr(value,'__url__',None)
        if not url:
            continue
        globals()[name] = value
        __all__.append(name)
        #main.log.info('debug: %s loaded'%name)

        try:
            main.urls += [url,name]
        except AttributeError:
            main.urls = []
            main.log.info('First: %s loaded'%name)
            main.urls += [url,name]
'''
import os

__all__ = []

#def LoadViews():
for views in os.listdir(os.path.dirname(__file__)):
    if views.endswith('.py') and not views.startswith('__'):
        viewname = os.path.splitext(views)[0]
        __all__.append(viewname)
        try:
            mview = __import__("apps.View." + viewname, fromlist='*')
            #bk = mbook.getBook()
            #globals()[bk.__name__] = getattr(bk, bk.__name__)
            #RegisterBook(bk)
        except Exception as e:
            default_log.warn("View '%s' import failed : %s" % (viewname,e))

#LoadViews()'''