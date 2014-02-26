#!/usr/bin/env python
# -*- coding:utf-8 -*-
import re, datetime
from bs4 import BeautifulSoup
from lib.urlopener import URLOpener
from base import BaseFeedBook

def getBook():
    return AnBang

class AnBang(BaseFeedBook):
    title                 = u'安邦咨询'
    description           = u'从事宏观经济与战略决策研究的民间智库，不定期更新。'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    mastheadfile          = "mh_anbang.gif"
    coverfile             = "cv_anbang.jpg"
    network_timeout       = 60
    oldest_article        = 1
    feeds = [
            (u'安邦咨询', 'http://www.letscorp.net/archives/category/%E7%BB%8F%E6%B5%8E/anbound'),
           ]

    def ParseFeedUrls(self):
        """ return list like [(section,title,url,desc),..] """
        urls = []
        url = self.feeds[0][1]
        opener = URLOpener(self.host, timeout=self.timeout)
        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn('fetch webpage failed(%d):%s.' % (result.status_code, url))
            return []
            
        if self.feed_encoding:
            try:
                content = result.content.decode(self.feed_encoding)
            except UnicodeDecodeError:
                content = AutoDecoder(False).decode(result.content,opener.realurl)
        else:
            content = AutoDecoder(False).decode(result.content,opener.realurl)
            
        soup = BeautifulSoup(content, 'lxml')
        for article in soup.find_all('div', attrs={'class':'post'}):
            title = article.find('a', attrs={'class':'title'})
            if not title or not title.string.startswith(u'安邦'):
                continue
                
            #获取发布时间
            pubdate = article.find('span',attrs={'class':'date'})
            if not pubdate:
                continue
            mt = re.match(ur'(\d{4})年(\d{1,2})月(\d{1,2})日',pubdate.string)
            if not mt:
                continue
            pubdate = datetime.datetime(int(mt.group(1)),int(mt.group(2)),int(mt.group(3)))
            
            #确定文章是否需要推送，时区固定为北京时间
            tnow = datetime.datetime.utcnow()+datetime.timedelta(hours=8)
            delta = tnow - pubdate
            if self.oldest_article > 0 and delta.days > self.oldest_article:
                continue
            
            urls.append((u'安邦咨询',title.string,title['href'],None))
            
        return urls
        