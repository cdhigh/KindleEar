#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseComicBook

def getBook():
    return Tokyo

class Tokyo(BaseComicBook):
    title               = u'东京食尸鬼re'
    description         = u'日本漫画家石田翠作画的漫画，是前作《东京食尸鬼》的第二部'
    coverfile           = 'cv_tokyo.jpg'
    mainurl             = 'http://www.cartoonmad.com/comic/4270.html'
