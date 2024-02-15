#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Author: cdhigh <https://github.com/cdhigh>
#将发到string@appid.appspotmail.com的邮件正文转成附件发往kindle邮箱。

import re, zlib, base64, io
from urllib.parse import urljoin
from email.header import decode_header
from email.utils import parseaddr, collapse_rfc2231_value
from bs4 import BeautifulSoup
from flask import Blueprint, request, current_app as app
from google.appengine.api import mail
from calibre import guess_type
from ..back_end.task_queue_adpt import create_delivery_task, create_url2book_task
from ..back_end.db_models import KeUser, WhiteList
from ..back_end.send_mail_adpt import send_to_kindle
from ..base_handler import *
from ..utils import local_time
from build_ebook import html_to_book

bpInBoundEmail = Blueprint('bpInBoundEmail', __name__)

#subject of email will be truncated based limit of word count
SUBJECT_WORDCNT = 30

#if word count more than the number, the email received by appspotmail will 
#be transfered to kindle directly, otherwise, will fetch the webpage for links in email.
WORDCNT_THRESHOLD_APMAIL = 100

#clean css in dealing with content from string@appid.appspotmail.com or not
DELETE_CSS_APMAIL = True

#解码邮件主题
def decode_subject(subject):
    if subject.startswith('=?') and subject.endswith('?='):
        subject = ''.join(str(s, c or 'us-ascii') for s, c in decode_header(subject))
    else:
        subject = str(collapse_rfc2231_value(subject))
    return subject

#判断一个字符串是否是超链接，返回链接本身，否则空串
def IsHyperLink(txt):
    expr = r"""^(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>???“”‘’]))"""
    match = re.match(expr, txt)
    return match.group() if match else ''

#从接收地址提取账号名和真实地址
#如果有多个收件人的话，只解释第一个收件人
def extractUsernameFromEmail(to):
    to = parseaddr(to)[1]
    to = to.split('@')[0] if to and '@' in to else 'xxx'
    if '__' in to:
        userNameParts = to.split('__')
        userName = userNameParts[0] if userNameParts[0] else app.config['ADMIN_NAME']
        return userName, userNameParts[1]
    else:
        return app.config['ADMIN_NAME'], to

#判断是否是垃圾邮件
#sender: 发件人地址
#user: 用户账号数据库行实例
def IsSpamMail(sender, user):
    if not sender or '@' not in sender:
        return True

    mailHost = sender.split('@')[1]
    whitelist = [item.mail.lower() for item in user.white_lists()]

    return not (('*' in whitelist) or (sender.lower() in whitelist) or (f'@{mailHost}' in whitelist))

#GAE的退信通知
@bpInBoundEmail.post("/_ah/bounce")
def ReceiveBounce():
    msg = mail.BounceNotification(dict(request.form.lists()))
    #default_log.warning("Bounce original: {}, notification: {}".format(msg.original, msg.notification))
    return "OK", 200

#有新的邮件到达, _ah=apphosting
#每个邮件限额: 31.5 MB
@bpInBoundEmail.post("/_ah/mail/<path>")
def ReceiveMail(path):
    global default_log
    log = default_log

    message = mail.InboundEmailMessage(request.get_data())
    userName, to = extractUsernameFromEmail(message.to) #从接收地址提取账号名和真实地址
    adminName = app.config['ADMIN_NAME']

    user = KeUser.get_or_none(KeUser.name == (userName or adminName))
    if not user and (userName != adminName):
        user = KeUser.get_or_none(KeUser.name == adminName)
    
    if not user or not user.kindle_email:
        return "OK", 200

    #阻挡垃圾邮件
    sender = parseaddr(message.sender)[1]
    if IsSpamMail(sender, user):
        log.warning('Spam mail from : {}'.format(sender))
        return "Spam mail!"
    
    if hasattr(message, 'subject'):
        subject = decode_subject(message.subject).strip()
    else:
        subject = "NoSubject"
    
    forceToLinks = False
    forceToArticle = False

    #邮件主题中如果在最后添加一个 !links，则强制提取邮件中的链接然后生成电子书
    if subject.endswith('!links') or ' !links ' in subject:
        subject = subject.replace('!links', '').replace(' !links ', '').strip()
        forceToLinks = True
    # 如果邮件主题在最后添加一个 !article，则强制转换邮件内容为电子书，忽略其中的链接
    elif subject.endswith('!article') or ' !article ' in subject:
        subject = subject.replace('!article', '').replace(' !article ', '').strip()
        forceToArticle = True
        
    #通过邮件触发一次“现在投递”
    if to.lower() == 'trigger':
        create_delivery_task({'userName': userName, 'recipeId': subject})
        return f'A delivery task for "{userName}" is triggered'
    
    #获取和解码邮件内容
    txtBodies = message.bodies('text/plain')
    try:
        allBodies = [body.decode() for cType, body in message.bodies('text/html')]
    except:
        log.warning('Decode html bodies of mail failed.')
        allBodies = []
    
    #此邮件为纯文本邮件，将文本信息转换为HTML格式
    if not allBodies:
        log.info('There is no html body, use text body instead.')
        try:
            allBodies = [body.decode() for cType, body in txtBodies]
        except:
            log.warning('Decode text bodies of mail failed.')
            allBodies = []
        bodies = ''.join(allBodies)
        if not bodies:
            return "There is no html body neither text body."

        bodyUrls = []
        for line in bodies.split('\n'):
            line = line.strip()
            if not line:
                continue
            link = IsHyperLink(line)
            if link:
                bodyUrls.append('<a href="{}">{}</a><br />'.format(link, link))
            else: #有非链接行则终止，因为一般的邮件最后都有推广链接
                break

        bodies = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
          <title>{}</title></head><body>{}</body></html>""".format(subject,
          ''.join(bodyUrls) if bodyUrls else bodies)
        allBodies = [bodies]
    
    #开始处理邮件内容
    soup = BeautifulSoup(allBodies[0], 'lxml')
    
    #合并多个邮件文本段
    for otherBody in allBodies[1:]:
        bodyOther = BeautifulSoup(otherBody, 'lxml').find('body')
        soup.body.extend(bodyOther.contents if bodyOther else [])
    
    #判断邮件内容是文本还是链接（包括多个链接的情况）
    links = []
    body = soup.body if soup.find('body') else soup
    if not forceToArticle: #如果强制转正文就不分析链接了，否则先分析和提取链接
        for s in body.stripped_strings:
            link = IsHyperLink(s)
            if link:
                if link not in links:
                    links.append(link)
            #如果是多个链接，则必须一行一个，不能留空，除非强制提取链接
            #这个处理是为了去除部分邮件客户端在邮件末尾添加的一个广告链接
            elif not forceToLinks:
                break
            
    if not links and not forceToArticle: #如果通过正常字符（显示出来的）判断没有链接，则看html的a标签
        links = [link['href'] for link in soup.find_all('a', attrs={'href': True})]
        
        text = ' '.join([s for s in body.stripped_strings])
        
        #如果有相对路径，则在里面找一个绝对路径，然后转换其他
        hasRelativePath = False
        fullPath = ''
        for link in links:
            text = text.replace(link, '')
            if not link.startswith('http'):
                hasRelativePath = True
            if not fullPath and link.startswith('http'):
                fullPath = link
        
        if hasRelativePath and fullPath:
            for idx, link in enumerate(links):
                if not link.startswith('http'):
                    links[idx] = urljoin(fullPath, link)
        
        #如果字数太多，则认为直接推送正文内容
        if not forceToLinks and (len(links) != 1 or len(text) > WORDCNT_THRESHOLD_APMAIL):
            links = []
        
    if links:
        #判断是下载文件还是转发内容
        isBook = bool(to.lower() in ('book', 'file', 'download'))
        if not isBook:
            isBook = bool(link[-5:].lower() in ('.mobi','.epub','.docx'))
        if not isBook:
            isBook = bool(link[-4:].lower() in ('.pdf','.txt','.doc','.rtf'))
        isDebug = bool(to.lower() == 'debug')

        if isDebug:
            action = 'debug'
        elif isBook:
            action = 'download'
        else:
            action = ''
        
        #url需要压缩，避免URL太长
        params = {'userName': userName,
                 'urls': base64.urlsafe_b64encode(zlib.compress('|'.join(links).encode('utf-8'))).decode(),
                 'action': action,
                 'subject': subject[:SUBJECT_WORDCNT]}
        create_url2book_task(params)
    else: #直接转发邮件正文
        imageContents = []
        if hasattr(message, 'attachments'):  #先判断是否有图片
            imageContents = [(f, c) for f, c in message.attachments if (guess_type(f)[0] or '').startswith('image/')]
        
        #先修正不规范的HTML邮件
        h = soup.find('head')
        if not h:
            h = soup.new_tag('head')
            soup.html.insert(0, h)
        t = soup.head.find('title')
        if not t:
            t = soup.new_tag('title')
            t.string = subject
            soup.head.insert(0, t)
        
        #有图片的话，要生成MOBI或EPUB才行
        #而且多看邮箱不支持html推送，也先转换epub再推送
        if imageContents:
            #仿照Amazon的转换服务器的处理，去掉CSS
            if DELETE_CSS_APMAIL:
                tag = soup.find('style', attrs={'type': 'text/css'})
                if tag:
                    tag.decompose()
                for tag in soup.find_all(attrs={'style': True}):
                    del tag['style']
            
            #将图片的src的文件名调整好
            for img in soup.find_all('img', attrs={'src': True}):
                if img['src'].lower().startswith('cid:'):
                    img['src'] = img['src'][4:]

            book = html_to_book(str(soup), subject[:SUBJECT_WORDCNT], imageContents, user)
        else: #没有图片则直接推送HTML文件，阅读体验更佳
            m = soup.find('meta', attrs={"http-equiv": "Content-Type"})
            if not m:
                m = soup.new_tag('meta', content="text/html; charset=utf-8")
                m["http-equiv"] = "Content-Type"
                soup.html.head.insert(0, m)
            else:
                m['content'] = "text/html; charset=utf-8"
            book = (f'KindleEar_{local_time("%Y-%m-%d_%H-%M", user.timezone)}.html', str(soup).encode('utf-8'))

        send_to_kindle(user, subject[:SUBJECT_WORDCNT], book, fileWithTime=False)
    
    return 'OK'
