#!/usr/bin/env python
# -*- coding:utf-8 -*-

from books.xxbiqugebase import xxbiqugebase


def getBook():
    return DaWang


class DaWang(xxbiqugebase):
    title = u'大王饶命'
    description = u'肘子'
    feeds = [(u'大王饶命', 'https://www.xxbiquge.com/78_78201/')]
