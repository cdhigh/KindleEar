#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseComicBook

def getBook():
    return Giant

class Giant(BaseComicBook):
    title               = u'进击的巨人'
    description         = u'諫山創'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_giant.jpg'
    mainurl             = 'http://www.cartoonmad.com/comic/1221.html'
