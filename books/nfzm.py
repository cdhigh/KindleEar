#!/usr/bin/env python
# -*- coding:utf-8 -*-
from bs4 import BeautifulSoup
from base import BaseFeedBook, string_of_tag
from urllib import URLopener

EMAIL    = ""    # 南方周末注册邮箱
PASSWORD = ""    # 南方周末登录密码


def getBook():
    return NFZM


class NFZM(BaseFeedBook):
    title           = u'南方周末'
    description     = u'在这里读懂中国 | 每周五更新 | 订阅前请在books/nfzm.py填写账号密码'
    language        = 'zh-cn'
    feed_encoding   = "utf-8"
    page_encoding   = "utf-8"
    mastheadfile    = "mh_nfzm.gif"
    coverfile       = "cv_nfzm.jpg"
    deliver_days    = ['Friday']

    def ParseFeedUrls(self):
        login_url = "http://passport.infzm.com/passport/login"
        content_url = "http://www.infzm.com/enews/infzm"
        urls = []
        opener = URLopener()
        cookie = opener.open(login_url, data="loginname=%s&password=%s" %
                             (EMAIL, PASSWORD)).headers.getheader("Set-Cookie")
        opener.addheader("Cookie", cookie)
        result = opener.open(content_url)
        content = result.read().decode(self.feed_encoding)
        soup = BeautifulSoup(content, "lxml")
        sec_titles = []
        for sec_name in soup.find_all('h2'):
            sec_titles.append(sec_name.get_text())
        for top_news in soup.find_all('dl', {'class': 'topnews'}):
            url = top_news.a['href']
            feed_content = opener.open(url).read().decode(self.feed_encoding)
            feed_soup = BeautifulSoup(feed_content, "lxml")
            urls.append(
                (sec_titles[0], top_news.a['title'], url, feed_soup.find(id="articleContent")))
        sec_count = 0
        for sec_content in soup.find_all('ul', {'class': 'relnews'}):
            for a in sec_content.find_all('a'):
                url = a['href']
                feed_content = opener.open(
                    url).read().decode(self.feed_encoding)
                feed_soup = BeautifulSoup(feed_content, "lxml")
                urls.append(
                    (sec_titles[sec_count], a['title'], url, feed_soup.find(id="articleContent")))
            sec_count += 1
        return urls
