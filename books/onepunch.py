#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseComicBook

def getBook():
    return OnePunch

class OnePunch(BaseComicBook):
    title               = u'一拳超人'
    description         = u'日本漫画家One创作的少年漫画'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_onepunch.jpg'
    mainurl             = 'http://www.cartoonmad.com/comic/3583.html'
