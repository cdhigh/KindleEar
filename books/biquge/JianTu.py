#!/usr/bin/env python
# -*- coding:utf-8 -*-

from books.xxbiqugebase import xxbiqugebase


def getBook():
    return JianTu


class JianTu(xxbiqugebase):
    title = u'剑徒之路'
    description = u'NULL'
    feeds = [(u'剑徒之路', 'https://www.xxbiquge.com/81_81514/')]
