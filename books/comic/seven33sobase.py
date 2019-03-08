#!/usr/bin/env python3
# encoding: utf-8
#https://www.733.so或者https://m.733.so网站的免费漫画的基类，简单提供几个信息实现一个子类即可推送特定的漫画
#Author: insert0003 <https://github.com/insert0003>
import re, json, urlparse, time
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseComicBook
from bs4 import BeautifulSoup
import urllib, urllib2, imghdr
from base64 import b64decode, b64encode

class Seven33SoBaseBook(BaseComicBook):
    accept_domains = ("https://www.733.so", "https://m.733.so")
    host = "https://www.733.so"

    # 获取漫画章节列表
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
            href = "https://www.733.so" + lias[rindex].get("href")
            chapterList.append((lias[rindex].get_text(), href))

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

        urlpaths = urlparse.urlsplit(url.lower()).path.split("/")
        if ( (u"mh" in urlpaths) and (urlpaths.index(u"mh")+2 < len(urlpaths)) ):
            tid = str(time.time()).replace(".", "1")
            if len(tid) == 12:
                tid = tid + "1"
            cid = urlpaths[urlpaths.index(u"mh")+1]
            pid = urlpaths[urlpaths.index(u"mh")+2].replace(".html", "")
        else:
            self.log.warn('Can not get cid and pid from URL: {}.'.format(url))
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
            if "http://www.baidu1.com/" in img:
                b64str = img.replace("http://www.baidu1.com/", "") + '|{}|{}|{}|pc'.format(tid, cid, pid)
                imgb64 = b64encode(b64str)
                img_url = u'http://img_733.234us.com/newfile.php?data={}'.format(imgb64)
            elif "http://ac.tc.qq.com/" in img:
                b64str = img + '|{}|{}|{}|pc'.format(tid, cid, pid)
                imgb64 = b64encode(b64str)
                img_url = u'http://img_733.234us.com/newfile.php?data={}'.format(imgb64)
            else:
                img_url = img

            self.log.info('Ths image herf is: %s' % img_url)
            imgList.append(img_url)

        return imgList