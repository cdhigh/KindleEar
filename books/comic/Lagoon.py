#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return Lagoon

class Lagoon(CartoonMadBaseBook):
    title               = u'[漫画]LetsLagoon'
    description         = u'日本漫画家创作的漫画'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_default.gif'
    coverfile           = 'cv_bound.jpg'
    feeds               = [(u'[漫画]LetsLagoon', 'http://www.cartoonmad.com/comic/1473.html')]
