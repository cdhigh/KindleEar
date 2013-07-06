#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""app的配置文件"""

SrcEmail = "akindleear@gmail.com"  #邮件的发件人地址

DEFAULT_COVER = "cv_default.jpg" #如果书籍没有封面，则使用此封面，留空则不添加封面
TIMEZONE = 8 #管理员的时区
OWNFEEDS_TITLE = 'KindleEar' #自定义RSS的默认标题，后续可以在网页上修改
OWNFEEDS_DESC = 'RSS delivering from KindleEar'
PINYIN_FILENAME = True # True则发送邮件的文件名转换为拼音（如果是汉字的话）
