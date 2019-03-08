#!/usr/bin/env python3
# encoding: utf-8
# https://www.tohomh123.com/ 网站的免费漫画的基类，简单提供几个信息实现一个子类即可推送特定的漫画
import re, json
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseComicBook
from bs4 import BeautifulSoup
import urllib, urllib2, imghdr
from google.appengine.api import images
from lib.userdecompress import decompressFromBase64


class ToHoMHBaseBook(BaseComicBook):
    accept_domains = ("https://www.tohomh123.com", "https://m.tohomh123.com")
    host = "https://www.tohomh123.com"

    # 获取漫画章节列表
    def getChapterList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host, timeout=60)
        chapterList = []

        url = url.replace("https://m.tohomh123.com", "https://www.tohomh123.com")

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn('fetch comic page failed: %s' % url)
            return chapterList

        content = self.AutoDecodeContent(result.content, decoder,
                                         self.feed_encoding, opener.realurl,
                                         result.headers)

        soup = BeautifulSoup(content, 'html.parser')
        soup = soup.find("ul", {"id": 'detail-list-select-2'})
        if not soup:
            self.log.warn('chapterList is not exist.')
            return chapterList

        lias = soup.findAll('a')
        if not lias:
            self.log.warn('chapterList href is not exist.')
            return chapterList

        for a in lias:
            href = "https://www.tohomh123.com" + a.get("href")
            chapterList.append((unicode(a.contents[0]), href))

        return chapterList

    #获取漫画图片列表
    def getImgList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host, timeout=60)
        imgList = []

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn('fetch comic page failed: %s' % url)
            return imgList

        content = self.AutoDecodeContent(result.content, decoder,
                                         self.feed_encoding, opener.realurl,
                                         result.headers)
        soup = BeautifulSoup(content, 'html.parser')
        scripts = soup.findAll("script", {"type": "text/javascript"})
        for script in scripts:
            if "nextPlayDataUrl " in script.text:
                raw_content = script.text
                break

        if not raw_content:
            self.log.warn('raw_content href is not exist.')
            return imgList

        did = re.search("did=(\d+)", raw_content).group(1)
        sid = re.search("sid=(\d+)", raw_content).group(1)
        pcount = int(re.search("pcount = (\d+)", raw_content).group(1))

        for i in range(pcount):
            url = "https://www.tohomh123.com/action/play/read?did={}&sid={}&iid={}".format(
                did, sid, str(i + 1))
            img_result = opener.open(url)
            if img_result.status_code != 200 or not img_result.content:
                self.log.warn('fetch comic API failed: %s' % url)
                return imgList
            imgList.append(json.loads(img_result.content)["Code"])

        return imgList