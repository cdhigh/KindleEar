#!/usr/bin/env python3
# -*- coding:utf-8 -*-

__author__      = "@ohdarling88"
__version__     = "0.1.2"

import json
from urllib.parse import quote_plus
from books.base_book import BaseFeedBook, UrlOpener, RssItemTuple
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
    title                 = '知乎日报'
    description           = '知乎日报的内容是动态更新的，建议在晚 8 点或 23 点进行投递。此外，知乎日报 API 需要转发服务器，参见 https://github.com/ohdarling/ZhihuDailyForwarder'
    language      = 'zh-cn'
    feed_encoding = "utf-8"
    page_encoding = "utf-8"
    masthead_file = "mh_zhihudaily.gif"
    cover_file    = "cv_zhihudaily.jpg"
    fulltext_by_readability = False
    keep_only_tags = [dict(name='h1', attrs={'class': 'headline-title'}),
        dict(name='div', attrs={'class': 'question'})]
    remove_tags = []
    remove_ids = []
    remove_classes = ['view-more', 'avatar']
    remove_attrs = []
    extra_css = """.question-title {font-size:1.1em;font-weight:normal;text-decoration:underline;color:#606060;}
        .meta {font-size:0.9em;color:#808080;}
    """
    
    #http_forwarder = 'http://forwarder.ap01.aws.af.cm/?k=xzSlE&t=60&u=%s'
    
    feeds = [
            ('今日头条', 'http://news.at.zhihu.com/api/1.2/news/latest'),
           ]
           
    partitions = [('top_stories', '今日头条'), ('news', '今日热闻'),]
    
    #生成经过转发器的URL
    def url4forwarder(self, url):
        return SHARE_FUCK_GFW_SRV.format(quote_plus(url))
    
    #返回一个 RssItemTuple 列表，里面包含了接下来需要抓取的链接或描述
    def ParseFeedUrls(self):
        urls = []
        urlAdded = set()
        url = self.url4forwarder(self.feeds[0][1])
        opener = UrlOpener(self.host, timeout=self.timeout)
        result = opener.open(url)
        if result.status_code == 200:
            feed = json.loads(result.text)
            
            for partition, section in self.partitions:
                for item in feed[partition]:
                    urlFeed = item['share_url']
                    if urlFeed in urlAdded:
                        self.log.info('duplicated zhihudiaily, skipped {}'.format(urlFeed))
                        continue
                    
                    urls.append(RssItemTuple(section, item['title'], self.url4forwarder(urlFeed), ""))
                    urlAdded.add(urlFeed)
        else:
            self.log.warn('fetch rss failed({}):{}'.format(UrlOpener.CodeMap(result.status_code), url))
        return urls

            