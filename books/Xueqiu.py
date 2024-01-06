#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

import re
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import json
from config import SHARE_FUCK_GFW_SRV
from books.base_book import BaseFeedBook, UrlOpener

__author__ = 'henryouly'

def getBook():
    return Xueqiu

class Xueqiu(BaseFeedBook):
    title                 = '雪球今日话题'
    description           = '雪球是一个社交投资网络，「今日话题」是雪球用户每日发布的投资交流精选。'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    masthead_file         = "mh_xueqiu.gif"
    cover_file            = "cv_xueqiu.jpg"
    oldest_article        = 1
    fulltext_by_readability = False

    remove_tags = ['meta']
    remove_attrs = ['xmlns']

    feeds = [ ('今日话题', SHARE_FUCK_GFW_SRV.format(quote_plus('http://xueqiu.com/hots/topic/rss')), True) ]
    
    #生成经过转发器的URL
    def url4forwarder(self, url):
        return SHARE_FUCK_GFW_SRV.format(quote_plus(url))
    
    #链接网页获取一篇文章
    def FetchArticle(self, url, opener):
        return super().FetchArticle(self.url4forwarder(url), opener)
        
    def ProcessBeforeImage(self, soup):
        for img in soup.find_all('img'):
            imgUrl = img['src'] if 'src' in img.attrs else ''
            if imgUrl.startswith('http'):
                img['src'] = self.url4forwarder(imgUrl)
                
    def ProcessBeforeYield(self, content):
        pn = re.compile(r'<a href="(\S*?)">本话题在雪球有.*?条讨论，点击查看。</a>', re.I)
        comment = ''
        mt = pn.search(content)
        url = mt.group(1) if mt else None
        if url:
            opener = UrlOpener(url, timeout=self.timeout)
            result = opener.open(url)
            if result.status_code == 200:
                comment = result.text
            else:
                return content

        pn = re.compile(r'SNB.data.goodComments\ =\ ({.*?});', re.S | re.I)
        mt = pn.search(comment)
        if mt:
            commentJson = mt.group(1)
            j = json.loads(commentJson)
            soup = BeautifulSoup(content, "lxml")
            for c in j['comments']:
                u = c['user']['screen_name']
                t = BeautifulSoup('<p>@%s:%s</p>' % (u, c['text']))
                for img in t.find_all('img', alt=True):
                    img.replace_with(t.new_string(img['alt']))
                soup.html.body.append(t.p)

            content = str(soup)
        return content
