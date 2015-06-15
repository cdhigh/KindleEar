#!/usr/bin/env python
# -*- coding:utf-8 -*-
import re
from base import BaseFeedBook

def getBook():
    return WSJ

class WSJ(BaseFeedBook):
    title                 = u'华尔街日报'
    description           = u'每天最重要的商业财经要闻及金融市场综述'
    language        = 'zh-cn'
    feed_encoding   = "utf-8"
    page_encoding   = "GBK"
    mastheadfile    = "mh_wsj.gif"
    coverfile       = 'cv_wsj.jpg'
    oldest_article  = 1
    network_timeout = 60
    fulltext_by_readability = False
    fulltext_by_instapaper  = False
    host = r'http://cn.wsj.com/gb/'
    feeds = [
            (u'要闻','http://cn.wsj.com.feedsportal.com/c/33121/f/538760/index.rss'),
           ]
    keep_only_tags = [dict(name='div', attrs={'id':'A'}),]
    
    def fetcharticle(self, url, opener, decoder):
        result = opener.open(url)
        status_code, content = result.status_code, result.content
        if status_code != 200 or not content:
            self.log.warn('fetch article failed(%d):%s.' % (status_code,url))
            return None
        
        if self.page_encoding:
            try:
                content = content.decode('utf-8')
            except UnicodeDecodeError:
                content = decoder.decode(content,url,result.headers)
        else:
            content = decoder.decode(content,url,result.headers)
        
        m = re.search(r'<iframe.*?src="(.*?)".*?>', content)
        if m:
            newurl = m.group(1)
            result = opener.open(newurl)
            status_code, content = result.status_code, result.content
            if status_code != 200 or not content:
                self.log.warn('fetch article failed(%d):%s.' % (status_code,newurl))
                return None
            
            if self.page_encoding:
                try:
                    content = content.decode(self.page_encoding)
                except UnicodeDecodeError:
                    content = decoder.decode(content,newurl,result.headers)
            else:
                content = decoder.decode(content,newurl,result.headers)
        
        return content
        
    def processtitle(self, title):
        title = BaseFeedBook.processtitle(self,title)
        if title.endswith(u'-华尔街日报'):
            return title.replace(u'-华尔街日报','')
        else:
            return title
            
    def soupprocessex(self, soup):
        ' 将首字div变成b '
        content = soup.find('div',attrs={'id':'A'})
        if content:
            firstdiv = content.find('div')
            if firstdiv and firstdiv.string and len(firstdiv.string) == 1:
                b = soup.new_tag('b')
                b.string = firstdiv.string
                firstdiv.replace_with(b)
            