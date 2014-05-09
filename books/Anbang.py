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
                content = AutoDecoder(False).decode(result.content,opener.realurl,result.headers)
        else:
            content = AutoDecoder(False).decode(result.content,opener.realurl,result.headers)
            
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
    
    def soupprocessex(self, soup):
        """ 在网页内容上添加目录的超链接。
        因为在BeautifulSoup对象上一边遍历一边修改会随机出问题，
        所以第一次遍历先记录要修改的位置，然后再统一修改。
        """
        titles = [] #待修改位置
        seen = {} #确认哪些位置需要修改
        for e in soup.body.descendants:
            s = e.string.strip() if e.string else ''
            if s.startswith(u'【') and s.endswith(u'】'):
                #对应标题的内容
                if s in seen and e.parent is not seen[s]:
                    titles.append((seen[s], e))
                else:
                    seen[s] = e
        
        #增加超链接
        idxname = 0
        for src,des in titles:
            if src.parent:
                a = soup.new_tag('a', href='#article_%d'%idxname)
                a['name'] = 'articletoc_%d'%idxname
                a.string = src.string
                src.replace_with(a)
            
            if des.parent:
                a = soup.new_tag('a', href='#articletoc_%d'%idxname)
                a['name'] = 'article_%d'%idxname
                a.string = des.string
                des.replace_with(a)
            
            idxname += 1
        