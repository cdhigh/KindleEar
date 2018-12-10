#!/usr/bin/env python3
# encoding: utf-8
#https://www.733.so或者https://m.733.so网站的免费漫画的基类，简单提供几个信息实现一个子类即可推送特定的漫画
#Author: insert0003 <https://github.com/insert0003>
import re, json
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseComicBook
from bs4 import BeautifulSoup
import urllib, urllib2, imghdr
from base64 import b64decode, b64encode

class Seven33SoBaseBook(BaseComicBook):
    title               = u''
    description         = u''
    language            = ''
    feed_encoding       = ''
    page_encoding       = ''
    mastheadfile        = ''
    coverfile           = ''
    host                = 'https://m.733.so'
    feeds               = [] #子类填充此列表[('name', mainurl),...]

    #获取漫画章节列表
    def getChapterList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host, timeout=60)
        chapterList = []

        if url.startswith( "https://m.733.so" ):
            url = url.replace('https://m.733.so', 'https://www.733.so')

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn('fetch comic page failed: %s' % url)
            return chapterList

        content = self.AutoDecodeContent(result.content, decoder, self.feed_encoding, opener.realurl, result.headers)

        soup = BeautifulSoup(content, 'html.parser')
        soup = soup.find('div', {"class": "cy_plist"})
        if (soup is None):
            self.log.warn('cy_plist is not exist.')
            return chapterList

        lias = soup.findAll('a')
        if (lias is None):
            self.log.warn('chapterList href is not exist.')
            return chapterList

        for aindex in range(len(lias)):
            rindex = len(lias)-1-aindex
            href = "https://m.733.so/" + lias[rindex].get("href")
            chapterList.append(href)

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

        content = self.AutoDecodeContent(result.content, decoder, self.feed_encoding, opener.realurl, result.headers)

        res = re.search(r'var qTcms_S_m_murl_e=".*";', content).group()
        if (res is None):
            self.log.warn('var qTcms_S_m_murl_e is not exist.')
            return imgList

        list_encoded = res.split('\"')[1]
        lz_decoded = b64decode(list_encoded)
        images = lz_decoded.split("$qingtiandy$")

        if (images is None):
            self.log.warn('image list is not exist.')
            return imgList

        for img in images:
            imgb64 = b64encode(img.replace("http://www.baidu1.com/", ""))
            img_url = u'http://new.234us.com:8989/img_new.php?data={}'.format(imgb64)
            imgList.append(img_url)

        return imgList