#!/usr/bin/env python
# -*- coding:utf-8 -*-
import urlparse
from bs4 import BeautifulSoup
from base import BaseFeedBook, URLOpener

def getBook():
    return Moneydj

class Moneydj(BaseFeedBook):
    title                 = u'MoneyDJ理財網'
    description           = u'理財、財經綜合資訊網，提供全方位的專業財經資訊內容(繁体)'
    language = 'zh-tw'
    feed_encoding = "big5"
    page_encoding = "utf-8"
    mastheadfile = "mh_moneydj.gif"
    coverfile = "cv_moneydj.jpg"
    network_timeout = 30
    
    feeds = [
            (u'最新新聞', 'http://www.moneydj.com/KMDJ/News/NewsSubjectList.aspx?a=X0000000'),
            (u'美國新聞', 'http://www.moneydj.com/KMDJ/News/NewsSubjectList.aspx?a=X0400008'),
            (u'金融相關', 'http://www.moneydj.com/KMDJ/News/NewsSubjectList.aspx?a=X0300016'),
            (u'科技新聞', 'http://www.moneydj.com/KMDJ/News/NewsSubjectList.aspx?a=X0300012'),
            (u'台股新聞', 'http://www.moneydj.com/KMDJ/News/NewsSubjectList.aspx?a=X0200001'),
            (u'港股新聞', 'http://www.moneydj.com/KMDJ/News/NewsSubjectList.aspx?a=X0200002'),
            (u'黃金新聞', 'http://www.moneydj.com/KMDJ/News/NewsSubjectList.aspx?a=X1100000'),
            (u'最新報告', 'http://www.moneydj.com/KMDJ/Report/ReportSubjectList.aspx?a=X0000000'),
            (u'歐盟新聞', 'http://www.moneydj.com/KMDJ/News/NewsSubjectList.aspx?a=X0400003'),
            (u'日本新聞', 'http://www.moneydj.com/KMDJ/NEWS/NEWSSUBJECTLIST.ASPX?A=X0400031'),
            (u'新興市場', 'http://www.moneydj.com/KMDJ/News/NewsSubjectList.aspx?a=X1300006'),
            (u'中國新聞', 'http://www.moneydj.com/KMDJ/News/NewsSubjectList.aspx?a=X0400041'),
           ]
    
    def ParseFeedUrls(self):
        """ return list like [(section,title,url,desc),..] """
        urls = []
        timeout = self.timeout
        opener = URLOpener(self.host, timeout=timeout)
        
        urladded = set()
        for sec,url in self.feeds:
            result = opener.open(url)
            if result.status_code == 200:
                page = result.content.decode('utf-8')
                soup = BeautifulSoup(page)
                tbnews = soup.find(name='div',attrs={'class':['box2']})
                if tbnews:
                    for news in tbnews.find_all('a'):
                        if not news.string or news.string == u'繼續閱讀':
                            continue
                        urlnews = news['href']
                        if not urlnews.startswith('http'):
                            urlnews = urlparse.urljoin(url, urlnews)
                        if urlnews not in urladded:
                            urls.append((sec,news.string,urlnews,None))
                            urladded.add(urlnews)
                soup = None
            else:
                self.log.warn('fetch url failed:%s'%url)
            
        return urls
    