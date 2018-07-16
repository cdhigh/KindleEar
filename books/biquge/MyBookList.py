#!/usr/bin/env python
# -*- coding:utf-8 -*-

from books.xxbiqugebase import xxbiqugebase


def getBook():
    return MyBookList


class MyBookList(xxbiqugebase):
    title = u'我的书单1'
    description = u'我订阅的所有小说'
    feeds = [(u'修真聊天群', 'https://www.xxbiquge.com/65_65306/'),
             (u'剑徒之路', 'https://www.xxbiquge.com/81_81514/'),
             (u'大王饶命', 'https://www.xxbiquge.com/78_78201/'),
             (u'逆流纯真年代', 'https://www.xxbiquge.com/77_77294/'),
             (u'剑灵同居日记', 'http://www.xxbiquge.com/76_76570/')]
    limit = 100
