#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return GiantBefore

class GiantBefore(CartoonMadBaseBook):
    title               = u'[漫画]进击的巨人BeforeTheFall'
    description         = u'諫山創'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_default.gif'
    coverfile           = 'cv_bound.jpg'
    feeds               = [(u'[漫画]进击的巨人BeforeTheFall', 'http://www.cartoonmad.com/comic/3413.html')]
