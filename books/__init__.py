#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os

_booksclasses = []
def RegisterBook(book):
    if book.title:
        _booksclasses.append(book)

def BookClasses():
    return _booksclasses

def BookClass(title):
    for bk in _booksclasses:
        if bk.title == title:
            return bk
    return None

def LoadBooks():
    for bkfile in os.listdir(os.path.dirname(__file__)):
        if bkfile.endswith('.py') and not bkfile.startswith('__') and not bkfile.endswith("base.py"):
            bookname = os.path.splitext(bkfile)[0]
            mbook = __import__("books." + bookname, fromlist='*')
            bk = mbook.getBook()
            #globals()[bk.__name__] = getattr(bk, bk.__name__)
            RegisterBook(bk)

LoadBooks()
