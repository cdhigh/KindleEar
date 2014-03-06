#!/usr/bin/env python
# -*- coding:utf-8 -*-
from base import BaseFeedBook
import re
from lib.urlopener import URLOpener
from bs4 import BeautifulSoup
import json

def getBook():
    return Xueqiu

class Xueqiu(BaseFeedBook):
    title                 = u'雪球今日话题'
    description           = u'雪球是一个社交投资网络，「今日话题」是雪球用户每日发布的投资交流精选。'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    mastheadfile          = "mh_default.gif"
    coverfile             = "cv_default.jpg"
    oldest_article        = 1
    fulltext_by_readability = False

    remove_tags = ['meta']
    remove_attrs = ['xmlns']
    #keep_only_tags = [dict(name='div', attrs={'class':'statusContent'})]

    feeds = [
            (u'今日话题', 'http://xueqiu.com/hots/topic/rss', True),
            ]

    def processtitle(self, title):
        self.log.info('Title: %s' % title)
        return BaseFeedBook.processtitle(self, title)

    def preprocess(self, article):
        #self.log.info('Preprocess: %s ' % article)
        return BaseFeedBook.preprocess(self, article)
    
    def postprocess(self, content):
        pn = re.compile(ur'<a href="(\S*?)">本话题在雪球有.*?条讨论，点击查看。</a>',
                        re.I)
        mt = pn.search(content)
        url = mt.group(1) if mt else None
        self.log.info(url)
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
        comment_json = mt.group(1) if mt else None
        j = json.loads(comment_json)
        soup = BeautifulSoup(content, "lxml")
        for c in j['comments']:
            p = soup.new_tag('p')
            p.string = c['description']
            self.log.info('desc: %s'%p.string)
            soup.html.body.append(p)

        content = unicode(soup)
        self.log.info('Content:%s' % content)
        return content
