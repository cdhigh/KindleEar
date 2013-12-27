#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseFeedBook

def getBook():
    return Lifeweek

class Lifeweek(BaseFeedBook):
    title                 = u'三联生活周刊'
    description           = u'秉承"倡导品质生活"的理念，提供优质新媒体内容与服务。每周六推送'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    mastheadfile          = "mh_lifeweek.gif"
    coverfile             = "cv_lifeweek.jpg"
    oldest_article        = 0
    deliver_days          = ['Saturday']
    
    feeds = [
            (u'三联生活网', 'http://app.lifeweek.com.cn/?app=rss&controller=index&action=feed'),
           ]
