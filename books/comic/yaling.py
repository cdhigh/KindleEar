#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author: insert0003 <https://github.com/insert0003>
from .cartoonmadbase import CartoonMadBaseBook

def getBook():
    return yaling

class yaling(CartoonMadBaseBook):
    title               = u'啞鈴，能舉多少公斤？'
    description         = u' サンドロビッチ•ヤバ子'
    language            = 'zh-tw'
    feed_encoding       = 'big5'
    page_encoding       = 'big5'
    mastheadfile        = 'mh_comic.gif'
    coverfile           = 'cv_yaling.jpg'
    feeds               = [(u'啞鈴，能舉多少公斤？', 'http://www.cartoonmad.com/comic/5195.html')]
