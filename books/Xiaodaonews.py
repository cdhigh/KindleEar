#!/usr/bin/env python
# -*- coding:utf-8 -*-
from weixinbase import WeixinBook

def getBook():
    return Xiaodaonews

class Xiaodaonews(WeixinBook):
    title                 = u'微信公众号：小道消息'
    description           = u'只有小道消息才能拯救中国互联网'
    language              = 'zh-cn'
    feed_encoding         = "utf-8"
    page_encoding         = "utf-8"
    oldest_article        = 7
    deliver_days = ['Friday']
    feeds = [
            (u'小道消息', 'http://weixin.sogou.com/gzh?openid=oIWsFt86NKeSGd_BQKp1GcDkYpv0'),
            ]
