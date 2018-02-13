#!/usr/bin/env python3
# encoding: utf-8
#http://ac.qq.com或者http://m.ac.qq.com网站的免费漫画的基类，简单提供几个信息实现一个子类即可推送特定的漫画
import datetime
import json
from time import sleep
import re
from config import TIMEZONE
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseComicBook
from apps.dbModels import LastDelivered


class TencentBaseBook(BaseComicBook):
    title               = u''
    description         = u''
    language            = ''
    feed_encoding       = ''
    page_encoding       = ''
    mastheadfile        = ''
    coverfile           = ''
    host                = 'http://m.ac.qq.com'
    feeds               = [] #子类填充此列表[('name', mainurl),...]

    #使用此函数返回漫画图片列表[(section, title, url, desc),...]
    def ParseFeedUrls(self):
        urls = [] #用于返回
        
        userName = self.UserName()
        for item in self.feeds:
            title, url = item[0], item[1]
            
            lastCount = LastDelivered.all().filter('username = ', userName).filter("bookname = ", title).get()
            if not lastCount:
                default_log.info('These is no log in db LastDelivered for name: %s, set to 0' % title)
                oldNum = 0
            else:
                oldNum = lastCount.num

            comic_id = url.split("/")[6]
            chapterList = self.getChapterList(comic_id)
            for deliverCount in range(5):
                newNum = oldNum + deliverCount
                if newNum < len(chapterList):
                    imgList = self.getImgList(chapterList[newNum], comic_id)
                    for img in imgList:
                        urls.append((title, img, img, None))
                    self.UpdateLastDelivered(title, newNum+1)
                    if newNum == 0:
                        break

        return urls

    #更新已经推送的卷序号到数据库
    def UpdateLastDelivered(self, title, num):
        userName = self.UserName()
        dbItem = LastDelivered.all().filter('username = ', userName).filter('bookname = ', title).get()
        self.last_delivered_volume = u' 第%d话' % num
        if dbItem:
            dbItem.num = num
            dbItem.record = self.last_delivered_volume
            dbItem.datetime = datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE)
        else:
            dbItem = LastDelivered(username=userName, bookname=title, num=num, record=self.last_delivered_volume,
                datetime=datetime.datetime.utcnow() + datetime.timedelta(hours=TIMEZONE))
        dbItem.put()

    #获取漫画章节列表
    def getChapterList(self, comic_id):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host, timeout=60)

        getChapterListUrl = 'http://m.ac.qq.com/GetData/getChapterList?id={}'.format(comic_id)
        result = opener.open(getChapterListUrl)
        if result.status_code != 200 or not result.content:
            self.log.warn('fetch comic page failed: %s' % url)
            return None
            
        content = result.content
        content = self.AutoDecodeContent(content, decoder, self.page_encoding, opener.realurl, result.headers)

        contentJson = json.loads(content)
        count = contentJson['length']
        chapterList = []
        for i in range(count + 1):
            for item in contentJson:
                if isinstance(contentJson[item], dict) and contentJson[item].get('seq') == i:
                    chapterList.append({item: contentJson[item]})
                    break
        return chapterList

    #获取漫画图片列表
    def getImgList(self, chapterJson, comic_id):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host, timeout=60)
        
        cid = list(chapterJson.keys())[0]
        getImgListUrl = 'http://ac.qq.com/ComicView/index/id/{0}/cid/{1}'.format(comic_id, cid)
        result = opener.open(getImgListUrl)
        if result.status_code != 200 or not result.content:
            self.log.warn('fetch comic page failed: %s' % url)
            return None
            
        content = result.content
        cid_page = self.AutoDecodeContent(content, decoder, self.page_encoding, opener.realurl, result.headers)

        base64data = re.findall(r"data\s*:\s*'(.+?)'", cid_page)[0][1:]
        img_detail_json = json.loads(self.__decode_base64_data(base64data))
        imgList = []
        for img_url in img_detail_json.get('picture'):
            imgList.append(img_url['url'])
        return imgList

    #漫画Base64解码数据
    def __decode_base64_data(self, base64data):
        base64DecodeChars = [- 1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
                            -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 62, -1, -1, -1,
                            63, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -1, -1, -1, -1, -1, -1, -1, 0, 1, 2, 3, 4, 5, 6, 7,
                            8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, -1, -1, -1, -1, -1,
                            26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49,
                            50, 51, -1, -1, -1, -1, -1]
        data_length = len(base64data)
        i = 0
        out = ""
        c1 = c2 = c3 = c4 = 0
        while i < data_length:
            while True:
                c1 = base64DecodeChars[ord(base64data[i]) & 255]
                i += 1
                if not (i < data_length and c1 == -1):
                    break
            if c1 == -1:
                break
            while True:
                c2 = base64DecodeChars[ord(base64data[i]) & 255]
                i += 1
                if not (i < data_length and c2 == -1):
                    break
            if c2 == -1:
                break
            out += chr(c1 << 2 | (c2 & 48) >> 4)
            while True:
                c3 = ord(base64data[i]) & 255
                i += 1
                if c3 == 61:
                    return out
                c3 = base64DecodeChars[c3]
                if not (i < data_length and c3 == - 1):
                    break
            if c3 == -1:
                break
            out += chr((c2 & 15) << 4 | (c3 & 60) >> 2)
            while True:
                c4 = ord(base64data[i]) & 255
                i += 1
                if c4 == 61:
                    return out
                c4 = base64DecodeChars[c4]
                if not (i < data_length and c4 == - 1):
                    break
            out += chr((c3 & 3) << 6 | c4)
        return out

