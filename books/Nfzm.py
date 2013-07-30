#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseFeedBook

def getBook():
    return Nanfangzhoumo

class Nanfangzhoumo(BaseFeedBook):
    title                 = u'南方周末'
    description           = u'在这里，读懂中国。 每周五推送'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    mastheadfile          = "mh_nfzm.gif"
    coverfile             = "cv_nfzm.jpg"
    deliver_days          = ['Friday',]
    
    feeds = [
            (u'热点新闻', 'http://feeds.feedburner.com/nfzm/hotnews?format=xml'),
           ]
