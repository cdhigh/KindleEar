#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return asobi

class asobi(CartoonMadBaseBook):
    title               = u'來玩遊戲吧'
    description         = u' 涼川りん'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_asobi.jpg'
    feeds               = [(u'來玩遊戲吧', 'http://www.cartoonmad.com/comic/4816.html')]
