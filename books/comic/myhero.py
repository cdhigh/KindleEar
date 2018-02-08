#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return MyHero

class MyHero(CartoonMadBaseBook):
    title               = u'[漫画]我的英雄学院'
    description         = u'日本漫画家堀越耕平创作的少年漫画'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_default.gif'
    coverfile           = 'cv_bound.jpg'
    feeds               = [(u'[漫画]我的英雄学院', 'http://www.cartoonmad.com/comic/4085.html')]
