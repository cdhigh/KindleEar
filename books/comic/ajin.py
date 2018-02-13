#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return AJin

class AJin(CartoonMadBaseBook):
    title               = u'[漫画]亚人'
    description         = u'日本漫画家樱井画门创作的漫画'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_default.gif'
    coverfile           = 'cv_bound.jpg'
    feeds               = [(u'[漫画]亚人', 'http://www.cartoonmad.com/comic/3572.html')]
