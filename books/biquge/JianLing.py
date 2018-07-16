#!/usr/bin/env python
# -*- coding:utf-8 -*-

from books.xxbiqugebase import xxbiqugebase


def getBook():
    return JianLing


class JianLing(xxbiqugebase):
    title = u'剑灵同居日记'
    description = u'国王陛下'
    feeds = [(u'剑灵同居日记', 'http://www.xxbiquge.com/76_76570/')]
