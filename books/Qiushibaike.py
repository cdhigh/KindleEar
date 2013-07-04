#!/usr/bin/env python
# -*- coding:utf-8 -*-
import re
from base import WebpageBook, Tag

def getBook():
    return Qiushibaike

class Qiushibaike(WebpageBook):
    title                 = u'糗事百科'
    description           = u'快乐就是要建立在别人的痛苦之上'
    language = 'zh-cn'
    feed_encoding = "utf-8"
    page_encoding = "utf-8"
    mastheadfile = "mh_qiushibaike.gif"
    coverfile = "cv_qiushibaike.jpg"
    keep_only_tags = [dict(name='div', attrs={'class':['main']}), # qiushibaike
        dict(name='div',attrs={'class':['block joke-item']}), # haha.mx
            ]
    remove_tags = []
    remove_ids = ['bdshare',]
    remove_classes = ['sharebox','comment','share','up','down', #qiushibaike
            'backtop','close','author','col2','sponsor','pagebar', #qiushibaike
            'toolkit fr','fr','clearfix mt-15',] # hah.mx
    remove_attrs = []
    
    feeds = [
            (u'8小时最热', r'http://www.qiushibaike.com'),
            (u'24小时最热Page1', r'http://www.qiushibaike.com/hot'),
            (u'24小时最热Page2', r'http://www.qiushibaike.com/hot/page/2'),
            (u'哈哈MX', r'http://www.haha.mx/'),
            (u'哈哈MX(24Hrs)Page1', r'http://www.haha.mx/good/day'),
            (u'哈哈MX(24Hrs)Page2', r'http://www.haha.mx/good/day/2'),
           ]
    
    def processtitle(self, title):
        title = re.sub(r'(\n)+', '', title)
        title = title.replace(u' :: 糗事百科 :: 快乐减压 健康生活', u'')
        return title.replace(u'——分享所有好笑的事情', u'')
        
    def soupbeforeimage(self, soup):
        for img in list(soup.findAll('img')): #HAHA.MX切换为大图链接
            src = img['src']
            if src.find(r'/small/') > 0:
                img['src'] = src.replace(r'/small/', r'/big/')
        
    def soupprocessex(self, soup):
        for article in soup.findAll("a", attrs={"href":re.compile(r'^/article')}):
            p = Tag(soup, "p", [('style', 'color:grey;text-decoration:underline;')])
            p.insert(0,article.string)
            article.replaceWith(p)
        
        first = True
        for detail in soup.findAll("div", attrs={"class":"detail"}):
            hr = Tag(soup, "hr")
            if not first:
                detail.insert(0,hr)
            first = False
        
        first = True
        for item in soup.findAll("div", attrs={"class":"block joke-item"}):
            hr = Tag(soup, "hr")
            if not first:
                item.insert(0,hr)
            first = False
            