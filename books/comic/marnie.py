#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return marnie

class marnie(CartoonMadBaseBook):
    title               = u'名偵探瑪尼'
    description         = u'木木津克久'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_marnie.jpg'
    feeds               = [(u'名偵探瑪尼', 'http://www.cartoonmad.com/comic/3947.html')]
