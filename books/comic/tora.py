#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return tora

class tora(CartoonMadBaseBook):
    title               = u'請別叫我軍神醬'
    description         = u' 柳原滿月'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_tora.jpg'
    feeds               = [(u'不要叫我军神酱', 'http://www.cartoonmad.com/comic/5446.html')]
