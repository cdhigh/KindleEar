#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return Yuna

class Yuna(CartoonMadBaseBook):
    title               = u'[漫画]摇曳庄的幽奈小姐'
    description         = u'三浦忠弘（ミウラタダヒロ）创作，2016年2月8日开始连载于《周刊少年JUMP》上的漫画'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_default.gif'
    coverfile           = 'cv_bound.jpg'
    feeds               = [(u'[漫画]摇曳庄的幽奈小姐', 'http://www.cartoonmad.com/comic/4897.html')]
