#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#http://www.cartoonmad.com网站的漫画的基类，简单提供几个信息实现一个子类即可推送特定的漫画
#Author: insert0003 <https://github.com/insert0003>
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from lib.urlopener import UrlOpener
from books.base_comic_book import BaseComicBook

class CartoonMadBaseBook(BaseComicBook):
    accept_domains = ("http://www.cartoonmad.com", "https://www.cartoonmad.com")
    host = "https://www.cartoonmad.com"

    # 获取漫画章节列表
    def GetChapterList(self, url):
        opener = UrlOpener(self.host, timeout=self.timeout)
        chapterList = []

        url = url.replace('http://', 'https://').replace('/m/', '/')

        result = opener.open(url)
        if result.status_code != 200:
            self.log.warning('Fetch comic page failed: {}'.format(url))
            return chapterList

        soup = BeautifulSoup(result.content, 'lxml')
        allComicTable = soup.find_all('table', {'width': '800', 'align': 'center'})

        if not allComicTable:
            self.log.warn('allComicTable is not exist.')
            return chapterList

        for comicTable in allComicTable:
            comicVolumes = comicTable.find_all('a', {'target': '_blank'})
            if not comicVolumes:
                self.log.warn('comicVolumes is not exist.')
                return chapterList

            for volume in comicVolumes:
                href = urljoin(self.host, volume.get("href"))
                chapterList.append((volume.string, href))

        return chapterList

    #获取漫画图片列表
    def GetImgList(self, url):
        imgList = []

        ulist = self.GetImgUrlList(url)
        if not ulist:
            self.log.warn('can not find img list for : {}'.format(url))
            return imgList

        firstPage = self.GetImgUrl(url)
        if not firstPage:
            self.log.warn('Can not get first image real url : {}'.format(url))
            return imgList

        # https://www.cartoonmad.com/home1/z2r26v3tr17/5582/001/001.jpg
        imgTail = firstPage.split("/")[-1]
        imgLeng = len(imgTail.split(".")[0])
        imgType = "." + imgTail.split(".")[1]
        imgBase = firstPage.replace(imgTail, "")

        imgList.append(firstPage)
        for index in range(len(ulist)):
            imgUrl = "{}{}{}".format(imgBase, str(index + 2).zfill(imgLeng), imgType)
            imgList.append(imgUrl)

        if imgList[0] != firstPage or imgList[-1] != self.getImgUrl(ulist[-1]):
            imgList = []
            for ul in ulist:
                imgList.append(self.getImgUrl(ul))

        return imgList

    #获取漫画图片网址，返回[url,...]
    def GetImgUrlList(self, url):
        imgUrlList = []
        opener = UrlOpener(self.host, timeout=self.timeout)

        result = opener.open(url)
        if result.status_code != 200:
            self.log.warn('Fetch comic page failed: {}'.format(url))
            return None

        soup = BeautifulSoup(result.content, 'lxml')

        sel = soup.find('select') #页码行，要提取所有的页面
        if not sel:
            self.log.warn("Cannot find tag 'select'")
            return None

        ulist = sel.find_all('option')
        if not ulist:
            self.log.warn('Select option is not exist')
            return None

        for ul in ulist:
            if ul.get('value') == None:
                ulist.remove(ul)
            else:
                href = self.host + '/comic/' + ul.get('value')
                imgUrlList.append(href)

        return imgUrlList

    #获取漫画图片链接
    def GetImgUrl(self, url):
        opener = UrlOpener(self.host, timeout=self.timeout)
        result = opener.open(url)
        if result.status_code != 200:
            self.log.warn('fetch comic page failed: {}'.format(url))
            return None

        soup = BeautifulSoup(result.text, 'lxml')
        comicImgTag = soup.find('img', {'oncontextmenu': 'return false'})
        if not comicImgTag:
            self.log.warn('Can not find image href.')
            return None

        imgUrl = self.host + "/comic/" + comicImgTag.get('src')

        headers = {'Referer': url}
        result = opener.open(imgUrl, headers=headers)
        if result.status_code != 200:
            self.log.warn('Can not get real comic url for : {}'.format(url))
            return None

        return result.url
