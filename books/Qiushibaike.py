#!/usr/bin/env python
# -*- coding:utf-8 -*-
import re
from base import *

def getBook():
    return Qiushibaike

class Qiushibaike(BaseFeedBook):
    title                 = u'糗事百科'
    description           = u'快乐就是要建立在别人的痛苦之上，额外赠送哈哈.MX'
    language = 'zh-cn'
    feed_encoding = "utf-8"
    page_encoding = "utf-8"
    mastheadfile = "mh_qiushibaike.gif"
    coverfile = "cv_qiushibaike.jpg"
    network_timeout       = 30
    keep_only_tags = [dict(name='div', attrs={'class':'main'}),] # qiushibaike
        #dict(name='div',attrs={'class':'block joke-item'}), # haha.mx
        #    ]
    remove_tags = []
    remove_ids = ['bdshare',]
    remove_classes = ['sharebox','comment','share','up','down', #qiushibaike
            'backtop','close','author','col2','sponsor','pagebar', #qiushibaike
            'seconday-nav fl','toolkit fr','fr','info clearfix', # haha.mx
            'joke-item-footer','pagination','pos-ab','praise-box',] # haha.mx
    remove_attrs = []
    
    feeds = [
            #(u'8小时最热', r'http://www.qiushibaike.com'),
            (u'24小时 Page1', r'http://www.qiushibaike.com/hot'),
            (u'24小时 Page2', r'http://www.qiushibaike.com/hot/page/2'),
            #(u'哈哈MX', r'http://www.haha.mx/'),
            (u'哈哈.MX Page1', r'http://www.haha.mx/good/day'),
            (u'哈哈.MX Page2', r'http://www.haha.mx/good/day/2'),
           ]
    
    def processtitle(self, title):
        title = re.sub(r'(\n)+', ' ', title)
        title = title.replace(u' :: 糗事百科 :: 快乐减压 健康生活', u'')
        return title.replace(u'——分享所有好笑的事情', u'')
        
    def soupbeforeimage(self, soup):
        if soup.html.head.title.string.find(u'哈哈') > 0:
            for img in list(soup.find_all('img')): #HAHA.MX切换为大图链接
                src = img['src']
                if src.find(r'/small/') > 0:
                    img['src'] = src.replace(r'/small/', r'/big/')
        
    def soupprocessex(self, soup):
        if u'小时' in soup.html.head.title.string: #qiushibaike
            for article in soup.find_all("a", attrs={"href":re.compile(r'^/article')}):
                p = soup.new_tag("p", style='color:grey;text-decoration:underline;')
                p.string = string_of_tag(article.string)
                article.replace_with(p)
            
            first = True
            for detail in soup.find_all("div", attrs={"class":"content"}):
                if not first:
                    hr = soup.new_tag("hr")
                    detail.insert(0, hr)
                first = False
        
        if soup.html.head.title.string.startswith(u'哈哈'): #haha.mx
            first = True
            for item in soup.find_all("div", attrs={"class":"block joke-item"}):
                if not first:
                    hr = soup.new_tag("hr")
                    item.insert(0, hr)
                first = False
            