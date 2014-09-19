#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseFeedBook

def getBook():
    return ArtsAndLettersDaily

class ArtsAndLettersDaily(BaseFeedBook):
    title                 = 'Arts and Letters Daily'
    description           = 'Delivered Daily. Latest article selections on arts, literatures, and other humanity topics. A must-have for all GRE prepers.'
    language              = 'en'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    coverfile             = "cv_aldaily.jpg"
    mastheadfile          = "mh_aldaily.gif"
    oldest_article        = 7
    
    feeds = [
            ('Arts & Letters Daily','http://pipes.yahoo.com/pipes/pipe.run?_id=b268a9d81c3525ef5275eaea242855ad&_render=rss'),
            ]