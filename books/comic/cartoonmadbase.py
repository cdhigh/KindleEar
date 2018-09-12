#!/usr/bin/env python
# -*- coding:utf-8 -*-
#http://www.cartoonmad.com网站的漫画的基类，简单提供几个信息实现一个子类即可推送特定的漫画
#Author: insert0003 <https://github.com/insert0003>
from bs4 import BeautifulSoup
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseComicBook

class CartoonMadBaseBook(BaseComicBook):
    title               = u''
    description         = u''
    language            = ''
    feed_encoding       = ''
    page_encoding       = ''
    mastheadfile        = ''
    coverfile           = ''
    host                = 'https://www.cartoonmad.com'
    feeds               = [] #子类填充此列表[('name', mainurl),...]
    
    #获取漫画章节列表
    def getChapterList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host, timeout=60)
        chapterList = []

        if url.startswith( "http://" ):
            url = url.replace('http://', 'https://')
            
        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn('fetch comic page failed: %s' % url)
            return chapterList

        content = self.AutoDecodeContent(result.content, decoder, self.feed_encoding, opener.realurl, result.headers)

        soup = BeautifulSoup(content, 'lxml')
            
        allComicTable = soup.find_all('table', {'width': '800', 'align': 'center'})
        for comicTable in allComicTable:
            comicVolumes = comicTable.find_all('a', {'target': '_blank'})
            for volume in comicVolumes:
                href = self.urljoin(self.host, volume.get('href'))
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

        content = self.AutoDecodeContent(result.content, decoder, self.page_encoding, opener.realurl, result.headers)
        soup = BeautifulSoup(content, 'lxml')
        sel = soup.find('select') #页码行，要提取所有的页面
        ulist = sel.find_all('option') if sel else None
        if not ulist:
            return imgList

        for ul in ulist:
            if ul.get('value') == None:
                ulist.remove(ul)

        listLen = len(ulist)
        firstPageTag = soup.find('img', {'oncontextmenu': 'return false'})
        firstPage = firstPageTag.get('src') if firstPageTag else None

        if firstPage != None:
            base, length, type = self.getImgStr(firstPage)
            for index in range(len(ulist)):
                imgUrl = "{}{}.{}".format(base, str(index+1).zfill(length), type)
                imgList.append(imgUrl)
        
        if imgList[0] == firstPage and imgList[listLen-1] == self.getImgUrl(ulist[listLen-1].get('value')):
            return imgList
        else:
            imgList = []
            for ul in ulist:
                imgList.append(self.getImgUrl(ul.get('value')))
            return imgList

        return imgList

    #获取漫画图片网址
    def getImgUrl(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host, timeout=60)

        url = self.host + "/comic/" + url
        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn('fetch comic page failed: %s' % url)
            return None

        content = self.AutoDecodeContent(result.content, decoder, self.page_encoding, opener.realurl, result.headers)
        soup = BeautifulSoup(content, 'lxml')
        comicImgTag = soup.find('img', {'oncontextmenu': 'return false'})
        return comicImgTag.get('src') if comicImgTag else None

    #获取漫画图片格式
    def getImgStr(self, url):
        urls = url.split("/")
        tail = urls[len(urls)-1]
        imgIndex = tail.split(".")[0]
        imgType = tail.split(".")[1]
        base = url.replace(tail, "")
        return base, len(imgIndex), imgType
