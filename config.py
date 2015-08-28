#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""Configures for KindleEar, the First two variable is must to modify.
KindleEar配置文件，请务必修改开始两个配置（如果使用uploader，则uploader自动帮你修改）
"""

SRC_EMAIL = "akindleear@gmail.com"  #Your gmail account for sending mail to Kindle
DOMAIN = "https://kindleear.appspot.com" #Your domain of app

TIMEZONE = 8  #Default timezone, you can modify it in webpage after deployed

DEFAULT_MASTHEAD = "mh_default.gif" #default masthead
DEFAULT_COVER = "cv_default.jpg" #default cover, leave it empty will not add cover to book
DEFAULT_COVER_BV = None #default cover for merged-book, None indicates paste all covers into one

MY_FEEDS_TITLE = u'KindleEar'
MY_FEEDS_DESC = u'RSS delivering from KindleEar'

#default timeout for network connection
CONNECTION_TIMEOUT = 60

# True to translate filename in chinese to pinyin
PINYIN_FILENAME = False

#If set to True, encoding detected by chardet module will be used for each article
#otherwise encoding in http response header or meta of html is used in proprity.
ALWAYS_CHAR_DETECT = False

#True indicates that any encoding in http header or in html header will be used.
#False indicates that encoding will be used if the encoding in http header and the one in html header are the same.
TRUST_ENCODING_IN_HEADER_OR_META = False

#generate brief description for toc item or not.
GENERATE_TOC_DESC = True
TOC_DESC_WORD_LIMIT = 500

#-------------------add by rexdf-----------
#title for table of contents
TABLE_OF_CONTENTS = u'Table Of Contents'

#description of toc contains image or not
GENERATE_TOC_THUMBNAIL = True

#if generate other html toc or not, just for reading in pc
GENERATE_HTML_TOC = True

#if convert color image to gray or not, good for reducing size of book if you read it in Kindle only
COLOR_TO_GRAY = True
#----------------end of add by rexdf-------

#reduce dimension of image to (Width,Height)
#or you can set it to None, and choose device type in webpage 'setting'
REDUCE_IMAGE_TO = None #(600,800)

#clean css in dealing with content from string@appid.appspotmail.com or not
DELETE_CSS_FOR_APPSPOTMAIL = True

#if word count more than the number, the email received by appspotmail will 
#be transfered to kindle directly, otherwise, will fetch the webpage for links in email.
WORDCNT_THRESHOLD_FOR_APMAIL = 100

#subject of email will be truncated based limit of word count
SUBJECT_WORDCNT_FOR_APMAIL = 16

#retry count when failed in sendmail to kindle
SENDMAIL_RETRY_CNT = 1

#GAE restrict postfix of attachment in email to send
#True indicates KindleEar will replace the dot to underline to send mail if it failed.
SENDMAIL_ALL_POSTFIX = False

#text for link to share or archive
#SHARE_FUCK_GFW_SRV: (For users in China)如果你要翻墙的话，请设置为其中一个转发服务器
#翻墙转发服务器源码：http://github.com/cdhigh/forwarder
#SHARE_FUCK_GFW_SRV = "http://forwarder.ap01.aws.af.cm/?k=xzSlE&t=60&u=%s"
SHARE_FUCK_GFW_SRV = "http://kforwarder.herokuapp.com/?k=xzSlE&t=60&u=%s"
SAVE_TO_EVERNOTE = u"Save to evernote"
SAVE_TO_WIZ = u"Save to Wiz"
SHARE_ON_XWEIBO = u"Share on Sina Weibo"
SHARE_ON_TWEIBO = u"Share on Tencent Weibo"
SHARE_ON_FACEBOOK = u"Share on facebook"
SHARE_ON_TWITTER = u"Tweet it"
SHARE_ON_TUMBLR = u"Share on tumblr"
OPEN_IN_BROWSER = u"Open in Browser"
