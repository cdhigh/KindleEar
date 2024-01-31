#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#实现接收到邮件后抓取URL然后制作成电子书

import zlib, base64, io
from flask import Blueprint, request
from apps.base_handler import *
from apps.back_end.db_models import *
from apps.back_end.send_mail_adpt import send_to_kindle
from apps.utils import local_time
from lib.makeoeb import *
from books.base_url_book import BaseUrlBook
from config import *

bpUrl2Book = Blueprint('bpUrl2Book', __name__)

#抓取指定链接，转换成附件推送
@bpUrl2Book.route("/url2book")
def Url2Book():
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
        return "Some parameter missing!<br />"
    
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
    
    opts = GetOpts(user.device)
    
    book = BaseUrlBook(opts=opts, user=user)
    book.title = subject
    book.description = subject
    book.language = language
    book.feeds = [(subject, url) for url in urls.split('|')]
    
    # 创建 OEB
    oeb = CreateEmptyOeb(opts, log)
    
    if len(book.feeds) > 1:
        setMetaData(oeb, subject, language, local_time(tz=tz))
        id_, href = oeb.manifest.generate('masthead', DEFAULT_MASTHEAD)
        oeb.manifest.add(id_, href, ImageMimeFromName(DEFAULT_MASTHEAD))
        oeb.guide.add('masthead', 'Masthead Image', href)
    else:
        setMetaData(oeb, subject, language, local_time(tz=tz), pubtype='book:book:KindleEar')
    
    # 对于html文件，变量名字自文档
    # 对于图片文件，section为图片mime,url为原始链接,title为文件名,content为二进制内容
    itemCnt = 0
    hasImage = False
    sections = {subject: []}
    tocThumbnails = {} #map img-url -> manifest-href
    #for sec_or_media, url, title, content, brief, thumbnail in book.Items():
    for item in book.Items():
        itemCnt += 1
        if isinstance(item, ItemImageTuple): #图像文件
            id_, href = oeb.manifest.generate(id='img', href=item.fileName)
            oeb.manifest.add(id_, href, item.mime, data=item.content)
            if item.isThumbnail:
                tocThumbnails[item.url] = href
            hasimage = True
        elif isinstance(item, ItemCssTuple): #CSS
            if item.url not in oeb.manifest.hrefs: #Only one css needed
                oeb.manifest.add('css', item.url, "text/css", data=item.content)
        elif len(book.feeds) > 1:
            sections[subject].append(item)
        else: #单文章
            id_, href = oeb.manifest.generate(id='page', href='page.html')
            manif = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=str(item.soup))
            oeb.spine.add(manif, False)
            oeb.toc.add(item.title, href)
        
    if itemCnt > 0:
        if len(book.feeds) > 1:
            InsertToc(oeb, sections, tocThumbnails)
            
        oIO = io.BytesIO()
        o = EPUBOutput() if bookType == "epub" else MOBIOutput()
        o.convert(oeb, oIO, opts, log)
        send_to_kindle(userName, to, book.title, bookType, oIO.getvalue(), tz)
        rs = "{}({}).{} Sent!".format(book.title, local_time(tz=tz), bookType)
    else:
        save_delivery_log(userName, to, book.title, 0, status='fetch failed', tz=tz)
        rs = "[Url2Book]Fetch url failed."

    return rs

