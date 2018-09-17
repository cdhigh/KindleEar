#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseFeedBook

def getBook():
    return ZhihuRss

class ZhihuRss(BaseFeedBook):
    title                 = u'知乎每日精选'
    description           = u'知乎官方RSS'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    mastheadfile = "mh_zhihudaily.gif"
    coverfile = "cv_zhihudaily.jpg"
    oldest_article        = 1
    feeds = [
            (u'知乎每日精选', 'https://www.zhihu.com/rss', True)
           ]
# 天国的http://zhihudaily.dev.malash.net/