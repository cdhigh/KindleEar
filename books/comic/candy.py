#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return candy

class candy(CartoonMadBaseBook):
    title               = u'CANDY & CIGARETTES'
    description         = u'井上智德'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_candy.jpg'
    feeds               = [(u'CANDY & CIGARETTES', 'http://www.cartoonmad.com/comic/6002.html')]
