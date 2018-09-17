#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return nozaki

class nozaki(CartoonMadBaseBook):
    title               = u'月刊少女野崎君漫畫'
    description         = u'椿泉的搞笑漫'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_nozaki.jpg'
    feeds               = [(u'月刊少女野崎君漫畫', 'http://www.cartoonmad.com/comic/2280.html')]
