#!/usr/bin/env python
# -*- coding:utf-8 -*-
import datetime, json
from lib import feedparser
from lib.urlopener import URLOpener
from base import BaseFeedBook
from lib.autodecoder import AutoDecoder

class WeixinBook(BaseFeedBook):

    #继承自BaseFeedBook，参数填写参考BaseFeedBook的注释

    #每个子类必须重新定义这个属性，为搜狗微信公众搜索地址，例：http://weixin.sogou.com/gzh?openid=oIWsFt6yAL253-qrm9rkdugjSlOY
    #每个链接格式为元组：(分节标题, URL)
    #注意，如果分节标题是中文的话，增加u前缀，比如
    #(u'沪江英语', 'http://weixin.sogou.com/gzh?openid=oIWsFt6yAL253-qrm9rkdugjSlOY'),
    feeds = []

    def ParseFeedUrls(self):
        """ return list like [(section,title,url,desc),..] """
        urls = []
        tnow = datetime.datetime.utcnow()
        urladded = set()

        for feed in self.feeds:
            section, url = feed[0], feed[1].replace('gzh', 'gzhjs')
            isfulltext = feed[2] if len(feed) > 2 else False
            timeout = self.timeout+10 if isfulltext else self.timeout
            opener = URLOpener(self.host, timeout=timeout)
            result = opener.open(url)
            if result.status_code == 200 and result.content:
                if self.feed_encoding:
                    try:
                        content = result.content.decode(self.feed_encoding)
                    except UnicodeDecodeError:
                        content = AutoDecoder(True).decode(result.content,opener.realurl,result.headers)
                else:
                    content = AutoDecoder(True).decode(result.content,opener.realurl,result.headers)
                content = content[content.index('{'):content.index('}')+1]
                content = json.loads(content)

                for e in content['items'][:self.max_articles_per_feed]:
                    e = feedparser.parse(e)['entries'][0]
                    updated = None
                    if hasattr(e, 'lastmodified') and e.lastmodified:
                        updated = float(e.lastmodified)

                    if self.oldest_article > 0 and updated:
                        updated = datetime.datetime.utcfromtimestamp(updated)
                        delta = tnow - updated
                        if self.oldest_article > 365:
                            threshold = self.oldest_article #以秒为单位
                        else:
                            threshold = 86400*self.oldest_article #以天为单位

                        if delta.days*86400+delta.seconds > threshold:
                            self.log.info("Skip old article(%s): %s" % (updated.strftime('%Y-%m-%d %H:%M:%S'),e.href))
                            continue

                    #支持HTTPS
                    if hasattr(e, 'href'):
                        if url.startswith('https://'):
                            urlfeed = e.href.replace('http://','https://')
                        else:
                            urlfeed = e.href

                        if urlfeed in urladded:
                            continue
                    else:
                        urlfeed = ''

                    desc = None
                    urls.append((section, e.title, urlfeed, desc))
                    urladded.add(urlfeed)
            else:
                self.log.warn('fetch rss failed(%d):%s'%(result.status_code,url))

        return urls
