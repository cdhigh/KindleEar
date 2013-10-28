#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""app的配置文件"""

SRC_EMAIL = "akindleear@gmail.com"  #邮件的发件人地址
TIMEZONE = 8                        #默认时区

DEFAULT_MASTHEAD = "mh_default.gif" #如果书籍没有报头，则使用此报头。
DEFAULT_COVER = "cv_default.jpg" #如果书籍没有封面，则使用此封面，留空则不添加封面

#自定义RSS的默认标题，后续可以在网页上修改，如果包含中文则需要在前面加u''
MY_FEEDS_TITLE = u'KindleEar'
MY_FEEDS_DESC = u'RSS delivering from KindleEar'

#设置下载RSS和文章的超时时间，单位为秒，如果RSS很多，设置短一点有可能提高一些效率
#但是也增加了下载超时的可能，超时则丢失超时的RSS或文章或图片，不会有更多的影响
#(GAE默认为5秒)
CONNECTION_TIMEOUT = 25

# True则发送邮件的文件名转换为拼音（如果是汉字的话）
PINYIN_FILENAME = False

#True则每篇文章都自动检测编码，这会减慢一些处理速度，但是一般不会导致乱码
#False则先使用上一篇文章的编码进行解码，如果失败再检测此文章编码，
#因为每个RSS源的第一篇文章都强制检测一次编码，一般来说不会导致乱码，
#并且处理性能好很多，如果有部分文章出现乱码，则需要设置此选项为True
#否则还是推荐设置为False
ALWAYS_CHAR_DETECT = False

#是否生成TOC的文章内容预览，如果使用非触摸版Kindle，没意义，因为看不到
#对于kindle touch和kindle paperwhite可以设置为True。
GENERATE_TOC_DESC = True
TOC_DESC_WORD_LIMIT = 150  # 内容预览（摘要）字数限制

#为减少文件大小，将大图片缩小为此尺寸，(Width,Height)
#此尺寸是适应Kindle3的，如果你是完美主义者，可以设置为(568,682)，扣除margin
#如果你使用的是其他分辨率的机器，可以直接修改为其他值
REDUCE_IMAGE_TO = (600,800)

#在使用string@appid.appspotmail.com邮件转发时，是否删除CSS
#删除CSS后阅读体验更佳，但是会丢失各种字体和颜色等排版信息
#如果不删除CSS，则部分文本可能太小以致于难以阅读
#当转换HTML时，Amazon的推送服务器会删除CSS
DELETE_CSS_FOR_APPSPOTMAIL = True
