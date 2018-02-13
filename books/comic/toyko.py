#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return Tokyo

class Tokyo(CartoonMadBaseBook):
    title               = u'[漫画]东京食尸鬼re'
    description         = u'日本漫画家石田翠作画的漫画，是前作《东京食尸鬼》的第二部'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_default.gif'
    coverfile           = 'cv_bound.jpg'
    feeds               = [(u'[漫画]东京食尸鬼re', 'http://www.cartoonmad.com/comic/4270.html')]
