#!/usr/bin/env python
# -*- coding:utf-8 -*-

from base import BaseFeedBook # 继承基类BaseFeedBook
from lib.urlopener import URLOpener # 导入请求URL获取页面内容的模块
from bs4 import BeautifulSoup # 导入BeautifulSoup处理模块
from bs4 import element
from config import SHARE_FUCK_GFW_SRV
import urllib
import string

# 返回此脚本定义的类名
def getBook():
    return KFTouTiao

# 继承基类BaseFeedBook
class KFTouTiao(BaseFeedBook):
    # 设定生成电子书的元数据
    title = u'开发者头条' # 设定标题
    __author__ = u'开发者头条' # 设定作者
    description = u'开发者头条是热门的技术新闻' # 设定简介
    language = 'zh-cn' # 设定语言

    # 指定要提取的包含文章列表的主题页面链接
    # 每个主题是包含主题名和主题页面链接的元组
    feeds = [
        (u'最近90天热门文章', 'https://toutiao.io/posts/hot/90'),
        (u'今日头条', 'https://toutiao.io/'),
    ]

    feed_encoding = "utf-8"
    page_encoding = 'utf-8' # 设定待抓取页面的页面编码
    fulltext_by_readability = False # 设定手动解析网页

    coverfile = 'cv_kftoutiao.jpg' # 设定封面图片

    http_headers = { 'Accept': '*/*','Connection': 'keep-alive', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.116 Safari/537.36'}

    def url4forwarder(self, url):
        ' 生成经过转发器的URL '
        return SHARE_FUCK_GFW_SRV % urllib.quote(url)

    def getRealUrl (self, url, try_count = 1):
        if try_count > 3:
            return url
        try:
            opener = URLOpener(self.host, timeout=self.timeout)
            result = opener.open(url, None, self.http_headers)
            if result.status_code > 400:
                return self.getRealUrl(url, try_count + 1)
            else:
                return opener.realurl
        except:
            return self.getRealUrl(url, try_count + 1)

    # 提取每个主题页面下所有文章URL
    def ParseFeedUrls(self):
        urls = [] # 定义一个空的列表用来存放文章元组
        # 循环处理fees中两个主题页面
        for feed in self.feeds:
            # 分别获取元组中主题的名称和链接
            topic, url = feed[0], feed[1]
            # 请求主题链接并获取相应内容
            opener = URLOpener(self.host, timeout=self.timeout)
            result = opener.open(url)
            # 如果请求成功，并且页面内容不为空
            if result.status_code == 200 and result.content:
                # 将页面内容转换成BeatifulSoup对象
                soup = BeautifulSoup(result.content, 'html.parser')
                # self.log.warn('title : %s' % soup.title)
                # 找出当前页面文章列表中所有文章条目'
                items = soup.find_all(name='div', class_="content")
                self.log.warn('find : %d articles.' % len(items))
                # 循环处理每个文章条目
                count = 0
                for item in items:
                    title = item.a.string # 获取文章标题
                    link = item.a.get('href') # 获取文章链接
                    link = BaseFeedBook.urljoin("https://toutiao.io", link) # 合成文章链接
                    link = self.getRealUrl (link)
                    self.log.warn('Fetch article : %s' % link)
                    if string.find (link, 'zhihu.com') != -1:
                        link = self.url4forwarder(url)
                        self.log.warn('transport : %s' % link)                        
                    urls.append((topic, title, link, None)) # 把文章元组加入列表
                    count = count + 1
                    if count >= 30 :
                        break
            # 如果请求失败通知到日志输出中
            else:
                self.log.warn('Fetch article failed(%s):%s' % \
                    (URLOpener.CodeMap(result.status_code), url))
        # 返回提取到的所有文章列表
        return urls

    # 在文章内容被正式处理前做一些预处理
    def preprocess(self, content):
        # 将页面内容转换成BeatifulSoup对象
        soup = BeautifulSoup(content, 'html.parser')

        self.keep_only_tags = []
        tag = soup.find (attrs={"property":"og:site_name"})
        if tag :
            siteName = tag['content']
            # 对微信公众号文章做清洗
            if siteName:
                if siteName == u'微信公众平台' :
                    #self.log.warn("it's WeChat article.")
                    # 需要填充title字段，否则微信公众号文章会没有标题
                    soup.title.string = soup.find (attrs={"property":"og:title"})['content']

                    self.keep_only_tags = [
                        dict(name='div', id="img-content", class_='rich_media_wrp'),
                        dict(name='div', id="js_content", class_='rich_media_content'),
                    ]

                    # 清除隐藏信息
                    tags = soup.find_all (name="div", style="display:none;")
                    for tag in tags:
                        tag.decompose () 

                    tags = soup.find_all (name="div", style="display: none;")
                    for tag in tags:
                        tag.decompose ()  

                    return unicode(soup)

                # 处理ThoughtWorks洞见文章
                elif siteName == u'ThoughtWorks洞见':
                    self.keep_only_tags = [
                        dict(name='div', class_='entry-wrap'),
                    ]
                    return content
        
        # 处理codingstyle文章
        tag = soup.find (name='link', rel='alternate')
        if tag :
            herfLink = tag['href']
            if herfLink and string.find (herfLink, 'codingstyle') != -1:
                self.keep_only_tags = [
                    dict(name='div', class_='topic-detail'),
                ]
                return content

        # 处理开发者头条文章
        title = soup.title.string
        if title and string.find (title, u'开发者头条') != -1 :
            self.keep_only_tags = [
                dict(name='div', class_='content'),
                dict(name='div', class_='preview'),
            ]
            return content

        return content


        