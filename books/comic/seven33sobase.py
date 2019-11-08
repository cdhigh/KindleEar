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

        if url.startswith( "https://www.733.so" ):
            url = url.replace('https://www.733.so', 'https://m.733.so')

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn('fetch comic page failed: %s' % url)
            return chapterList

        content = self.AutoDecodeContent(result.content, decoder, self.feed_encoding, opener.realurl, result.headers)

        soup = BeautifulSoup(content, 'html.parser')
        # <ul class="Drama autoHeight" id="mh-chapter-list-ol-0">
        soup = soup.find('ul', {"class":"Drama autoHeight", "id":"mh-chapter-list-ol-0"})
        if (soup is None):
            self.log.warn('chapter-list is not exist.')
            return chapterList

        lias = soup.findAll('a')
        if (lias is None):
            self.log.warn('chapter-list is not exist.')
            return chapterList

        for aindex in range(len(lias)):
            rindex = len(lias)-1-aindex
            href = "https://m.733.so" + lias[rindex].get('href', '')
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
                # http://www.baidu1.com/2016/06/28/21/042f051bea.jpg
                # http://img_733.234us.com/newfile.php?data=MjAxNi8wNi8yOC8yMS8wNDJmMDUxYmVhLmpwZ3wxNTQ4OTgzNDA0ODkwfDI2Nzk4fDMwOTYzNnxt
                b64str = img.replace("http://www.baidu1.com/", "") + '|{}|{}|{}|m'.format(tid, cid, pid)
            elif ("http://ac.tc.qq.com/" in img) or ("http://res.gufengmh.com/" in img):
                b64str = img + '|{}|{}|{}|m'.format(tid, cid, pid)
            else:
                # https://res.gufengmh8.com/
                # http://res.img.pufei.net
                # https://images.dmzj.com/
                self.log.warn('Ths image herf is: %s' % img)
                b64str = img

            if b64str == img:
                img_url = b64str
            else:
                imgb64 = b64encode(b64str)
                requestImg = 'http://img_733.234us.com/newfile.php?data={}'.format(imgb64)
                img_url = self.getImgUrl(requestImg)
            imgList.append(img_url)

        return imgList

    #获取漫画图片格式
    def getImgUrl(self, url):
        opener = URLOpener(self.host, timeout=60)
        headers = {
            'Host': "img_733.234us.com",
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 6_0 like Mac OS X) AppleWebKit/536.26 (KHTML, like Gecko) Version/6.0 Mobile/10A5376e Safari/8536.25'}
        result = opener.open(url, headers=headers)
        if result.status_code != 200 or opener.realurl == url:
            self.log.warn('can not get real comic url for : %s' % url)
            return None

        return opener.realurl