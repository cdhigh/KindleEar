#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""app的配置文件"""

SrcEmail = "akindleear@gmail.com"  #邮件的发件人地址

DEFAULT_MASTHEAD = "mh_default.gif" #如果书籍没有题图，则使用此题图。
DEFAULT_COVER = "cv_default.jpg" #如果书籍没有封面，则使用此封面，留空则不添加封面
TIMEZONE = 8 #默认时区

OWNFEEDS_TITLE = 'KindleEar' #自定义RSS的默认标题，后续可以在网页上修改
OWNFEEDS_DESC = 'RSS delivering from KindleEar'

PINYIN_FILENAME = False # True则发送邮件的文件名转换为拼音（如果是汉字的话）

#True则每篇文章都自动检测编码，这会减慢一些处理速度，但是一般不会导致乱码
#False则先使用上一篇文章的编码进行解码，如果失败再检测此文章编码，一般来说
#不会导致乱码，并且处理性能好很多，如果有部分文章出现乱码，则需要设置此选项为True
ALWAYS_CHAR_DETECT = False

#是否使用异步方式获取RSS文章，好处是效率比较高，可以在GAE的限额10分钟内处理
#更多的RSS订阅源，缺点就是没有了失败重试和重定向COOKIE处理功能。
#如果有部分RSS出现Too many redirects异常，则建议设置为False
#如果你的RSS订阅源不多，GAE的Logs内没有DeadlineExceededError异常，也建议设置为False
USE_ASYNC_URLFETCH = True
