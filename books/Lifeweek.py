#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import re
from books.base_book import BaseFeedBook

def getBook():
    return Lifeweek

class Lifeweek(BaseFeedBook):
    title                 = '三联生活周刊'
    description           = '秉承"倡导品质生活"的理念，提供优质新媒体内容与服务。每周六推送'
    language              = 'zh-cn'
    masthead_file         = "mh_lifeweek.gif"
    cover_file            = "cv_lifeweek.jpg"
    oldest_article        = 0
    deliver_days          = ['Saturday']

    feeds = [
        ('三联生活网', 'http://app.lifeweek.com.cn/?app=rss&controller=index&action=feed'),
    ]

    def ProcessTitle(self, title):
        return title[:-6] if title.endswith('_三联生活网') else title

    def PreProcess(self, content):
        #当文章有分页时，去除重复的首页

        #去除脚注，保留版权声明
        re_footer = re.compile(r'<div id="content_ad" [^>]*>.*</div>')
        article = re_footer.sub('', content)

        #为了统一，去除“网络编辑“
        re_editor = re.compile(r'<p class="editer" [^>]*>.*</p>')
        article = re_editor.sub('', article)

        re_mce = re.compile(r'_mcePaste')
        if re_mce.search(content) is not None:
            #文章有分页，只处理一层嵌套
            re_first_page = re.compile(r'<p[^>]*>[^<>]*(<[^<>]*>[^<>]*</[^<>]*>|<[^<>]*[/]>){,3}[^<>]*</p>')
            article = re_first_page.sub('', article)

        return article
