#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseComicBook

def getBook():
    return Lagoon

class Lagoon(BaseComicBook):
    title               = u'LetsLagoon'
    description         = u'日本漫画家创作的漫画'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_lagoon.jpg'
    mainurl             = 'http://www.cartoonmad.com/comic/1473.html'
