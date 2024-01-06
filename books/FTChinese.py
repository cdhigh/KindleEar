#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from books.base_book import BaseFeedBook

def getBook():
    return FTChinese

class FTChinese(BaseFeedBook):
    title                 = 'FT中文网'
    description           = '英国《金融时报》集团旗下唯一的中文商业财经网站。'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    masthead_file         = "mh_ftchinese.gif"
    cover_file            = "cv_ftchinese.jpg"
    oldest_article        = 1
    
    feeds = [
            ('每日新闻', 'http://www.ftchinese.com/rss/feed'),
            ]
    
    def FetchArticle(self, url, opener):
        #每个URL都增加一个后缀full=y，如果有分页则自动获取全部分页
        url += '?full=y'
        return super().FetchArticle(url, opener)
        