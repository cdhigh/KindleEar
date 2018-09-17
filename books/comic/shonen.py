#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return shonen

class shonen(CartoonMadBaseBook):
    title               = u'我的少年'
    description         = u'30歲的OL與12歲的小學生 by 高野一深'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_sn.jpg'
    feeds               = [(u'我的少年', 'http://www.cartoonmad.com/comic/5304.html')]
