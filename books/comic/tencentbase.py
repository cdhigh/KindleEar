#!/usr/bin/env python3
# encoding: utf-8
#http://ac.qq.com或者http://m.ac.qq.com网站的免费漫画的基类，简单提供几个信息实现一个子类即可推送特定的漫画
import re, urlparse, json, datetime, base64
from time import sleep
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
            comic_id = ""
            
            lastCount = LastDelivered.all().filter('username = ', userName).filter("bookname = ", title).get()
            if not lastCount:
                default_log.info('These is no log in db LastDelivered for name: %s, set to 0' % title)
                oldNum = 0
            else:
                oldNum = lastCount.num

            urlpaths = urlparse.urlsplit(url.lower()).path.split("/")
            if ( (u"id" in urlpaths) and (urlpaths.index(u"id")+1 < len(urlpaths)) ):
                comic_id = urlpaths[urlpaths.index(u"id")+1]

            if ( (not comic_id.isdigit()) or (comic_id=="") ):
                self.log.warn('can not get comic id: %s' % url)
                break

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
        chapterList = []

        getChapterListUrl = 'http://m.ac.qq.com/GetData/getChapterList?id={}'.format(comic_id)
        result = opener.open(getChapterListUrl)
        if result.status_code != 200 or not result.content:
            self.log.warn('fetch comic page failed: %s' % url)
            return chapterList

        content = result.content
        content = self.AutoDecodeContent(content, decoder, self.page_encoding, opener.realurl, result.headers)

        contentJson = json.loads(content)
        count = contentJson.get('length', 0)
        if (count != 0):
            for i in range(count + 1):
                for item in contentJson:
                    if isinstance(contentJson[item], dict) and contentJson[item].get('seq') == i:
                        chapterList.append({item: contentJson[item]})
                        break
        else:
            self.log.warn('comic count is zero.')

        return chapterList

    #获取漫画图片列表
    def getImgList(self, chapterJson, comic_id):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host, timeout=60)
        imgList = []

        cid = list(chapterJson.keys())[0]
        getImgListUrl = 'http://ac.qq.com/ComicView/index/id/{0}/cid/{1}'.format(comic_id, cid)
        result = opener.open(getImgListUrl)
        if result.status_code != 200 or not result.content:
            self.log.warn('fetch comic page failed: %s' % url)
            return imgList

        content = result.content
        cid_page = self.AutoDecodeContent(content, decoder, self.page_encoding, opener.realurl, result.headers)
        filter_result = re.findall(r"data\s*:\s*'(.+?)'", cid_page)
        if len(filter_result) != 0:
            base64data = filter_result[0][1:]
            img_detail_json = json.loads(base64.decodestring(base64data))
            for img_url in img_detail_json.get('picture', []):
                if ( 'url' in img_url ):
                    imgList.append(img_url['url'])
                else:
                    self.log.warn('no url in img_url:%s' % img_url)

        return imgList
