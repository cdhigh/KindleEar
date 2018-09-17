#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return neverland

class neverland(CartoonMadBaseBook):
    title               = u'約定的夢幻島'
    description         = u'外面的世界好可怕 by 白井カイウ、出水ぽすか'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_never.jpg'
    feeds               = [(u'約定的夢幻島', 'http://www.cartoonmad.com/comic/5187.html')]
