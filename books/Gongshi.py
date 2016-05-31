#!/usr/bin/env python
# -*- coding:utf-8 -*-

from bs4 import BeautifulSoup
from base import BaseFeedBook, URLOpener


def getBook():
    return Gongshi


class Gongshi(BaseFeedBook):
    title               = u'共识网一周排行'
    description         = u'共识网—在大变革时代寻找共识 | 每周六推送。'
    language            = 'zh-cn'
    feed_encoding       = "gbk"
    page_encoding       = "gbk"
    mastheadfile        = "mh_gongshi.gif"
    coverfile           = 'cv_gongshi.jpg'
    deliver_days        = ['Saturday']

    def FetchDesc(self, url):
        opener = URLOpener(self.host, timeout=60)
        result = opener.open(url)
        if result.status_code != 200:
            self.log.warn('fetch article failed(%d):%s.' % (status_code, url))
            return None
        content = result.content.decode(self.feed_encoding)
        soup = BeautifulSoup(content, 'lxml')
        abstract = unicode(soup.find('div', attrs={'class': 'zhaiyao'}))
        article = unicode(soup.find(id='contents'))
        pagelist = soup.find('ul', attrs={'class': 'pagelist'})
        if pagelist and pagelist.find('li'):
            page_count_context = pagelist.a.text
            page_count = int(
                page_count_context[1:page_count_context.index(u'页')])
            for i in range(2, page_count + 1):
                page_url = url[:-5] + "_%d.html" % i
                result = opener.open(page_url)
                if result.status_code != 200:
                    self.log.warn(
                        'fetch page failed(%d):%s.' % (status_code, page_url))
                    return None
                content = result.content.decode(self.feed_encoding)
                pagesoup = BeautifulSoup(content, 'lxml')
                article += unicode(pagesoup.find(id='contents'))
        return abstract + article

    def ParseFeedUrls(self):
        mainurl = "http://www.21ccom.net/articles/china/"
        urls = []
        opener = URLOpener(self.host, timeout=60)
        result = opener.open(mainurl)
        if result.status_code != 200:
            self.log.warn('fetch rss failed:%s' % mainurl)
            return []
        content = result.content.decode(self.feed_encoding)
        soup = BeautifulSoup(content, "lxml")
        # Get the 2nd block
        ul = soup.find_all('ul', attrs={'class': ['m-list', 'list-tweet']})[1]
        for li in ul.find_all('li'):
            urls.append(
                (u'共识网一周排行', li.a.text, li.a['href'], self.FetchDesc(li.a['href'])))
        return urls
