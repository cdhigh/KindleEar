#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return Hunter

class Hunter(CartoonMadBaseBook):
    title               = u'全职猎人'
    description         = u'日本漫画家富坚义博的一部漫画作品'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_hunter.jpg'
    feeds               = [(u'全职猎人', 'http://www.cartoonmad.com/comic/1155.html')]
