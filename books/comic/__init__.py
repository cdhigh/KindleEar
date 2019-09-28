#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
自动导入KindleEar漫画书基类
可以继承BaseComicBook类而实现自己的定制漫画书籍。
cdhigh <https://github.com/cdhigh>
"""
import itertools, os
from books.base import BaseComicBook

ComicBaseClasses = []
for comicFile in os.listdir(os.path.dirname(__file__)):
    if comicFile.endswith('base.py') and not comicFile.startswith('__'):
        comicName = os.path.splitext(comicFile)[0]
        try:
            moduleComic = __import__('books.comic.' + comicName, fromlist='*')
            memberList = [getattr(moduleComic, member) for member in dir(moduleComic) if not member.startswith('_')]
            typeofBase = type(BaseComicBook)
            for member in memberList:
                if type(member) == typeofBase and issubclass(member, BaseComicBook) and (member is not BaseComicBook):
                    ComicBaseClasses.append(member)
        except Exception as e:
            default_log.warn("Comic base book '%s' import failed : %s" % (comicName, e))

comic_domains = tuple(itertools.chain(*[x.accept_domains for x in ComicBaseClasses]))

