#!/usr/bin/env python
# -*- coding:utf-8 -*-
from .tohomhbase import ToHoMHBaseBook

def getBook():
    return Saki

class Saki(ToHoMHBaseBook):
    title               = u'[漫画]天才麻将少女'
    description         = u'《天才麻将少女》，是小林立的麻将漫画作品。SQUARE ENIX的“YOUNG GANGAN”曾于2006年第4期～第6期短期登载，之后由2006年第12期起连载至今。'
    language            = 'zh-cn'
    feed_encoding       = 'utf-8'
    page_encoding       = 'utf-8'
    mastheadfile        = 'mh_default.gif'
    coverfile           = 'cv_bound.jpg'
    feeds               = [(u'[漫画]天才麻将少女', 'https://www.tohomh123.com/tiancaimajiangshaonv/')]
