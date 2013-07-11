#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""app的配置文件"""

SrcEmail = "akindleear@gmail.com"  #邮件的发件人地址

DEFAULT_COVER = "cv_default.jpg" #如果书籍没有封面，则使用此封面，留空则不添加封面
TIMEZONE = 8 #管理员的时区

OWNFEEDS_TITLE = 'KindleEar' #自定义RSS的默认标题，后续可以在网页上修改
OWNFEEDS_DESC = 'RSS delivering from KindleEar'

PINYIN_FILENAME = True # True则发送邮件的文件名转换为拼音（如果是汉字的话）

#True则每篇文章都自动检测编码，这会减慢一些处理速度，但是一般不会导致乱码
#False则先使用上一篇文章的编码进行解码，如果失败再检测此文章编码，一般来说
#不会导致乱码，并且处理性能好很多，如果有部分文章出现乱码，则需要设置此选项为True
ALWAYS_CHAR_DETECT = False
