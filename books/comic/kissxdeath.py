#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return KissXDeath

class KissXDeath(CartoonMadBaseBook):
    title               = u'[漫画]KissXDeath'
    description         = u'叶恭弘创作，2014年09月22日新连载在电子漫画周刊《少年Jump+》上的作品'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_default.gif'
    coverfile           = 'cv_bound.jpg'
    feeds               = [(u'[漫画]KissXDeath', 'http://www.cartoonmad.com/comic/4329.html')]