#!/usr/bin/env python
# -*- coding:utf-8 -*-
# https://www.xxbiquge.com 的基类
import datetime
from bs4 import BeautifulSoup
from config import TIMEZONE
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseUrlBook
from apps.dbModels import LastDelivered


class xxbiqugebase(BaseUrlBook):
    """
    子类重写这三个属性
    """
    title = u''
    description = u''
    feeds = []
    language = 'zh-cn'
    feed_encoding = 'utf-8'
    page_encoding = 'utf-8'
    host = 'https://www.xxbiquge.com/'

    def ParseFeedUrls(self):
        urls = []

        newNovelUrls = self.GetNewNovel()
        if not newNovelUrls:
            return []
        for title, chapterTitle, num, url in newNovelUrls:
            urls.append((title, chapterTitle, url, ''))
            self.UpdateLastDelivered(title, num, chapterTitle)
        return urls

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

    def GetNewNovel(self):
        urls = []

        userName = self.UserName()
        decoder = AutoDecoder(isfeed=False)

        for title, url in self.feeds:
            lastCount = LastDelivered.all().filter('username = ', userName).filter("bookname = ", title).get()
            if not lastCount:
                oldNum = 0
            else:
                oldNum = lastCount.num

            opener = URLOpener(self.host, timeout=60)
            result = opener.open(url)
            if result.status_code != 200:
                self.log.warn('fetch index page for %s failed[%s] : %s' % (
                    title, URLOpener.CodeMap(result.status_code), url))
                continue
            content = result.content
            content = self.AutoDecodeContent(content, decoder, self.feed_encoding, opener.realurl, result.headers)

            soup = BeautifulSoup(content, 'lxml')

            table = soup.find('div', {'id': 'list'}).find_all('a')
            chapterNum = 0
            for chapter in table:
                chapterNum += 1
                if chapterNum > 100:
                    break
                url = chapter.get('href')
                chapterTitle = chapter.text
                num = int(url.split('/')[2].split('.')[0])
                if num > oldNum:
                    oldNum = num
                    urls.append((title, chapterTitle, num, self.urljoin(self.host, url)))

        return urls
