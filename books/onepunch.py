#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseComicBook

def getBook():
    return OnePunch

class OnePunch(BaseComicBook):
    title               = u'一拳超人'
    description         = u'日本漫画家One创作的少年漫画'
    coverfile           = 'cv_onepunch.jpg'
    mainurl             = 'http://www.cartoonmad.com/comic/3583.html'
