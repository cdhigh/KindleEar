#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return mochi

class mochi(CartoonMadBaseBook):
    title               = u' 魔女的僕人和魔王的角'
    description         = u'MOCHI创作的有点乱的漫画'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_mochi.jpg'
    feeds               = [(u' 魔女的僕人和魔王的角', 'http://www.cartoonmad.com/comic/3930.html')]
