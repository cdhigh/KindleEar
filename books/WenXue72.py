#!/usr/bin/env python
# -*- coding:utf-8 -*-

from base import BaseFeedBook  # 继承基类BaseFeedBook
from lib.urlopener import URLOpener  # 导入请求URL获取页面内容的模块
from bs4 import BeautifulSoup  # 导入BeautifulSoup处理模块
from bs4 import element

# 返回此脚本定义的类名
def getBook():
    return WenXue72

# 继承基类BaseFeedBook
class WenXue72(BaseFeedBook):
    # 设定生成电子书的元数据
    title = u'追网文最新章节(72文学)'  # 设定标题
    description = u'在72文学网站追书，每本书只获取最新章节'  # 设定简介
    language = 'zh-cn'  # 设定语言

    # 指定要提取的包含文章列表的主题页面链接
    # 每个主题是包含主题名和主题页面链接的元组
    feeds = [
        (u'芝加哥1990', 'https://www.72wx.com/wenxue/23636/'),
        (u'我真没想重生啊', 'https://www.72wx.com/wenxue/25304/'),
        (u'我拍戏不在乎票房', 'https://www.72wx.com/wenxue/75487/'),
        (u'穿越八年才出道', 'https://www.72wx.com/wenxue/89019/'),
    ]

    fulltext_by_readability = False  # 设定手动解析网页

    coverfile = 'cv_WenXue72.jpg'  # 设定封面图片

    # 设定内容页需要保留的标签
    keep_only_tags = [
        dict(name='div', class_='bookname'),
        dict(name='div', id='content'),
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
                item = soup.find(name='dd')
                count = 0
                while item:
                    # 只获取最新更新章节
                    if item.name != 'dd':
                        break
                    title = item.a.string  # 获取文章标题
                    link = item.a.get('href')  # 获取文章链接
                    link = BaseFeedBook.urljoin(
                        "https://www.72wx.com", link)  # 合成文章链接
                    urls.insert(0, (topic, title, link, None))  # 把文章元组加入列表
                    count = count + 1
                    if count >= 20:
                        break
                    item = item.next_sibling
                    while type(item) != element.Tag:
                        item = item.next_sibling
            # 如果请求失败通知到日志输出中
            else:
                self.log.warn('Fetch article failed(%s):%s' %
                              (URLOpener.CodeMap(result.status_code), url))
        # 返回提取到的所有文章列表
        return urls

    def postprocess(self, content):
        # 去除网站嵌入文字广告
        replacedContent = content.replace(u'72文学网首发 www.（72wx）.comm.72wx.coma', ''). \
            replace(u'无广告72文学网am~w~w.7~2~w~x.c~o~m', ''). \
            replace(u'天才一秒钟就记住：(www).72wx.com 72文学', ''). \
            replace(u'72文学网首发 https://www.72wx.com', ''). \
            replace(u'更新最快的72文学网w~w~w.7~2~w~x.c~o~m', '')

        # 将页面内容转换成BeatifulSoup对象
        soup = BeautifulSoup(replacedContent, 'html.parser')

        # 清除文章导航
        tag = soup.find(name="div", class_="bottem1")
        if tag:
            tag.decompose()

        # 清除推荐
        tag = soup.find(name="div", class_="lm")
        if tag:
            tag.decompose()

        return unicode(soup)

    # 清理文章URL附带字符
    def processtitle(self, title):
        return title.replace(u'_72文学', '')
