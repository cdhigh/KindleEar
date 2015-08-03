#!/usr/bin/env python
# -*- coding:utf-8 -*-
#通过搜狗微信搜索实现特定公众号文章爬取并推送至Kindle
#或者你可以作者(zhu327)的 <https://diy-devz.rhcloud.com/> 来将微信公众号转换为RSS在KindleEar中直接订阅
#Author:
# zhu327 <https://github.com/zhu327>

import datetime, json, re, time, urlparse, urllib
import lxml.html, lxml.etree
from lib import feedparser
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from lib.weixin import process_eqs
from base import BaseFeedBook

WEIXIN_URL = 'http://weixin.sogou.com/gzhjs?cb=sogou.weixin.gzhcb&openid={id}&eqs={eqs}&ekv={ekv}&page=1&t={t}'

class WeixinBook(BaseFeedBook):

    #继承自BaseFeedBook，参数填写参考BaseFeedBook的注释

    #每个子类必须重新定义这个属性，为搜狗微信公众搜索地址，例：http://weixin.sogou.com/gzh?openid=oIWsFt6yAL253-qrm9rkdugjSlOY
    #每个链接格式为元组：(分节标题, URL)
    #注意，如果分节标题是中文的话，增加u前缀，比如
    #(u'沪江英语', 'http://weixin.sogou.com/gzh?openid=oIWsFt6yAL253-qrm9rkdugjSlOY'),
    feeds = []

    def preprocess(self, html):
        root = lxml.html.fromstring(html)
    
        # 抽取封面cover图片
        script = root.xpath('//*[@id="media"]/script/text()')
        cover = None
        if script:
            l = _COVER_RE.findall(script[0])
            if l:
                cover = l[0]

        # 抽取文章内容
        try:
            content = root.xpath('//*[@id="js_content"]')[0]
        except IndexError:
            return ''

        # 处理图片链接
        for img in content.xpath('.//img'):
            if not 'src' in img.attrib:
                img.attrib['src'] = img.attrib.get('data-src', '')

        # 生成封面
        if cover:
            coverelement = lxml.etree.Element('img')
            coverelement.set('src', cover)
            content.insert(0, coverelement)

        return lxml.html.tostring(content, encoding='unicode')

    def ParseFeedUrls(self):
        """ return list like [(section,title,url,desc),..] """
        urls = []
        tnow = datetime.datetime.utcnow()
        urladded = set()

        for feed in self.feeds:
            section, url = feed[0], feed[1]
            isfulltext = feed[2] if len(feed) > 2 else False
            timeout = self.timeout+10 if isfulltext else self.timeout
            opener = URLOpener(self.host, timeout=timeout)

            id = urlparse.urlparse(url).query.split('=')[1]

            result = opener.open(url)
            if result.status_code == 200 and result.content:
                if self.feed_encoding:
                    try:
                        content = result.content.decode(self.feed_encoding)
                    except UnicodeDecodeError:
                        content = AutoDecoder(True).decode(result.content,opener.realurl,result.headers)
                else:
                    content = AutoDecoder(True).decode(result.content,opener.realurl,result.headers)
            else:
                self.log.warn('fetch rss failed(%d):%s'%(result.status_code,url))
                continue
            
            eqs, ekv = process_eqs(content)
            url = WEIXIN_URL.format(id=id, eqs=urllib.quote(eqs), ekv=ekv, t=int(time.time()*1000))

            result = opener.open(url)
            if result.status_code == 200 and result.content:
                if self.feed_encoding:
                    try:
                        content = result.content.decode(self.feed_encoding)
                    except UnicodeDecodeError:
                        content = AutoDecoder(True).decode(result.content,opener.realurl,result.headers)
                else:
                    content = AutoDecoder(True).decode(result.content,opener.realurl,result.headers)
                content = content[content.find('{'):content.rfind('}')+1]
                try:
                    content = json.loads(content)
                except ValueError:
                    continue

                for e in content['items'][:self.max_articles_per_feed]:
                    e = feedparser.parse(e)['entries'][0]
                    updated = None
                    if hasattr(e, 'lastmodified') and e.lastmodified:
                        updated = float(e.lastmodified)

                    if self.oldest_article > 0 and updated:
                        updated = datetime.datetime.utcfromtimestamp(updated)
                        delta = tnow - updated
                        if self.oldest_article > 365:
                            threshold = self.oldest_article #以秒为单位
                        else:
                            threshold = 86400*self.oldest_article #以天为单位

                        if delta.days*86400+delta.seconds > threshold:
                            self.log.info("Skip old article(%s): %s" % (updated.strftime('%Y-%m-%d %H:%M:%S'),e.href))
                            continue

                    #支持HTTPS
                    if hasattr(e, 'href'):
                        if url.startswith('https://'):
                            urlfeed = e.href.replace('http://','https://')
                        else:
                            urlfeed = e.href

                        if urlfeed in urladded:
                            continue
                    else:
                        urlfeed = ''

                    desc = None
                    urls.append((section, e.title, urlfeed, desc))
                    urladded.add(urlfeed)
            else:
                self.log.warn('fetch rss failed(%d):%s'%(result.status_code,url))

        return urls
