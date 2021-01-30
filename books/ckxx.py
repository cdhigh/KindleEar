#!/usr/bin/env python
# -*- coding:utf-8 -*-

from base import BaseFeedBook  # 继承基类BaseFeedBook
from lib.urlopener import URLOpener  # 导入请求URL获取页面内容的模块
from bs4 import BeautifulSoup  # 导入BeautifulSoup处理模块
import re
from bs4 import element

# 返回此脚本定义的类名
def getBook():
    return CKXX

# 继承基类BaseFeedBook
class CKXX(BaseFeedBook):
    # 设定生成电子书的元数据
    title = u'参考消息要闻'  # 设定标题
    description = u'参考消息头版要闻'  # 设定简介
    language = 'zh-cn'  # 设定语言

    # 指定要提取的包含文章列表的主题页面链接
    # 每个主题是包含主题名和主题页面链接的元组
    feeds = [
        (u'参考消息要闻', 'http://www.cankaoxiaoxi.com/'),
    ]

    feed_encoding = "utf-8"
    page_encoding = 'utf-8'  # 设定待抓取页面的页面编码
    fulltext_by_readability = False  # 设定手动解析网页

    coverfile = 'cv_ckxx.jpg'  # 设定封面图片

    # 设定内容页需要保留的标签
    keep_only_tags = [
        dict(class_='articleHead'),
        dict(name='div', class_='articleContent'),
    ]

    # 提取每个主题页面下所有文章URL
    def ParseFeedUrls(self):
        urls = []  # 定义一个空的列表用来存放文章元组
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
                # 找出当前页面文章列表中所有文章条目'
                sections = soup.find_all(name='div', class_='column-news')
                # self.log.warn('find %d sections' % len(sections))
                for section in sections:
                    tag = section.find (name='ul', class_='column-title')
                    sectionName = tag.a.li.string
                    tuwens = section.find_all (name='div', class_=re.compile("tuwen-block-"))   
                    # self.log.warn('%s find %d tuwen' % (sectionName, len(tuwens)))
                    for tuwen in tuwens:
                        articles = tuwen.find_all ('a')
                        title = ''
                        link = ''
                        for article in articles:
                            if not article.img:
                                title = article.string
                                link = article.get('href')  # 获取文章链接
                                self.log.warn('title : %s, link: %s' % (title, link))
                                break
                        urls.append((sectionName, title, link, None))  # 把文章元组加入列表
                    texts = section.find_all (name='li', class_=re.compile("list-text-")) 
                    # self.log.warn('%s find %d texts' % (sectionName, len(texts)))  
                    for text in texts:                       
                        title = text.a.string
                        link = text.a.get('href')  # 获取文章链接
                        self.log.warn('title : %s, link: %s' % (title, link))
                        urls.append((sectionName, title, link, None))  # 把文章元组加入列表

            # 如果请求失败通知到日志输出中
            else:
                self.log.warn('Fetch article failed(%s):%s' %
                              (URLOpener.CodeMap(result.status_code), url))
        # 返回提取到的所有文章列表
        return urls

    # 清理文章URL附带字符
    def processtitle(self, title):
        return title.replace(u'_《参考消息》官方网站', '')