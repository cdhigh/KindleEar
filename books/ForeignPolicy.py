#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseFeedBook

def getBook():
    return ForeignPolicy

class ForeignPolicy(BaseFeedBook):
    title                 = 'Foreign Policy'
    language              = 'en'
    description           = 'Delivered Daily. Latest global affairs, current events, and US domestic and international policy.'
    publisher             = 'Washingtonpost.Newsweek Interactive, LLC'
    coverfile             = "cv_fp.jpg"
    oldest_article = 7
    auto_cleanup = True
    keep_image = True

    feeds          = [('Foreign Policy','http://www.foreignpolicy.com/node/feed'),]

