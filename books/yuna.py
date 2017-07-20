#!/usr/bin/env python
# -*- coding:utf-8 -*-
import imghdr

from bs4 import BeautifulSoup
from base import BaseFeedBook, URLOpener

def getBook():
    return Yuna

class Yuna(BaseFeedBook):
    title               = u'摇曳庄的幽奈小姐'
    description         = u'三浦忠弘（ミウラタダヒロ）创作，2016年2月8日开始连载于《周刊少年JUMP》上的漫画'
    language            = 'zh-tw'
    feed_encoding       = "big5"
    page_encoding       = "big5"
    mastheadfile        = "mh_comic.gif"
    coverfile           = 'cv_yuna.jpg'

    def Items(self, opts=None, user=None):
        """
        生成器，返回一个图片元组，mime,url,filename,content,brief,thumbnail
        """
        urls = self.ParseFeedUrls()
        opener = URLOpener(self.host, timeout=self.timeout, headers=self.extra_header)
        for section, ftitle, url, desc in urls:
            opener = URLOpener(self.host, timeout=self.timeout, headers=self.extra_header)
            result = opener.open(url)
            article = result.content 
            if not article:
                continue
           
            imgtype = imghdr.what(None, article)
            imgmime = r"image/" + imgtype
            fnimg = "img%d.%s" % (self.imgindex, 'jpg' if imgtype=='jpeg' else imgtype)
            yield (imgmime, url, fnimg, article, None, None)
           
            tmphtml = '<html><head><title>Picture</title></head><body><img src="%s" /></body></html>' % fnimg
            yield (section, url, ftitle, tmphtml, '', None)

    def ParseFeedUrls(self):
        mainurl = "http://www.cartoonmad.com/comic/4897.html"
        title = '摇曳庄的幽奈小姐'.decode("utf")

        
        href = self.GetNewComic(title, mainurl)
        if href == "":
            return []

        return self.GetComicUrls(title, href)

