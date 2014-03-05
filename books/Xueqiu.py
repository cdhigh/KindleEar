#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseFeedBook

def getBook():
    return Xueqiu

class Xueqiu(BaseFeedBook):
    title                 = u'雪球今日话题'
    description           = u'雪球是一个社交投资网络，「今日话题」是雪球用户每日发布的投资交流精选。'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    mastheadfile          = "mh_ftchinese.gif"
    coverfile             = "cv_ftchinese.jpg"
    oldest_article        = 1
    
    feeds = [
            (u'今日话题', 'http://xueqiu.com/hots/topic/rss'),
            ]
    
    def fetcharticle(self, url, decoder):
        return BaseFeedBook.fetcharticle(self, url, decoder)
        
