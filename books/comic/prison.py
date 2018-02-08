#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return Prison

class Prison(CartoonMadBaseBook):
    title               = u'[漫画]监狱学园'
    description         = u'日本漫画家Akira创作的少年漫画'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_default.gif'
    coverfile           = 'cv_bound.jpg'
    feeds               = [(u'[漫画]监狱学园', 'http://www.cartoonmad.com/comic/1416.html')]
