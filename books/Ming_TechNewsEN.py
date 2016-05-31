#!/usr/bin/env python
# -*- coding:utf-8 -*-
import re, datetime
import urllib
import json
from bs4 import BeautifulSoup
from lib.urlopener import URLOpener
from base import BaseFeedBook

def getBook():
    return tech

class tech(BaseFeedBook):
    title                 = 'TechNews_EJ'
    __author__            = 'calibre'
    description           = u'国外新闻精选English&Japanese'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    mastheadfile          = "mh_technews.gif"
    coverfile             = "cv_technews.jpg"
    network_timeout       = 60
    oldest_article        = 1
    max_articles_per_feed = 15
    feeds = [
        ('HuJiang Japanese', 'http://jp.hujiang.com/new/rss'),
        ('Engadget Japanese', 'http://feed.rssad.jp/rss/engadget/rss'),
        ('HuJiang English', 'http://www.hjenglish.com/new/rss'),
        ('Top News - MIT Technology Review', 'http://www.technologyreview.com/topnews.rss'),
        ('ChinaDaily', 'http://www.chinadaily.com.cn/rss/cndy_rss.xml'),
        ('Hacker News', 'https://news.ycombinator.com/rss'),
        ('warfalcon', 'http://ys.8wss.com/rss/oIWsFtxo3oqejVy4KaJ4RDMVIrE0/'),
        ('BBC News - World', 'http://feeds.bbci.co.uk/news/world/rss.xml'),
        ('Quora', 'http://www.quora.com/rss', True),
        ('The Economist: China', 'http://www.economist.com/feeds/print-sections/77729/china.xml'),
        ('The Economist: Science and technology', 'http://www.economist.com/feeds/print-sections/80/science-and-technology.xml'),
        ('The Economist: Asia', 'http://www.economist.com/feeds/print-sections/73/asia.xml'),
        ('Matrix67', 'http://www.matrix67.com/blog/feed'),
        ]