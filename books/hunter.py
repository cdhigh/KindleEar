#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseComicBook

def getBook():
    return Hunter

class Hunter(BaseComicBook):
    title               = u'全职猎人'
    description         = u'日本漫画家富坚义博的一部漫画作品'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_hunter.jpg'
    mainurl             = 'http://www.cartoonmad.com/comic/1155.html'
