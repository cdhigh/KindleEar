#!/usr/bin/env python
# -*- coding:utf-8 -*-

from base import BaseFeedBook # 继承基类BaseFeedBook
from lib.urlopener import URLOpener # 导入请求URL获取页面内容的模块
from bs4 import BeautifulSoup # 导入BeautifulSoup处理模块
from bs4 import element

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

    # 设定内容页需要保留的标签
    # keep_only_tags = [
    #     dict(name='rich_media_title', class_='js_content'),
    #     dict(name='rich_media_conetent', id='js_content'),
    # ]

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
                    # self.log.warn('Fetch article : %s' % link)
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

        siteNameTag = soup.find (attrs={"property":"og:site_name"})
        if siteNameTag :
            siteName = siteNameTag['content']
            # 对微信公众号文章做清洗
            if siteName and siteName == u'微信公众平台' :
                #self.log.warn("it's WeChat article.")
                # 需要填充title字段，否则微信公众号文章会没有标题
                soup.title.string = soup.find (attrs={"property":"og:title"})['content']
                # 清除后面的“喜欢此内容的人还喜欢”
                tag = soup.find (name="div", class_="rich_media_area_extra")
                if tag :
                    tag.decompose ()

                # 清除微信扫码
                tag = soup.find (name="div", class_="qr_code_pc_outer")
                if tag :
                    tag.decompose ()

                # 清除文章标签
                tag = soup.find (name="div", class_="article-tag_list")
                if tag :
                    tag.decompose ()
               

                # 清除文章的元数据信息
                tag = soup.find (name="div", class_="rich_media_meta_list")
                if tag :
                    tag.decompose ()
                    
                # 清除打赏信息
                tag = soup.find (name="div", id="js_reward_area")
                if tag :
                    tag.decompose ()

                # 清除工具条信息
                tag = soup.find (name="div", class_="rich_media_tool")
                if tag :
                    tag.decompose ()

                # 清除隐藏信息
                tags = soup.find_all (name="div", style="display:none;")
                for tag in tags:
                    tag.decompose () 

                tags = soup.find_all (name="div", style="display: none;")
                for tag in tags:
                    tag.decompose ()                           

        # 返回预处理完成的内容
        return unicode(soup)



        