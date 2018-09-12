#!/usr/bin/env python
# -*- coding:utf-8 -*-
#http://www.cartoonmad.com网站的漫画的基类，简单提供几个信息实现一个子类即可推送特定的漫画
#Author: insert0003 <https://github.com/insert0003>
import datetime
from bs4 import BeautifulSoup
from config import TIMEZONE
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseComicBook
from apps.dbModels import LastDelivered

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
    
    #使用此函数返回漫画图片列表[(section, title, url, desc),...]
    def ParseFeedUrls(self):
        urls = [] #用于返回
        newComicUrls = self.GetNewComic() #返回[(title, num, url),...]
        if not newComicUrls:
            return []
        
        decoder = AutoDecoder(isfeed=False)
        for title, num, url in newComicUrls:
            if url.startswith( "http://" ):
                url = url.replace('http://', 'https://')

            opener = URLOpener(self.host, timeout=60)
            result = opener.open(url)
            if result.status_code != 200 or not result.content:
                self.log.warn('fetch comic page failed: %s' % url)
                continue
                
            content = result.content
            content = self.AutoDecodeContent(content, decoder, self.page_encoding, opener.realurl, result.headers)
            
            bodySoup = BeautifulSoup(content, 'lxml')
            sel = bodySoup.find('select') #页码行，要提取所有的页面
            ul = sel.find_all('option') if sel else None
            if not ul:
                continue

            for comicPage in ul:
                href = comicPage.get('value')
                if href:
                    pageHref = self.urljoin(url, href)
                    result = opener.open(pageHref)
                    if result.status_code != 200:
                        self.log.warn('fetch comic page failed: %s' % pageHref)
                        continue
                        
                    content = result.content
                    content = self.AutoDecodeContent(content, decoder, self.page_encoding, opener.realurl, result.headers)
                    soup = BeautifulSoup(content, 'lxml')
                    
                    comicImgTag = soup.find('img', {'oncontextmenu': 'return false'})
                    comicSrc = comicImgTag.get('src') if comicImgTag else None
                    if comicSrc:
                        urls.append((title, comicPage.text, comicSrc, None))

            self.UpdateLastDelivered(title, num)
            
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

    #根据已经保存的记录查看连载是否有新的章节，返回章节URL列表
    #返回：[(title, num, url),...]
    def GetNewComic(self):
        urls = []

        if not self.feeds:
            return []
        
        userName = self.UserName()
        decoder = AutoDecoder(isfeed=False)
        for item in self.feeds:
            title, url = item[0], item[1]
            if url.startswith( "http://" ):
                url = url.replace('http://', 'https://')
            
            lastCount = LastDelivered.all().filter('username = ', userName).filter("bookname = ", title).get()
            if not lastCount:
                default_log.info('These is no log in db LastDelivered for name: %s, set to 0' % title)
                oldNum = 0
            else:
                oldNum = lastCount.num
                
            opener = URLOpener(self.host, timeout=60)
            result = opener.open(url)
            if result.status_code != 200:
                self.log.warn('fetch index page for %s failed[%s] : %s' % (title, URLOpener.CodeMap(result.status_code), url))
                continue
            content = result.content
            content = self.AutoDecodeContent(content, decoder, self.feed_encoding, opener.realurl, result.headers)
            
            soup = BeautifulSoup(content, 'lxml')
            
            allComicTable = soup.find_all('table', {'width': '800', 'align': 'center'})
            addedForThisComic = False
            for comicTable in allComicTable:
                comicVolumes = comicTable.find_all('a', {'target': '_blank'})
                for volume in comicVolumes:
                    texts = volume.text.split(' ')
                    if len(texts) > 2 and texts[1].isdigit() and volume.get('href'):
                        num = int(texts[1])
                        if num > oldNum:
                            oldNum = num
                            href = self.urljoin(self.host, volume.get('href'))
                            urls.append((title, num, href))
                            addedForThisComic = True
                            break #一次只推送一卷（有时候一卷已经很多图片了）
                            
                if addedForThisComic:
                    break
                    
        return urls

