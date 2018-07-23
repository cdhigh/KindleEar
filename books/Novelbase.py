#!/usr/bin/env python
# -*- coding:utf-8 -*-
# https://www.xxbiquge.com 的基类
# Author: skiinder <https://github.com/skiinder>
import datetime
from bs4 import BeautifulSoup
from config import TIMEZONE
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseUrlBook
from apps.dbModels import LastDelivered
from apps.utils import str_to_int

class Novelbase(BaseUrlBook):
    # 子类重写这四个属性
    title = u''
    description = u''
    feeds = ''
    host = ''

    language = 'zh-cn'
    feed_encoding = 'utf-8'
    page_encoding = 'utf-8'

    # URL中章节序号的索引，以‘/’分割，从0开始
    # 如果不能简单通过序号获取，请重写GetChapterNum方法
    indexChapterInUrl = 0

    # 章节列表的标签名和标签属性
    # 目前tag和tagAttr的值代表章节列表的标签为<div id="readerlist">
    # 如果章节列表属性不唯一或者无法简单解析，请重写GetChapterList方法
    tag = 'div'
    tagAttr = {'id': 'readerlist'}

    # 单本书章节限制
    limit = 100

    def ParseFeedUrls(self):
        urls = []
        userName = self.UserName()
        decoder = AutoDecoder(isfeed=False)

        lastCount = LastDelivered.all().filter('username = ', userName).filter("bookname = ", self.title).get()
        if not lastCount:
            oldNum = 0
            oldChapterTitle = ''
        else:
            oldNum = lastCount.num
            oldChapterTitle = lastCount.record

        opener = URLOpener(self.host, timeout=60)
        result = opener.open(self.feeds)
        if result.status_code != 200:
            self.log.warn('fetch index page for %s failed[%s] : %s' % (
                self.title, URLOpener.CodeMap(result.status_code), self.feeds))
            return []

        # 从页面获取章节列表
        content = self.AutoDecodeContent(result.content, decoder, self.feed_encoding, opener.realurl, result.headers)
        soup = BeautifulSoup(content, 'lxml')
        chapterList = self.GetChapterList(soup)

        chapterNum = 0
        for chapter in chapterList:
            if chapterNum >= self.limit:
                break
            url = chapter.get('href')
            num = self.GetChapterNum(url)
            if num > oldNum:
                oldNum = num
                oldChapterTitle = chapter.text
                chapterNum += 1
                urls.append((self.title, oldChapterTitle, self.urljoin(self.host, url), ''))

        self.UpdateLastDelivered(self.title, oldNum, oldChapterTitle)
        return urls

    # 获取章节列表
    # 如果简单的属性定义不能获取章节列表，请重写此方法
    def GetChapterList(self, soup):
        return soup.find(self.tag, self.tagAttr).find_all('a')

    # 获取章节序号
    # 如果简单的属性定义不能获取章节序号，请重写此方法
    def GetChapterNum(self, url):
        return str_to_int(url.split('/')[self.indexChapterInUrl].split('.')[0])

    def UpdateLastDelivered(self, title, num, chapter):
        userName = self.UserName()
        dbItem = LastDelivered.all().filter('username = ', userName).filter('bookname = ', title).get()
        if dbItem:
            dbItem.num = num
            dbItem.record = chapter
            dbItem.datetime = datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE)
        else:
            dbItem = LastDelivered(username=userName, bookname=title, num=num, record=chapter,
                                   datetime=datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE))
        dbItem.put()


class xxbiqugebase(Novelbase):
    host = 'https://www.xxbiquge.com/'
    tag = 'div'
    tagAttr = {'id': 'list'}
    indexChapterInUrl = 2


class cn3k5(Novelbase):
    feed_encoding = 'gbk'
    page_encoding = 'gbk'
    host = 'http://www.cn3k5.com/'
    tag = 'div'
    tagAttr = {'id': 'readerlist'}
    indexChapterInUrl = 3
