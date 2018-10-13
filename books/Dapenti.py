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
    oldest_article        = 2
    mastheadfile          = "mh_dapenti.gif"
    coverfile             = "cv_dapenti.jpg"
    network_timeout       = 60
    fetch_img_via_ssl     = False
    feeds = [
            (u'喷嚏图卦', 'https://feedx.net/rss/pentitugua.xml', True),
           ]
    
    # def soupbeforeimage(self, soup):
    #     # 更换另一个图库，因为RSS中的图库已经被封
    #     for img in soup.find_all('img', attrs={'src':True}):
    #         if img['src'].startswith('http://ptimg.org:88'):
    #             img['src'] = img['src'].replace('http://ptimg.org:88','http://pic.yupoo.com')
