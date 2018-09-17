#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return migi

class migi(CartoonMadBaseBook):
    title               = u'基米與達利'
    description         = u' 佐野菜見'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_migi.jpg'
    feeds               = [(u'基米與達利', 'http://www.cartoonmad.com/comic/6197.html')]
