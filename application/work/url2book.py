#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#实现接收到邮件后抓取URL然后制作成电子书

import zlib, base64, io
from flask import Blueprint, request
from ..base_handler import *
from ..back_end.db_models import *
from ..back_end.send_mail_adpt import send_to_kindle
from ..utils import local_time
from ..lib.recipe_helper import GenerateRecipeSource
from calibre.web.feeds.recipes import compile_recipe
from config import *

bpUrl2Book = Blueprint('bpUrl2Book', __name__)

#抓取指定链接，转换成附件推送
@bpUrl2Book.route("/url2book")
def Url2BookRoute():
    global default_log
    log = default_log
    args = request.args
    userName = args.get('u')
    urls = args.get('urls')
    subject = args.get('subj')
    to = args.get('to')
    language = args.get('lng')
    bookType = args.get("type", "epub")
    tz = int(args.get("tz", TIMEZONE))
    if not all((userName, urls, subject, to, language, bookType, tz)):
        return "Some parameter missing!"
    
    if (';' in to) or (',' in to):
        to = to.replace(',', ';').replace(' ', '').split(';')
        
    urls = zlib.decompress(base64.urlsafe_b64decode(urls)).decode('utf-8')
    
    if bookType == 'Download': #直接下载电子书并推送
        from lib.filedownload import Download
        for url in urls.split('|'):
            result = Download(url)
            #如果标题已经给定了文件名，则使用标题文件名
            if '.' in subject and (1 < len(subject.split('.')[-1]) < 5):
                fileName = subject
            else:
                fileName = result.fileName or "NoName"
                
            if result.content:
                send_to_kindle(userName, to, fileName, '', result.content, tz)
            else:
                save_delivery_log(userName, to, fileName, 0, status=result.status, tz=tz)
            log.info("{} Sent!".format(fileName))
        return "{} Sent!".format(fileName)
    elif bookType == 'Debug': #调试目的，将链接直接下载，发送到管理员邮箱
        from lib.debug_utils import debug_fetch
        #如果标题已经给定了文件名，则使用标题文件名，否则为默认文件名(page.html)
        fileName = None
        if '.' in subject and (1 < len(subject.split('.')[-1]) < 5):
            fileName = subject

        for url in urls.split('|'):
            debug_fetch(url, fileName)
        log.info('[DEBUG] debug file sent!')
        return 'Debug file sent!'
        
    user = KeUser.get_one(KeUser.name == userName)
    if not user or not user.kindle_email:
        return "The user does not exist."
    
    book = url_to_book(subject, urls.split('|'), user, language)
    if book:
        send_to_kindle(userName, to, subject, user.book_type, book, tz)
        rs = f"Sent {subject}.{user.book_type}"
    else:
        save_delivery_log(userName, to, title, 0, status='fetch failed', tz=tz)
        rs = "[Url2Book]Fetch url failed."
    return rs

#仅通过一个url列表构建一本电子书，返回电子书二进制内容，格式为user.book_type
def url_to_book(title, urls, user, language=None):
    feeds = [(title, url) for url in urls]
    src = GenerateRecipeSource(title, feeds, user, language)
    try:
        ro = compile_recipe(src)
    except Exception as e:
        default_log.warning('Failed to compile recipe {}: {}'.format(title, e))
        return None

    #合并自定义css
    if user.css_content:
        ro.extra_css = ro.extra_css + '\n\n' + user.css_content if ro.extra_css else user.css_content

    output = io.BytesIO()
    ConvertRecipeToEbook(ro, output, user)
    return output.getvalue()