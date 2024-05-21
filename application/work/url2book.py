#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#实现接收到邮件后抓取URL然后制作成电子书
#Author: cdhigh <https://github.com/cdhigh>
from urllib.parse import urljoin
from flask import Blueprint, request, current_app as app
from bs4 import BeautifulSoup
from calibre.web.feeds.news import recursive_fetch_url
from ..base_handler import *
from ..utils import filesizeformat, hide_email
from ..back_end.db_models import *
from ..back_end.send_mail_adpt import send_to_kindle, send_mail
from urlopener import UrlOpener
from filesystem_dict import FsDictStub
from build_ebook import urls_to_book, html_to_book

bpUrl2Book = Blueprint('bpUrl2Book', __name__)

#抓取指定链接，转换成附件推送
@bpUrl2Book.route("/url2book", methods=['GET', 'POST'])
def Url2BookRoute():
    params = request.args if request.method == 'GET' else (request.json or {})
    userName = params.get('userName', app.config['ADMIN_NAME'])
    urls = params.get('urls', '')
    title = params.get('title', '')
    key = params.get('key', '')
    action = params.get('action', '')
    text = params.get('text', '')
    return Url2BookImpl(userName, urls, title, key, action, text)
    

#实现Url2book的具体功能
#action: 
#  download: 直接下载对应链接的电子书并推送
#  debug: 下载链接推送至管理员邮箱
#  其他: 抓取对应链接的网页并生成电子书推送
#text存在则直接使用text制作电子书(优先)，urls存在则抓取url
def Url2BookImpl(userName, urls, title, key, action='', text='', language=''):
    if not all((userName, urls, title, key)):
        return "Some parameter missing!"

    user = KeUser.get_or_none(KeUser.name == userName)
    if not user or not user.cfg('kindle_email') or user.share_links.get('key', '') != key:
        return "The user does not exist."
    
    urls = urls.split('|') if urls else []

    if urls and action == 'download': #直接下载电子书并推送
        return u2lDownloadFile(user, urls, title)
    elif action == 'debug': #调试目的，将链接直接下载，发送到管理员邮箱
        return u2lDebugFetch(user, urls, title, text)
    else:
        return u2lFetchUrl2(user, urls, title, text, language)
        
#直接下载urls指定的书籍，而不是转换
def u2lDownloadFile(user, urls, title):
    from filedownload import Download
    sents = []
    for url in urls:
        result = Download(url)
        #如果标题已经给定了文件名，则使用标题文件名
        if '.' in title and (1 < len(title.split('.')[-1]) < 5):
            fileName = title
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
    default_log.warning(sents)
    return sents

#调试目的，将链接直接下载，发送到管理员邮箱
def u2lDebugFetch(user, urls, title, text):
    #如果标题已经给定了文件名，则使用标题文件名，否则为默认文件名(page.html)
    if '.' in title and (1 < len(title.split('.')[-1]) < 5):
        fileName = title
    else:
        fileName = 'page.html'

    sendCnt = 0
    if text:
        attachments = [(fileName, text.encode('utf-8'))]
        send_to_kindle(user, 'DEBUG FETCH', attachments, to=user.cfg('email'))
        sendCnt += 1
    else:
        opener = UrlOpener()
        for url in urls:
            resp = opener.open(url)
            if resp.status_code == 200:
                attachments = [(fileName, resp.content)]
                send_to_kindle(user, 'DEBUG FETCH', attachments, to=user.cfg('email'))
                sendCnt += 1
            else:
                default_log.warning(f'debug fetch failed: {UrlOpener.CodeMap(resp.status_code)}, url: {url}')
    
    if sendCnt:
        info = f"The debug file have been sent to {hide_email(user.cfg('email'))}."
        default_log.warning(info)
        return info
    else:
        return 'debug fetch failed'

#抓取url，制作成电子书
def u2lFetchUrl2(user, urls, title, text, language=''):
    if not urls:
        return "No URLs provided."

    if text:
        target = 'selected text'
        book = u2lCreateEbookFromText(user, urls[0], title, text, language=language)
    else:
        target = 'urls'
        processedUrls = u2lPreprocessUrl(urls)
        book = urls_to_book(urls, title, user, language=language)
        
    if book:
        send_to_kindle(user, title, book, fileWithTime=False)
        size = filesizeformat(len(book), suffix='Bytes')
        email = hide_email(user.cfg('kindle_email'))
        rs = f"The {target} have been sent to {email}:<br/>Title: {title}<br/>Size: {size}"
    else:
        save_delivery_log(user, title, 0, status='fetch failed')
        rs = "Fetch url failed:<br/>{}".format('<br/>'.join(urls))
    return rs

#下载text里面的图像文件，和文本一起做成电子书投递
def u2lCreateEbookFromText(user, url, title, text, language=''):
    text = text.replace('\n', '<br/>').replace('\\n', '<br/>')
    htmlText = ['<!DOCTYPE html>', '<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>', 
        f'<title>{title}</title></head><body><div>{text}</div>']
    if url:
        htmlText.append(f'<br/><br/><p><a href="{url}">origin : {url}</a></p>')
    htmlText.append('</body></html>')
    fs = FsDictStub(path=None)
    fs.write('/index.html', '\n'.join(htmlText).encode('utf-8'))
    res, paths, failures = recursive_fetch_url('file:///index.html', fs)
    if not res:
        return None

    imgs = []
    soup = BeautifulSoup(fs.read(res), 'lxml')
    for tag in soup.find_all('img', src=True): #修正图片路径，从images目录里面移出
        src = tag['src']
        data = fs.read(os.path.join(fs.path, src))
        if data:
            if src.startswith('images/'):
                src = src[7:]
            elif src.startswith('/images/'):
                src = src[8:]
            tag['src'] = src
            imgs.append((src, data))
        else:
            tag.extract()

    return html_to_book(str(soup), title, user, imgs, language=language)

#url列表的预处理，对一些特殊的网站进行url的适当转换
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
        if tagSummary:
            for tagChapter in tagSummary.find_all('li', attrs={'class': ['chapter']}): #type:ignore
                tagA = tagChapter.find('a', href=True)
                if tagA:
                    urls.append((tagA.string.strip(), urljoin(url, tagA.attrs['href'])))
    else:
        urls.append(url)
    return urls if urls else [url]
