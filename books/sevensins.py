#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseComicBook

def getBook():
    return SevenSins

class SevenSins(BaseComicBook):
    title               = u'七大罪'
    description         = u'日本漫画家铃木央创作的少年漫画'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_sevensins.jpg'
    mainurl             = 'http://www.cartoonmad.com/comic/2504.html'
