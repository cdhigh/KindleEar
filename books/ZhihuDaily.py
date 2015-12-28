#!/usr/bin/env python
# -*- coding:utf-8 -*-

__author__      = "@ohdarling88"
__version__     = "0.1.2"

import urllib
import json
from base import BaseFeedBook
from lib.urlopener import URLOpener
from config import SHARE_FUCK_GFW_SRV

# 知乎屏蔽了 GAE 访问 API，所以需要一个中转服务器来获取知乎日报的 Feed 内容
# nodejs 版本可以参考：https://github.com/ohdarling/ZhihuDailyForwarder
# 搭建完中转服务器后，将 feeds 中的 http://news.at.zhihu.com/api/1.1/news/latest 替换为实际的中转服务器地址

#因为KindleEar作者不想安装node.js本地开发环境，部署node.js不成功，
#因此自己写了一个python版本的：http://github.com/cdhigh/forwarder
#http://forwarder.ap01.aws.af.cm为KindleEar作者搭建的转发器

def getBook():
    return ZhihuDaily

class ZhihuDaily(BaseFeedBook):
    title                 = u'知乎日报'
    description           = u'知乎日报的内容是动态更新的，建议在晚 8 点或 23 点进行投递。此外，知乎日报 API 需要转发服务器，参见 https://github.com/ohdarling/ZhihuDailyForwarder'
    network_timeout = 60
    language = 'zh-cn'
    feed_encoding = "utf-8"
    page_encoding = "utf-8"
    mastheadfile = "mh_zhihudaily.gif"
    coverfile = "cv_zhihudaily.jpg"
    fulltext_by_readability = False
    fulltext_by_instapaper = False
    keep_only_tags = [dict(name='h1', attrs={'class':'headline-title'}),
        dict(name='div', attrs={'class':'question'})]
    remove_tags = []
    remove_ids = []
    remove_classes = ['view-more', 'avatar']
    remove_attrs = []
    extra_css = """
        .question-title {font-size:1.1em;font-weight:normal;text-decoration:underline;color:#606060;}
        .meta {font-size:0.9em;color:#808080;}
    """
    
    #http_forwarder = 'http://forwarder.ap01.aws.af.cm/?k=xzSlE&t=60&u=%s'
    
    feeds = [
            (u'今日头条', 'http://news.at.zhihu.com/api/1.2/news/latest'),
           ]
           
    partitions = [('top_stories',u'今日头条'),('news',u'今日热闻'),]
    
    def url4forwarder(self, url):
        ' 生成经过转发器的URL '
        return SHARE_FUCK_GFW_SRV % urllib.quote(url)
        
    def ParseFeedUrls(self):
        """ return list like [(section,title,url,desc),..] """
        urls = []
        urladded = set()
        url = self.url4forwarder(self.feeds[0][1])
        opener = URLOpener(self.host, timeout=self.timeout)
        result = opener.open(url)
        if result.status_code == 200 and result.content:
            feed = json.loads(result.content.decode(self.feed_encoding))
            
            for partition,section in self.partitions:
                for item in feed[partition]:
                    urlfeed = item['share_url']
                    if urlfeed in urladded:
                        self.log.info('duplicated, skipped %s' % urlfeed)
                        continue
                        
                    urls.append((section, item['title'], self.url4forwarder(urlfeed), None))
                    urladded.add(urlfeed)
        else:
            self.log.warn('fetch rss failed(%s):%s' % (URLOpener.CodeMap(result.status_code), url))
        return urls

    #def fetcharticle(self, url, opener, decoder):
    #    result = opener.open(self.url4forwarder(url))
    #    status_code, content = result.status_code, result.content
    #    if status_code != 200 or not content:
    #        self.log.warn('fetch article failed(%s):%s.' % (URLOpener.CodeMap(status_code),url))
    #        return None
    #    
    #    if self.page_encoding:
    #        return content.decode(self.page_encoding)
    #    else:
    #        return decoder.decode(content,url,result.headers)
            