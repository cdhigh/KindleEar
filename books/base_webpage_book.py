#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
KindleEar电子书基类，每本投递到kindle的书籍抽象为这里的一个类。
可以继承BaseFeedBook类而实现自己的定制书籍。
cdhigh <https://github.com/cdhigh>
"""
from books.base_book import *

#直接在网页中获取信息的电子书，不经过RSS
class BaseWebpageBook(BaseFeedBook):
    fulltext_by_readability = False

    #生成器，返回电子书中的每一项内容，包括HTML或图像文件，
    #每次返回一个命名元组，可能为 ItemHtmlTuple 或 ItemImageTuple
    def Items(self):
        timeout = self.timeout
        for section, url in self.feeds:
            opener = UrlOpener(self.host, timeout=timeout, headers=self.extra_header)
            result = opener.open(url)
            status_code = result.status_code
            if status_code != 200:
                self.log.warning('Fetch article failed({}):{}'.format(UrlOpener.CodeMap(status_code), url))
                continue
            
            content =  self.PreProcess(result.text)
            soup = BeautifulSoup(content, "lxml")

            headTag = soup.find('head')
            if not head:
                headTag = soup.new_tag('head')
                soup.html.insert(0, headTag)

            titleTag = headTag.find('title')
            if titleTag:
                title = titleTag.string
            else:
                title = section
                t = soup.new_tag('title')
                t.string = section
                headTag.append(t)
            
            title = self.ProcessTitle(title)

            #根据书籍 keep_only_tags 属性，创建一个新的 body 标签替代原先的
            bodyTag = self.BuildNewSoupBody(soup) if self.keep_only_tags else soup.find("body")
                
            #根据书籍内置remove_xxx 属性，清理一些元素
            self.removeSoupElements(soup)

            #添加额外的CSS
            if self.AddCustomCss(soup):
                yield ItemCssTuple("custom.css", "custom.css", user.css_content)

            #逐个处理文章内的图像链接，生成对应的图像文件
            thumbnailUrl = None
            for imgManifest in self.PrepareImageManifest(soup, url):
                if not thumbnailUrl and imgManifest.isThumbnail:
                    thumbnailUrl = imgManifest.url
                yield imgManifest

            self.PostProcess(soup)

            #提取文章内容的前面一部分做为摘要，[漫画模式不需要摘要]
            brief = self.ExtractBrief(soup)
            yield ItemHtmlTuple(section, url, title, soup, brief, thumbnailUrl)
            
