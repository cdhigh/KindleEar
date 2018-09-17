#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return terror

class terror(CartoonMadBaseBook):
    title               = u'恐怖之夜'
    description         = u' 月見隆士'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_terror.jpg'
    feeds               = [(u'恐怖之夜', 'http://www.cartoonmad.com/comic/5589.html')]
