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
    title                 = 'TechNews_CN'
    __author__            = 'calibre'
    description           = u'国内科技新闻精选，各种科普，沪江英文日文，果壳天文，科学精选。'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    mastheadfile          = "mh_technews.gif"
    coverfile             = "cv_technews.jpg"
    network_timeout       = 60
    oldest_article        = 1
    max_articles_per_feed = 15
    feeds = [
        (u'TechCrunch 中国', 'http://techcrunch.cn/feed/'),
        (u'爱范儿', 'http://www.ifanr.com/feed'),
        (u'小道消息', 'http://hutu.me/feed'),
        (u'极客公园', 'http://www.geekpark.net/rss'),
        (u'极客范', 'http://www.geekfan.net/feed/'),
        (u'人人都是产品经理', 'http://iamsujie.com/feed/'),
        (u'邹剑波Kant', 'http://kant.cc/feed'),
        (u'环球科学', 'http://blog.sina.com.cn/rss/sciam.xml'),
        (u'科普公园', 'http://www.scipark.net/feed/'),
        (u'科学松鼠会', 'http://songshuhui.net/feed'),
        (u'泛科学', 'http://pansci.tw/feed'),
        (u'果壳网', 'http://www.guokr.com/rss/'),
        (u'果壳网科学人', 'http://feed43.com/8781486786220071.xml'),
        (u'果壳网天文', 'http://feed43.com/3144628515834775.xml'),
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