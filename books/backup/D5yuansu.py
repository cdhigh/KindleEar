#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseFeedBook

def getBook():
    return D5yuansu

class D5yuansu(BaseFeedBook):
    title                 = u'D5大生活'
    description           = u'宇宙很大，生活更大'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    oldest_article        = 1
    mastheadfile          = "mh_d5yuansu.gif"
    coverfile             = "cv_d5yuansu.jpg"
    network_timeout       = 60
    feeds = [
            (u'D5大生活', 'http://d5ys.net/feed/', True),
           ]
    