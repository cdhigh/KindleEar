#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return site

class site(CartoonMadBaseBook):
    title               = u'魔法少女site'
    description         = u'魔法少女site第二部'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_site.jpg'
    feeds               = [(u'魔法少女site', 'http://www.cartoonmad.com/comic/7669.html')]
