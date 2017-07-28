#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseComicBook

def getBook():
    return MyHero

class MyHero(BaseComicBook):
    title               = u'我的英雄学院'
    description         = u'日本漫画家堀越耕平创作的少年漫画'
    coverfile           = 'cv_myhero.jpg'
    mainurl             = 'http://www.cartoonmad.com/comic/4085.html'
