#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseComicBook

def getBook():
    return Prison

class Prison(BaseComicBook):
    title               = u'监狱学园'
    description         = u'日本漫画家Akira创作的少年漫画'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_prison.jpg'
    mainurl             = 'http://www.cartoonmad.com/comic/1416.html'
