#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseComicBook

def getBook():
    return Onepiece

class Onepiece(BaseComicBook):
    title               = u'海贼王'
    description         = u'日本漫画家尾田荣一郎创作的少年漫画'
    coverfile           = 'cv_onepiece.jpg'
    mainurl             = 'http://www.cartoonmad.com/comic/1152.html'
