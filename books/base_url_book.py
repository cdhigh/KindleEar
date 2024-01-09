#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
KindleEar电子书基类，每本投递到kindle的书籍抽象为这里的一个类。
可以继承BaseFeedBook类而实现自己的定制书籍。
cdhigh <https://github.com/cdhigh>
"""
from books.base_book import *

#提供网页URL，而不是RSS订阅地址，
#此类生成的MOBI使用普通书籍格式，而不是期刊杂志格式
#feeds中的地址为网页的URL，section可以为空。
class BaseUrlBook(BaseFeedBook):
    fulltext_by_readability = True

    def ParseFeedUrls(self):
        return [ItemRssTuple(sec, sec, url, '') for sec, url in self.feeds]
