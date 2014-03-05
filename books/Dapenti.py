#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseFeedBook

def getBook():
    return Dapenti

class Dapenti(BaseFeedBook):
    title                 = u'喷嚏图卦'
    description           = u'每天一图卦，让我们更清楚地了解这个世界'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    max_articles_per_feed = 1
    mastheadfile          = "mh_dapenti.gif"
    coverfile             = "cv_dapenti.jpg"
    network_timeout       = 30
    fetch_img_via_ssl     = False
    feeds = [
            (u'喷嚏图卦', 'https://www.dapenti.com/blog/rssfortugua.asp', True),
           ]
