#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#实现接收到邮件后抓取URL然后制作成电子书

import zlib, base64, io
from urllib.parse import urljoin
from flask import Blueprint, request, current_app as app
from bs4 import BeautifulSoup
from ..base_handler import *
from ..utils import filesizeformat
from ..back_end.db_models import *
from ..back_end.send_mail_adpt import send_to_kindle, send_mail
from urlopener import UrlOpener
from build_ebook import urls_to_book

bpUrl2Book = Blueprint('bpUrl2Book', __name__)

#抓取指定链接，转换成附件推送
@bpUrl2Book.route("/url2book")
def Url2BookRoute():
    args = request.args
    userName = args.get('userName', app.config['ADMIN_NAME'])
    urls = args.get('urls')
    subject = args.get('subject')
    action = args.get("action")
    return Url2BookImpl(userName, urls, subject, action)
    

#实现Url2book的具体功能
#action: 
#  download: 直接下载对应链接的电子书并推送
#  debug: 下载链接推送至管理员邮箱
#  其他: 抓取对应链接的网页并生成电子书推送
def Url2BookImpl(userName: str, urls: str, subject: str, action: str=''):
    if not all((userName, urls, subject)):
        return "Some parameter missing!"

    user = KeUser.get_or_none(KeUser.name == userName)
    if not user or not user.kindle_email:
        return "The user does not exist."
    
    to = user.kindle_email
    tz = user.timezone

    try:
        urls = zlib.decompress(base64.urlsafe_b64decode(urls)).decode('utf-8')
    except:
        pass
    urls = urls.split('|')

    if action == 'download': #直接下载电子书并推送
        from filedownload import Download
        sents = []
        for url in urls:
            result = Download(url)
            #如果标题已经给定了文件名，则使用标题文件名
            if '.' in subject and (1 < len(subject.split('.')[-1]) < 5):
                fileName = subject
            else:
                fileName = result.fileName or "NoName"
                
            if result.content:
                send_to_kindle(user, fileName, (fileName, result.content))
                sents.append(fileName)
            else:
                save_delivery_log(user, fileName, 0, status=result.status)
        if sents:
            sents = 'Downloaded books:<br/>{}'.format('<br/>'.join(sents))
        else:
            sents = 'Failed to download books'
        default_log.info(sents)
        return sents
    elif action == 'debug': #调试目的，将链接直接下载，发送到管理员邮箱
        #如果标题已经给定了文件名，则使用标题文件名，否则为默认文件名(page.html)
        fileName = None
        if '.' in subject and (1 < len(subject.split('.')[-1]) < 5):
            fileName = subject

        opener = UrlOpener()
        for url in urls:
            resp = opener.open(url)
            if resp.status_code == 200:
                attachments = [('page.html', resp.content)]
                send_mail(user, user.email, 'DEBUG FETCH', 'DEBUG FETCH', attachments=attachments)
            else:
                default_log.warning('debug_fetch failed: code:{}, url:{}'.format(resp.status_code, url))
            
        default_log.info('[DEBUG] debug file sent!')
        return 'Debug file sent!'
    else:
        urls = u2lPreprocessUrl(urls)
        book = urls_to_book(urls, subject, user)
        if book:
            send_to_kindle(user, subject, book, fileWithTime=False)
            size = filesizeformat(len(book), suffix='Bytes')
            rs = f"The book have been sent:<br/><i>{subject}.{user.book_type} ({size})</i>"
        else:
            save_delivery_log(user, subject, 0, status='fetch failed')
            rs = "Fetch url failed:<br/>{}".format('<br/>'.join(urls))
        return rs

#url列表的预处理
#返回处理过的url列表
def u2lPreprocessUrl(urls):
    #可以将gitbook整个下载为一本书
    if len(urls) == 1 and 'gitbooks.io' in urls[0]:
        urls = GetGitbookChapterUrls(urls[0])

    return urls

#输入gitbook的书籍地址，返回所有章节的URL和标题
def GetGitbookChapterUrls(url):
    opener = UrlOpener()
    resp = opener.open(url)
    urls = []
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, 'lxml')
        tagSummary = soup.find('ul', attrs={'class': ['summary']})
        for tagChapter in tagSummary.find_all('li', attrs={'class': ['chapter']}):
            tagA = tagChapter.find('a', href=True)
            if tagA:
                urls.append((tagA.string.strip(), urljoin(url, tagA.attrs['href'])))
    else:
        urls.append(url)
    return urls

