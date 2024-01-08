#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from books.base_book import BaseFeedBook

def getBook():
    return Dapenti

class Dapenti(BaseFeedBook):
    title                 = '喷嚏图卦'
    description           = '每天一图卦，让我们更清楚地了解这个世界'
    language              = 'zh-cn'
    max_articles_per_feed = 1
    oldest_article        = 2
    masthead_file         = "mh_dapenti.gif"
    cover_file            = "cv_dapenti.jpg"
    fetch_img_via_ssl     = False
    feeds = [
            ('喷嚏图卦', 'https://feedx.net/rss/pentitugua.xml', True),
           ]
    
    # def ProcessBeforeImage(self, soup):
    #     # 更换另一个图库，因为RSS中的图库已经被封
    #     for img in soup.find_all('img', attrs={'src': True}):
    #         if img['src'].startswith('http://ptimg.org:88'):
    #             img['src'] = img['src'].replace('http://ptimg.org:88', 'http://pic.yupoo.com')
