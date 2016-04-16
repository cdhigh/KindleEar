#!/usr/bin/env python
# -*- coding:utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

from base import BaseFeedBook
import re, urllib
from lib.urlopener import URLOpener
from bs4 import BeautifulSoup
import json
from config import SHARE_FUCK_GFW_SRV

__author__ = 'henryouly'

def getBook():
    return Xueqiu

class Xueqiu(BaseFeedBook):
    title                 = u'雪球今日话题'
    description           = u'雪球是一个社交投资网络，「今日话题」是雪球用户每日发布的投资交流精选。'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    mastheadfile          = "mh_xueqiu.gif"
    coverfile             = "cv_xueqiu.jpg"
    oldest_article        = 1
    fulltext_by_readability = False

    remove_tags = ['meta']
    remove_attrs = ['xmlns']

    feeds = [ (u'今日话题', SHARE_FUCK_GFW_SRV % urllib.quote('http://xueqiu.com/hots/topic/rss'), True) ]
    
    def url4forwarder(self, url):
        #生成经过转发器的URL
        return SHARE_FUCK_GFW_SRV % urllib.quote(url)
    
    def fetcharticle(self, url, opener, decoder):
        #链接网页获取一篇文章
        return BaseFeedBook.fetcharticle(self, self.url4forwarder(url), opener, decoder)
        
    def soupbeforeimage(self, soup):
        for img in soup.find_all('img'):
            imgurl = img['src'] if 'src' in img.attrs else ''
            if imgurl.startswith('http'):
                img['src'] = self.url4forwarder(imgurl)
                
    def postprocess(self, content):
        pn = re.compile(ur'<a href="(\S*?)">本话题在雪球有.*?条讨论，点击查看。</a>', re.I)
        comment = ''
        mt = pn.search(content)
        url = mt.group(1) if mt else None
        if url:
            opener = URLOpener(url, timeout=self.timeout)
            result = opener.open(url)
            if result.status_code == 200 and result.content:
              if self.feed_encoding:
                try:
                  comment = result.content.decode(self.feed_encoding)
                except UnicodeDecodeError:
                  return content

        pn = re.compile(r'SNB.data.goodComments\ =\ ({.*?});', re.S | re.I)
        mt = pn.search(comment)
        if mt:
            comment_json = mt.group(1)
            j = json.loads(comment_json)
            soup = BeautifulSoup(content, "lxml")
            for c in j['comments']:
                u = c['user']['screen_name']
                t = BeautifulSoup('<p>@%s:%s</p>' % (u, c['text']))
                for img in t.find_all('img', alt=True):
                    img.replace_with(t.new_string(img['alt']))
                soup.html.body.append(t.p)

            content = unicode(soup)
        return content
