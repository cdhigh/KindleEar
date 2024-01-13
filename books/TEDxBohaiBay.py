#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#抓取传送门网站http://chuansongme.com/的特定微信公众号文章列表，
#将title/description/feeds稍加修改后即可用于其他公众号
#feeds里也可以直接增加几个账号
import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from lib.urlopener import UrlOpener
from books.base_book import BaseFeedBook, ItemRssTuple

def getBook():
    return TEDxBohaiBay

class TEDxBohaiBay(BaseFeedBook):
    title                 = 'TED渤海湾'
    description           = '推送最新的TED内容，来自传送门抓取的TEDxBohaiBay微信公众账号文章'
    language              = 'en' #TED中英文双语，为en则能英文查词
    masthead_file         = "mh_chuansongme.gif"
    cover_file            = "cv_chuansongme.jpg"
    oldest_article        = 1
    #设置为True排版也很好（往往能更好的剔除不相关内容），
    #除了缺少标题下的第一幅图
    fulltext_by_readability = False
    keep_only_tags = [dict(name='div', attrs={'id':'page-content'})]
    remove_classes = ['page-toolbar']

    feeds = [
            ('TED渤海湾', 'http://chuansongme.com/account/tedxbohaibay'),
           ]

    #返回一个 ItemRssTuple 列表，里面包含了接下来需要抓取的链接或描述
    def ParseFeedUrls(self):
        urls = []
        for feed in self.feeds:
            feedTitle, url = feed[0], feed[1]
            opener = UrlOpener(self.host, timeout=self.timeout)
            result = opener.open(url)
            if result.status_code != 200:
                self.log.warning('fetch webpage failed({}):{}'.format(result.status_code, url))
                continue

            soup = BeautifulSoup(result.text, 'lxml')
            for article in soup.find_all('div', attrs={'class': 'feed_item_question'}):
                title = article.find('a', attrs={'class': 'question_link'})
                if not title:
                    continue

                #获取发布时间
                pubDate = article.find('span', attrs={'class': 'timestamp'})
                if not pubDate:
                    continue

                try:
                    pubDate = datetime.datetime.strptime(pubDate.string, '%Y-%m-%d')
                except Exception as e:
                    self.log.warning('Parse pubdate failed for [{}]: {}'.format(url, pubDate.string))
                    continue

                #确定文章是否需要推送，时区固定为北京时间
                tNow = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
                delta = tNow - pubDate
                if self.oldest_article > 0 and delta.days > self.oldest_article:
                    continue

                href = title['href'] if title['href'].startswith('http') else urljoin(url, title['href'])

                urls.append(ItemRssTuple(feedTitle, title.get_text(), href, ""))

        return urls

    def ProcessBeforeImage(self, soup):
        #去掉第一个图片“旋转圈”
        img = soup.body.find('img',attrs={'src':True})
        if img and 'loading' in img['src']:
            img.decompose()
