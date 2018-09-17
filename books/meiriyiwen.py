#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseFeedBook

def getBook():
    return meiriyiwen

class meiriyiwen(BaseFeedBook):
    title                 = u'每日一文'
    description           = u'每日一文山寨全文RSS订阅'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    mastheadfile = "mh_default.gif"
    coverfile = "cv_default.jpg"
    oldest_article        = 1
    feeds = [
            (u'每日一文', 'http://www.feed43.com/meiriyiwen.xml', True)
           ]