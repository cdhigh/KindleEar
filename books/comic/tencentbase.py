#!/usr/bin/env python3
# encoding: utf-8
#http://ac.qq.com或者http://m.ac.qq.com网站的免费漫画的基类，简单提供几个信息实现一个子类即可推送特定的漫画
#Author: insert0003 <https://github.com/insert0003>
import re, urlparse, json, base64
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseComicBook
from bs4 import BeautifulSoup


class TencentBaseBook(BaseComicBook):
    accept_domains = ("http://ac.qq.com", "http://m.ac.qq.com")
    host = "http://m.ac.qq.com"
    feeds = []  # 子类填充此列表[('name', mainurl),...]

    # 获取漫画章节列表
    def getChapterList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host, timeout=60)
        chapterList = []

        urlpaths = urlparse.urlsplit(url.lower()).path.split("/")
        if ( (u"id" in urlpaths) and (urlpaths.index(u"id")+1 < len(urlpaths)) ):
            comic_id = urlpaths[urlpaths.index(u"id")+1]

        if ( (not comic_id.isdigit()) or (comic_id=="") ):
            self.log.warn('can not get comic id: %s' % url)
            return chapterList

        url = 'https://m.ac.qq.com/comic/chapterList/id/{}'.format(comic_id)
        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn('fetch comic page failed: %s' % url)
            return chapterList

        content = self.AutoDecodeContent(result.content, decoder, self.feed_encoding, opener.realurl, result.headers)

        soup = BeautifulSoup(content, 'html.parser')
        # <section class="chapter-list-box list-expanded" data-vip-free="1">
        section = soup.find('section', {'class': 'chapter-list-box list-expanded'})
        if (section is None):
            self.log.warn('chapter-list-box is not exist.')
            return chapterList

        # <ul class="chapter-list normal">
        # <ul class="chapter-list reverse">
        reverse_list = section.find('ul', {'class': 'chapter-list reverse'})
        if (reverse_list is None):
            self.log.warn('chapter-list is not exist.')
            return chapterList

        for item in reverse_list.find_all('a'):
            # <a class="chapter-link lock" data-cid="447" data-seq="360" href="/chapter/index/id/531490/cid/447">360</a>
            # https://m.ac.qq.com/chapter/index/id/511915/cid/1
            href = 'https://m.ac.qq.com' + item.get('href')
            isVip = "lock" in item.get('class')
            if isVip == True:
                self.log.info("Chapter {} is Vip, waiting for free.".format(href))
                continue

            chapterList.append((item.get_text(), href))

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

        content = result.content
        cid_page = self.AutoDecodeContent(content, decoder, self.page_encoding, opener.realurl, result.headers)
        filter_result = re.findall(r"data\s*:\s*'(.+?)'", cid_page)
        # "picture": [{},...{}]}
        if len(filter_result) != 0:
            # "picture" > InBpY3R1cmUi
            # picture": > cGljdHVyZSI6
            # icture":[ > aWN0dXJlIjpb
            if "InBpY3R1cmUi" in filter_result[0]:
                base64data = filter_result[0].split("InBpY3R1cmUi")[1]
                self.log.warn('found flag string: %s'%"InBpY3R1cmUi")
            elif "cGljdHVyZSI6" in filter_result[0]:
                base64data = filter_result[0].split("cGljdHVyZSI6")[1]
                self.log.warn('found flag string: %s'%"cGljdHVyZSI6")
            elif "aWN0dXJlIjpb" in filter_result[0]:
                base64data = filter_result[0].split("aWN0dXJl")[1]
                self.log.warn('found flag string: %s'%"aWN0dXJlIjpb")
            else:
                self.log.warn('can not found flag string in data: %s'%filter_result[0])
                return imgList
            decodeData = base64.decodestring(base64data)
            startIndex = decodeData.find('[')
            endIndex = decodeData.find(']')

            if startIndex > -1 and endIndex > -1:
                img_detail_json = json.loads(decodeData[startIndex:endIndex+1])
                for img_url in img_detail_json:
                    if ( 'url' in img_url ):
                        imgList.append(img_url['url'])
                    else:
                        self.log.warn('no url in img_url:%s' % img_url)
            else:
                self.log.warn('can not found [] in decodeData:%s' % decodeData)
        else:
            self.log.warn('can not fount filter_result with data: .')

        return imgList
