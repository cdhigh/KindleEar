#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return jojo

class jojo(CartoonMadBaseBook):
    title               = u'JoJolion'
    description         = u'JOJO第八部 by 荒木飛呂彥'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_jojo.jpg'
    feeds               = [(u'JoJolion', 'http://www.cartoonmad.com/comic/2131.html')]
