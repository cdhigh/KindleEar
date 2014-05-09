#!/usr/bin/env python
# -*- coding:utf-8 -*-
""" 爱思想的网站文章大多数有分页，此书籍是自定义书籍处理分页的一个例子 """

import re
from bs4 import BeautifulSoup, NavigableString
from base import BaseFeedBook

def getBook():
    return Aisixiang

class Aisixiang(BaseFeedBook):
    title                 = u'爱思想一周排行'
    description           = u'最具原创性和思想性的中文学术平台之一。每周六推送。'
    language = 'zh-cn'
    feed_encoding = "utf-8"
    page_encoding = "gbk"
    mastheadfile = "mh_aisixiang.gif"
    coverfile =  'cv_aisixiang.jpg'
    deliver_days = ['Saturday']
    fulltext_by_readability = True
    fulltext_by_instapaper = False
    
    feeds = [
            (u'爱思想一周文章排行', 'http://www.aisixiang.com/rss.php?type=2'),
           ]
    
    def processtitle(self, title):
        return title[:-4] if title.endswith(u'_爱思想') else title
        
    def postprocess(self, content):
        return content.replace('()', '')
        
    def fetcharticle(self, url, opener, decoder):
        """ 爱思想的文章有分页，在此函数内下载全部分页，合并成一个单独的HTML返回。"""
        result = opener.open(url)
        status_code, content = result.status_code, result.content
        if status_code != 200 or not content:
            self.log.warn('fetch article failed(%d):%s.' % (status_code,url))
            return None
        
        #内嵌函数，用于处理分页信息
        def not_is_thispage(tag):
            return not tag.has_attr('class')
        
        if self.page_encoding:
            try:
                firstpart = content.decode(self.page_encoding)
            except UnicodeDecodeError:
                firstpart = decoder.decode(content,opener.realurl,result.headers)
        else:
            firstpart = decoder.decode(content,opener.realurl,result.headers)
        
        otherparts = []
        soup = BeautifulSoup(firstpart, "lxml")
        listpage = soup.find('div', attrs={'class':'list_page'})
        if listpage: #有分页
            for page in listpage.find_all('li'):
                parturl = page.find(not_is_thispage)
                if parturl:
                    parturl = self.urljoin(url, parturl['href'])
                    result = opener.open(parturl)
                    status_code, content = result.status_code, result.content
                    if status_code != 200 or not content:
                        self.log.warn('fetch article failed(%d):%s.' % (status_code,url))
                    else:
                        if self.page_encoding:
                            try:
                                thispart = content.decode(self.page_encoding)
                            except UnicodeDecodeError:
                                thispart = decoder.decode(content,parturl,result.headers)
                        else:
                            thispart = decoder.decode(content,parturl,result.headers)
                        otherparts.append(thispart)
                        
            #合并文件后不再需要分页标志
            listpage.decompose()
            
        #逐个处理各分页，合成一个单独文件
        article1 = soup.find('div', attrs={'id':'content'})
        if not article1:
            return None
        
        for foot in article1.contents[-2:]:
            if isinstance(foot, NavigableString):
                if u'本文责编：' in unicode(foot) or u'进入专题：' in unicode(foot):
                    foot.decompose()
            else:
                for s in foot.strings:
                    if u'本文责编：' in s or u'进入专题：' in s:
                        foot.decompose()
                        break
        
        #将其他页的文章内容附加到第一页的文章内容后面
        for page in otherparts[::-1]:
            souppage = BeautifulSoup(page, "lxml")
            article = souppage.find('div', attrs={'id':'content'})
            if not article:
                continue
            
            for foot in article.contents[-2:]:
                if isinstance(foot, NavigableString):
                    if u'本文责编：' in unicode(foot) or u'进入专题：' in unicode(foot):
                        foot.decompose()
                else:
                    for s in foot.strings:
                        if u'本文责编：' in s or u'进入专题：' in s:
                            foot.decompose()
                            break
                            
            article1.insert_after(article)
        
        for a in soup.find_all('a',attrs={'href':True}):
            if a.string == u'点击此处阅读下一页':
                a.decompose()
        
        return unicode(soup)
    