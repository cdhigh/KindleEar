#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseFeedBook

def getBook():
    return ZhihuDailyRss

class ZhihuDailyRss(BaseFeedBook):
    title                 = u'知乎日报'
    description           = u'知乎日报全文RSS，不需要转发，排版图片正常。'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    mastheadfile = "mh_zhihudaily.gif"
    coverfile = "cv_zhihudaily.jpg"
    oldest_article        = 1
    feeds = [
            (u'知乎日报', 'https://feedx.net/rss/zhihudaily.xml', True)
           ]
# 天国的http://zhihudaily.dev.malash.net/ http://feeds.feedburner.com/zhihu-daily http://feed43.com/feed.html?name=zhihurb