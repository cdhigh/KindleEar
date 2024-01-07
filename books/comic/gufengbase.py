#!/usr/bin/env python3
# encoding: utf-8
#https://www.gufengmh8.com或者https://m.gufengmh8.com网站的免费漫画的基类，简单提供几个信息实现一个子类即可推送特定的漫画
#Author: insert0003 <https://github.com/insert0003>
import re, json
from lib.urlopener import UrlOpener
from books.base_comic_book import BaseComicBook
from bs4 import BeautifulSoup

class GuFengBaseBook(BaseComicBook):
    accept_domains = ("https://www.gufengmh8.com", "https://m.gufengmh8.com")
    host = "https://m.gufengmh8.com"

    #获取漫画章节列表
    def GetChapterList(self, url):
        opener = URLOpener(self.host, timeout=self.timeout)
        chapterList = []

        url = url.replace('https://www.gufengmh8.com', 'https://m.gufengmh8.com')

        result = opener.open(url)
        if result.status_code != 200:
            self.log.warn('Fetch comic page failed: {}'.format(url))
            return chapterList

        soup = BeautifulSoup(result.text, 'lxml')
        #<ul class="Drama autoHeight" data-sort="asc" id="chapter-list-1">
        tag = soup.find('ul', {"class": "Drama autoHeight", "id": "chapter-list-1"})
        if not tag:
            self.log.warn('Chapter-list is not exist.')
            return chapterList

        for index, a in enumerate(tag.find_all('a')):
            href = urljoin("https://m.gufengmh8.com", a.get('href', ''))
            span = a.find("span")
            if not span:
                chapterList.append(('第{}话'.format(index + 1), href))
            else:
                chapterList.append((span.contents[0].string, href))

        return chapterList

    #获取漫画图片列表
    def GetImgList(self, url):
        opener = UrlOpener(self.host, timeout=self.timeout)
        imgList = []

        result = opener.open(url)
        if result.status_code != 200:
            self.log.warn('Fetch comic page failed: {}'.format(url))
            return imgList

        content = result.text
        #var chapterPath = "images/comic/31/61188/";
        chapterPath = re.search(r'(var chapterPath = ")(.*)(";var chapterPrice)', content)
        if not chapterPath:
            self.log.warn('Var chapterPath is not exist.')
            return imgList
        else:
            chapterPath = chapterPath.group(2)

        #var pageImage = "https://res.gufengmh8.com/gufeng/images/";
        imgPrefix = re.search(r'(var pageImage = ")(.*)(gufeng/images/)', content)
        if not imgPrefix:
            self.log.warn('"https://res.gufengmh8.com/gufeng/images/ is not exist.')
            return imgList
        else:
            imgPrefix = imgPrefix.group(2) + "/"

        #var chapterImages = ["",""];
        images = re.search(r'(var chapterImages = \[)(.*)(\];)', content)
        if not images:
            self.log.warn('Var chapterImages is not exist.')
            return imgList
        else:
            images = images.group(2).split(',')

        for img in images:
            imgList.append(imgPrefix + chapterPath + img.replace("\"", ""))

        return imgList
