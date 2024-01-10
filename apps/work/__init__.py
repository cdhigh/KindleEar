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

'''import os

#def LoadWorker():
for works in os.listdir(os.path.dirname(__file__)):
    if works.endswith('.py') and not works.startswith('__'):
        workname = os.path.splitext(works)[0]
        try:
            mwork = __import__("apps.Work." + workname, fromlist='*')
            #bk = mbook.getBook()
            #globals()[bk.__name__] = getattr(bk, bk.__name__)
            #RegisterBook(bk)
        except Exception as e:
            default_log.warn("Worker '%s' import failed : %s" % (workname,e))

#LoadWorker()'''