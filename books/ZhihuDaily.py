#!/usr/bin/env python
# -*- coding:utf-8 -*-

__author__      = "@ohdarling88"
__version__     = "0.1.0"

import re
import json
from datetime import datetime
from base import BaseFeedBook
from lib.urlopener import URLOpener

# 知乎屏蔽了 GAE 访问 API，所以需要一个中转服务器来获取知乎日报的 Feed 内容
# nodejs 版本可以参考：https://github.com/ohdarling/ZhihuDailyForwarder
# 搭建完中转服务器后，将 feeds 中的 http://news.at.zhihu.com/api/1.1/news/latest 替换为实际的中转服务器地址

def getBook():
    return ZhihuDaily

class ZhihuDaily(BaseFeedBook):
    title                 = u'知乎日报'
    description           = u'知乎日报'
    network_timeout = 60
    language = 'zh-cn'
    feed_encoding = "utf-8"
    page_encoding = "utf-8"
    mastheadfile = "mh_zhihudaily.gif"
    coverfile = "cv_zhihudaily.jpg"
    keep_only_tags = [dict(name='div', attrs={'class':['question']})]
    remove_tags = []
    remove_ids = []
    remove_classes = ['view-more', 'avatar', 'headline', 'global-header']
    remove_attrs = []
    
    feeds = [
            (u'今日头条', r'http://news.at.zhihu.com/api/1.1/news/latest', u'top_stories'),
            (u'今日热闻', r'http://news.at.zhihu.com/api/1.1/news/latest', u'news'),
           ]
    
    def processtitle(self, title):
        title = re.sub(r'(\n)+', ' ', title)
        #title = title.replace(u' 知乎生活周刊', u'')
        return title

    def ParseFeedUrls(self):
        """ return list like [(section,title,url,desc),..] """
        urls = []
        tnow = datetime.utcnow()
        urladded = set()
        for feed in self.feeds:
            section, url = feed[0], feed[1]
            partition = feed[2]
            timeout = 30
            opener = URLOpener(self.host, timeout=timeout)
            result = opener.open(url)
            if result.status_code == 200 and result.content:
                feed = json.loads(result.content.decode(self.feed_encoding))

                for item in feed[partition]:
                    for e in item['items']:
                        #支持HTTPS
                        urlfeed = e['share_url'].replace('http://','https://') if url.startswith('https://') else e['share_url']
                        if urlfeed in urladded:
                            self.log.warn('skipped %s' % urlfeed)
                            continue
                            
                        desc = None
                        urls.append((section, e['title'], urlfeed, desc))
                        urladded.add(urlfeed)
            else:
                self.log.warn('fetch rss failed(%d):%s'%(result.status_code,url))
        #self.log.warn('%s' % json.dumps(urls))
        return urls

