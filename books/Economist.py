#!/usr/bin/env python
# -*- coding:utf-8 -*-
from bs4 import BeautifulSoup
from base import BaseFeedBook, URLOpener, string_of_tag

def getBook():
    return Economist

class Economist(BaseFeedBook):
    title                 = 'The Economist'
    description           = 'Global news and current affairs from a European perspective. deliver on Friday.'
    language              = 'en'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    mastheadfile          = "mh_economist.gif"
    coverfile             = "cv_economist.jpg"
    deliver_days          = ['Friday']
    
    remove_classes = ['ec-messages',]
    feeds = [
        ('The world this week', 'http://www.economist.com/rss/the_world_this_week_rss.xml'),
        ('Leaders', 'http://www.economist.com/feeds/print-sections/69/leaders.xml'),
        ('Briefings', 'http://www.economist.com/feeds/print-sections/102/briefings2.xml'),
        ('Special reports', 'http://www.economist.com/feeds/print-sections/103/special-reports.xml'),
        ('Britain', 'http://www.economist.com/feeds/print-sections/76/britain.xml'),
        ('Europe', 'http://www.economist.com/feeds/print-sections/75/europe.xml'),
        ('United States', 'http://www.economist.com/feeds/print-sections/71/united-states.xml'),
        ('The Americas', 'http://www.economist.com/feeds/print-sections/72/the-americas.xml'),
        ('Middle East and Africa', 'http://www.economist.com/feeds/print-sections/99/middle-east-africa.xml'),
        ('Asia', 'http://www.economist.com/feeds/print-sections/73/asia.xml'),
        ('China', 'http://www.economist.com/feeds/print-sections/77729/china.xml'),
        ('International', 'http://www.economist.com/feeds/print-sections/74/international.xml'),
        ('Business', 'http://www.economist.com/feeds/print-sections/77/business.xml'),
        ('Finance and economics', 'http://www.economist.com/feeds/print-sections/79/finance-and-economics.xml'),
        ('Science and technology', 'http://www.economist.com/feeds/print-sections/80/science-and-technology.xml'),
        ('Books and arts', 'http://www.economist.com/feeds/print-sections/89/books-and-arts.xml'),
        ('Obituary', 'http://www.economist.com/feeds/print-sections/82/obituary.xml'),
        ]
    