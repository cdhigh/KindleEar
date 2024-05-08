#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Author: cdhigh <https://github.com/cdhigh>
#将发到string@appid.appspotmail.com的邮件正文转成附件发往kindle邮箱。

import os, re, email
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from flask import Blueprint, request
from calibre import guess_type
from ..back_end.task_queue_adpt import create_delivery_task, create_url2book_task
from ..back_end.db_models import KeUser
from ..back_end.send_mail_adpt import send_to_kindle
from ..base_handler import *
from build_ebook import html_to_book

try:
    from google.appengine.api import mail as gae_mail
except ImportError:
    gae_mail = None

bpInBoundEmail = Blueprint('bpInBoundEmail', __name__)

#主题最长字数
SUBJECT_WORDCNT = 50

#除非强制提取链接，否则超过这个字数的邮件直接转发内容
WORDCNT_THRESHOLD_APMAIL = 500

#GAE的退信通知
@bpInBoundEmail.post("/_ah/bounce")
def ReceiveGaeBounce():
    msg = gae_mail.BounceNotification(dict(request.form.lists())) #type:ignore
    default_log.warning("Bounce original: {}, notification: {}".format(msg.original, msg.notification))
    return "OK"

#有新的GAE邮件到达, _ah=apphosting
#每个邮件限额: 31.5 MB
@bpInBoundEmail.post("/_ah/mail/<path>")
def ReceiveGaeMail(path):
    message = gae_mail.InboundEmailMessage(request.get_data()) #type:ignore

    subject = message.subject if hasattr(message, 'subject') else 'NoSubject'
    
    try:
        txtBodies = [body.decode() for cType, body in message.bodies('text/plain')]
    except:
        txtBodies = []

    try:
        htmlBodies = [body.decode() for cType, body in message.bodies('text/html')]
    except:
        htmlBodies = []

    attachments = message.attachments if hasattr(message, 'attachments') else []
    
    return ReceiveMailImpl(sender=message.sender, to=message.to, subject=subject, txtBodies=txtBodies,
        htmlBodies=htmlBodies, attachments=attachments)

#postfix的content filter转发的邮件，适用与除GAE之外的平台
@bpInBoundEmail.post("/mail")
def ReceiveMail():
    msg = email.message_from_bytes(request.get_data())

    txtBodies = []
    htmlBodies = []
    attachments = []
    for part in msg.walk():
        cType = part.get_content_type()
        body = part.get_payload(decode=True)
        if part.get('Content-Disposition') == 'attachment':
            attachments.append((part.get_filename(), body))
        elif cType == 'text/plain':
            txtBodies.append(body.decode(part.get_content_charset('us-ascii'))) #type:ignore
        elif cType == 'text/html':
            htmlBodies.append(body.decode(part.get_content_charset('us-ascii'))) #type:ignore

    return ReceiveMailImpl(sender=msg.get('From'), to=msg.get_all('To'), subject=msg.get('Subject'), txtBodies=txtBodies,
        htmlBodies=htmlBodies, attachments=attachments)

#postfix的一个内容过滤器 mailglove 转发的邮件
#<https://github.com/thingless/mailglove>
@bpInBoundEmail.post("/mailglove")
def ReceiveMailGlove():
    msg = request.get_json(silent=True)
    if not msg or not isinstance(msg, dict):
        return "The content is invalid"
    
    sender = msg.get('envelopeSender', '')
    to = msg.get('envelopeRecipient', '')
    if not sender:
        sender = msg.get('from', {}).get('text', '')
    if not to:
        to = msg.get('to', {}).get('text', '')
        
    subject = msg.get('subject', '')
    txtBodies = msg.get('text', '')
    htmlBodies = msg.get('html', '')
    attachments = msg.get('attachments', '')

    return ReceiveMailImpl(sender=sender, to=to, subject=subject, txtBodies=txtBodies,
        htmlBodies=htmlBodies, attachments=attachments)

#实际实现接收邮件功能
#sender/to/subject: 发件人，收件人，主题
#txtBodies: text/plain的邮件内容列表
#htmlBodies: text/html的邮件内容列表
#attachements: 附件列表，格式为[(fileName, content),...]
def ReceiveMailImpl(sender, to, subject, txtBodies, htmlBodies, attachments):
    adminName = os.getenv('ADMIN_NAME')
    userName, to = ExtractUsernameFromEmail(to) #从接收地址提取账号名和真实地址, 格式：user__to
    userName = userName if userName else adminName

    user = KeUser.get_or_none(KeUser.name == userName)
    if not user and (userName != adminName):
        user = KeUser.get_or_none(KeUser.name == adminName)
    
    if not user or not user.cfg('kindle_email'):
        return "The user does not exists"

    #阻挡垃圾邮件
    sender = email.utils.parseaddr(sender)[1] #type:ignore
    if IsSpamMail(user, sender):
        default_log.warning(f'Spam mail from : {sender}')
        return "Spam mail"
    
    subject = DecodeSubject(subject or 'NoSubject')

    #通过邮件触发一次“现在投递”
    if to.lower() == 'trigger':
        create_delivery_task({'userName': userName, 'recipeId': subject, 'reason': 'manual'})
        return f'A delivery task for "{userName}" is triggered'
    
    forceToLinks = False
    forceToArticle = False

    #邮件主题中如果存在 !links，则强制提取邮件中的链接然后生成电子书
    if subject.endswith('!links') or ' !links ' in subject:
        subject = subject.replace(' !links ', '').replace('!links', '').strip()
        forceToLinks = True
    # 如果主题存在 !article，则强制转换邮件内容为电子书，忽略其中的链接
    elif subject.endswith('!article') or ' !article ' in subject:
        subject = subject.replace(' !article ', '').replace('!article', '').strip()
        forceToArticle = True
    
    soup = CreateMailSoup(subject, txtBodies, htmlBodies)
    if not soup:
        return "There is no html body neither text body."
    
    #提取文章的超链接
    links = [] if forceToArticle else CollectSoupLinks(soup, forceToLinks)
        
    if links:
        #判断是下载文件还是要转发邮件内容
        isBook = ((to.lower() in ('book', 'file', 'download')) or
            links[0].lower().endswith(('.mobi', '.epub', '.docx', '.pdf', '.txt', '.doc', '.rtf')))

        if to.lower() == 'debug':
            action = 'debug'
        elif isBook:
            action = 'download'
        else:
            action = ''
        
        params = {'userName': userName,
                 'urls': '|'.join(links),
                 'action': action,
                 'key': user.share_links.get('key', ''),
                 'title': subject[:SUBJECT_WORDCNT]}
        create_url2book_task(params)
    else: #直接转发邮件正文
        #只处理图像，忽略其他类型的附件
        #guess_type返回元祖 (type, encoding)
        imgs = [(f, c) for f, c in (attachments or []) if (guess_type(f)[0] or '').startswith('image/')]
        
        #有图像的话，生成MOBI或EPUB，没有图像则直接推送HTML文件
        if imgs:
            book = html_to_book(str(soup), subject[:SUBJECT_WORDCNT], user, imgs)
        else:
            book = (f'KindleEar_{user.local_time("%Y-%m-%d_%H-%M")}.html', str(soup).encode('utf-8'))

        send_to_kindle(user, subject[:SUBJECT_WORDCNT], book, fileWithTime=False)
    
    return 'OK'


#解码邮件主题
def DecodeSubject(subject):
    if not subject:
        subject = 'NoSubject'
    elif subject.startswith('=?') and subject.endswith('?='):
        subject = ''.join(str(s, c or 'us-ascii') for s, c in email.header.decode_header(subject)) #type:ignore
    else:
        subject = str(email.utils.collapse_rfc2231_value(subject)) #type:ignore
    return subject.strip()

#判断一个字符串是否是超链接
def IsHyperLink(txt):
    expr = r"""^\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>???“”‘’]))"""
    return re.match(expr, txt, re.IGNORECASE)

#从接收地址提取账号名和真实地址
#如果有多个收件人的话，只解释第一个收件人
#返回 (userName, to的@前面的部分)
def ExtractUsernameFromEmail(to):
    to = email.utils.parseaddr(to)[1] #type:ignore
    to = (to or 'xxx').split('@')[0]
    
    return to.split('__', 1) if '__' in to else ('', to)
    
#判断是否是垃圾邮件
#user: 用户账号数据库行实例
#sender: 发件人地址
def IsSpamMail(user, sender):
    if not sender or '@' not in sender:
        return True

    host = sender.split('@')[-1]
    whitelist = [item.mail.lower() for item in user.white_lists()]

    return not (('*' in whitelist) or (sender.lower() in whitelist) or (f'@{host}' in whitelist))


#将邮件里面的纯文本内容转换为一个合法的html字符串
def ConvertTextToHtml(subject, text):
    if not text:
        return ''

    #转换纯文本到html时需要将里面的文本链接变成tag a
    bodyUrls = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if IsHyperLink(line):
            bodyUrls.append(f'<a href="{line}">{line}</a><br />')
        else: #有非链接行则终止，因为一般的邮件最后都有推广链接
            break

    text = ''.join(bodyUrls) if bodyUrls else text

    return f"""<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
      <title>{subject}</title></head><body>{text}</body></html>"""

#根据邮件内容，创建一个 BeautifulSoup 实例
def CreateMailSoup(subject, txtBodies, htmlBodies):
    if txtBodies and not isinstance(txtBodies, list):
        txtBodies = [str(txtBodies)]
    if htmlBodies and not isinstance(htmlBodies, list):
        htmlBodies = [str(htmlBodies)]

    if not htmlBodies: #此邮件为纯文本邮件，将文本信息转换为HTML格式
        html = ConvertTextToHtml(subject, '\n'.join(txtBodies or []))
        htmlBodies = [html] if html else []

    if not htmlBodies:
        return None
        
    soup = BeautifulSoup(htmlBodies[0], 'lxml')
    for other in htmlBodies[1:]: #合并多个邮件HTML内容
        tag = BeautifulSoup(other, 'lxml').find('body')
        soup.body.extend(tag.contents if tag else []) #type:ignore

    #修正不规范的HTML邮件
    h = soup.find('head')
    if not h:
        h = soup.new_tag('head')
        soup.html.insert(0, h) #type:ignore
    t = soup.head.find('title') #type:ignore
    if not t:
        t = soup.new_tag('title')
        t.string = subject
        soup.head.insert(0, t) #type:ignore

    #删除CSS/JS
    for tag in list(soup.find_all(['link', 'meta', 'style', 'script'])):
        tag.extract()
    for tag in soup.find_all(attrs={'style': True}):
        del tag['style']
    
    #将图片的src的文件名修改正确，因为邮件中的图像可能会以cid:开头
    for tag in soup.find_all('img', attrs={'src': True}):
        if tag['src'].lower().startswith('cid:'):
            tag['src'] = tag['src'][4:]

    m = soup.new_tag('meta', attrs={"content": "text/html; charset=utf-8", "http-equiv": "Content-Type"})
    soup.html.head.insert(0, m) #type:ignore
    return soup
    
#提取Soup的超链接，返回一个列表
#判断邮件内容是文本还是链接（包括多个链接的情况）
#forceToLinks: 不管文章内容如何，强制提取链接
def CollectSoupLinks(soup, forceToLinks):
    links = []
    body = soup.body
    for s in body.stripped_strings:
        if IsHyperLink(s):
            if s not in links:
                links.append(s)
        #如果是多个链接，则必须一行一个，不能留空，除非强制提取链接
        #这个处理是为了去除部分邮件客户端在邮件末尾添加的一个广告链接
        elif not forceToLinks:
            break
            
    if not links: #如果通过正常字符（显示出来的）判断没有链接，则看html的a标签
        links = [link['href'] for link in soup.find_all('a', attrs={'href': True})]
        
        #如果有相对路径，则在里面找一个绝对路径，然后转换其他
        hasRelativePath = False
        fullPath = ''
        text = ' '.join([s for s in body.stripped_strings])
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

    return links
