#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseComicBook

def getBook():
    return FairyTail

class FairyTail(BaseComicBook):
    title               = u'妖精的尾巴'
    description         = u'日本漫画家真岛浩创作的少年漫画'
    coverfile           = 'cv_fairytail.jpg'
    mainurl             = 'http://www.cartoonmad.com/comic/1153.html'
