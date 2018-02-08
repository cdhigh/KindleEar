#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return Conan

class Conan(CartoonMadBaseBook):
    title               = u'[漫画]名侦探柯南'
    description         = u'日本漫画家青山刚昌创作的侦探漫画'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_default.gif'
    coverfile           = 'cv_bound.jpg'
    feeds               = [(u'[漫画]名侦探柯南', 'http://www.cartoonmad.com/comic/1066.html')]
