#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return FairyTail

class FairyTail(CartoonMadBaseBook):
    title               = u'[漫画]妖精的尾巴'
    description         = u'日本漫画家真岛浩创作的少年漫画'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_default.gif'
    coverfile           = 'cv_bound.jpg'
    feeds               = [(u'[漫画]妖精的尾巴', 'http://www.cartoonmad.com/comic/1153.html')]
