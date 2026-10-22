#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Author: cdhigh <https://github.com/cdhigh>
#将发到string@appid.appspotmail.com的邮件正文转成附件发往kindle邮箱。
import os, re, json, email
from typing import Union
from operator import itemgetter
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from flask import Blueprint, request, render_template, current_app as app
from flask_babel import gettext as _
from calibre import guess_type
from ..back_end.task_queue_adpt import create_delivery_task, create_url2book_task
from ..back_end.db_models import KeUser
from ..back_end.send_mail_adpt import send_to_kindle, send_html_mail
from ..mail_hook import run_mail_hook, run_mail_content_hook
from ..base_handler import *
from build_ebook import html_to_book, convert_book
from urlopener import UrlOpener

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

    attachments = []
    if hasattr(message, 'attachments'):
        for attachment in message.attachments:
            filename = attachment.filename
            if filename:
                attachments.append((filename, attachment.payload))

    return ReceiveMailImpl(sender=message.sender, to=message.to, subject=subject, txtBodies=txtBodies,
        htmlBodies=htmlBodies, attachments=attachments)

#postfix的content filter转发的邮件，适用与除GAE之外的平台
@bpInBoundEmail.post("/mail")
def ReceiveMail():
    msg = email.message_from_bytes(request.get_data())
    sender = msg.get('From', '')
    to = msg.get_all('To', '')
    subject = msg.get('Subject', '')

    txtBodies = []
    htmlBodies = []
    attachments = []
    for part in msg.walk():
        cType = part.get_content_type()
        body = part.get_payload(decode=True)
        if part.get('Content-Disposition', '').startswith('attachment'):
            filename = part.get_filename()
            if filename:
                decoded_filename = DecodeSubject(filename)
                attachments.append((decoded_filename, body))
        elif cType == 'text/plain':
            txtBodies.append(body.decode(part.get_content_charset('us-ascii'))) #type:ignore
        elif cType == 'text/html':
            htmlBodies.append(body.decode(part.get_content_charset('us-ascii'))) #type:ignore

    return ReceiveMailImpl(sender=sender, to=to, subject=subject,txtBodies=txtBodies, 
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
    txtBodies = msg.get('text', []) or []
    htmlBodies = msg.get('html', []) or []
    attachments = msg.get('attachments', [])

    if not isinstance(txtBodies, list):
        txtBodies = [str(txtBodies)]
    if not isinstance(htmlBodies, list):
        htmlBodies = [str(htmlBodies)]
    if not isinstance(attachments, list):
        attachments = [attachments]

    return ReceiveMailImpl(sender=sender, to=to, subject=subject, txtBodies=txtBodies,
        htmlBodies=htmlBodies, attachments=attachments)

#实际实现接收邮件功能
#sender/to/subject: 发件人，收件人，主题
#txtBodies: text/plain的邮件内容列表
#htmlBodies: text/html的邮件内容列表
#attachements: 附件列表，格式为[(fileName, content),...]
def ReceiveMailImpl(sender: str, to: Union[list,str], subject: str, txtBodies: list, htmlBodies: list, attachments: list):
    adminName = os.environ.get('ADMIN_NAME', 'admin')
    userName, dest = ExtractUsernameFromEmail(to) #从接收地址提取账号名和真实地址, 格式：user__to
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
    
    subject = DecodeSubject(subject)

    UrlOpener.set_proxy(user.cfg('proxy'))

    #如果发件人匹配了用户上传的钩子文件，先调用钩子函数预处理邮件内容
    subject, txtBodies, htmlBodies, attachments = run_mail_hook(user, sender, to, subject,
        txtBodies, htmlBodies, attachments)

    #如果需要暂存邮件
    inbound_email = user.cfg('inbound_email')
    if not inbound_email:
        default_log.warning('inbound mail disabled')
        return

    if 'save' in inbound_email:
        SaveInEmailToDb(user, sender, to, subject, txtBodies, htmlBodies, attachments)

    #通过邮件触发一次“现在投递”
    if dest == 'trigger':
        key = app.config['DELIVERY_KEY']
        create_delivery_task({'userName': userName, 'recipeId': subject, 'reason': 'manual', 'key': key})
        return f'A delivery task for "{userName}" is triggered'
    
    if 'forward' not in inbound_email:
        default_log.warning('The inbound email forwarding feature is not yet enabled.')
        return 'The inbound email forwarding feature is not yet enabled.'

    #需要需要，转发mobi为epub
    if dest == 'convert':
        ret = TransferMobi(attachments, user)
        if ret:
            return 'Sent:<br/>{}'.format('<br/>'.join(ret))

    forceLinks = bool(dest == 'links') #强制提取链接
    forceArticle = bool(dest == 'article') #强制发送邮件内容
    
    #邮件主题中如果存在 !links ，则强制提取邮件中的链接然后生成电子书
    if subject.endswith('!links') or ' !links ' in subject:
        subject = subject.replace(' !links ', '').replace('!links', '').strip()
        forceLinks = True
    # 如果主题存在 !article ，则强制转换邮件内容为电子书，忽略其中的链接
    elif subject.endswith('!article') or ' !article ' in subject:
        subject = subject.replace(' !article ', '').replace('!article', '').strip()
        forceArticle = True

    #设置电子书语种
    language = ''
    match = re.search(r'!lang=([^ ]+)', subject) # !lang=en
    if match:
        language = match.group(1).replace('_', '-').lower()
        subject = subject.replace(match.group(0), '').strip()
    
    soup = CreateMailSoup(subject, txtBodies, htmlBodies)
    if not soup:
        return "There is no html body neither text body."
        
    title = subject[:SUBJECT_WORDCNT] or f'KindleEar_{user.local_time("%Y-%m-%d_%H-%M")}'
    
    #如果发件人匹配了用户上传的钩子文件，调用钩子函数处理邮件正文和附件
    soup, attachments, hook_urls = run_mail_content_hook(user, sender, to, soup, attachments)

    #确定外链任务：hook显式返回优先，否则尝试从正文提取超链接
    if hook_urls:
        urls = [hook_urls] if isinstance(hook_urls, str) else [str(u).strip() for u in hook_urls if str(u).strip()]
        book_title = title
    elif soup and not forceArticle:
        urls = CollectSoupLinks(soup, forceLinks)
        book_title = title
    else:
        urls = []
        book_title = title

    #只处理图像附件，判断邮件是否包含图片
    imgs = [(f, c) for f, c in (attachments or []) if (guess_type(f)[0] or '').startswith('image/')]

    #判断链接是否为电子书直链
    isBook = bool(urls and ((dest in ('book', 'file', 'download')) or
        urls[0].lower().endswith(('.mobi', '.epub', '.docx', '.pdf', '.txt', '.doc', '.rtf'))))

    #判定是否能够合并为单文档推送：
    #1. 既有外链又有邮件正文
    #2. 邮件正文没有内嵌图片（有图片时通过任务队列传递不可靠，转为分开推送）
    #3. 外链不是下载外部电子书文件，不是 debug
    can_merge = bool(urls and soup and not imgs and not isBook and dest != 'debug')

    mail_text = ''
    if can_merge:
        action = 'merge'
        mail_text = str(soup)
        #边界条件1：控制传递大小，避免超出任务队列payload限制（如GAE的100KB限制）
        MAX_MERGE_TEXT_SIZE = 70 * 1024  # 70KB
        if len(mail_text) > MAX_MERGE_TEXT_SIZE:
            cut_idx = mail_text[:MAX_MERGE_TEXT_SIZE].rfind('<')
            if cut_idx > 0:
                mail_text = mail_text[:cut_idx]
            mail_text += '<p><i>[Content truncated due to size limit]</i></p></body></html>'
    elif dest == 'debug':
        action = 'debug'
    elif isBook:
        action = 'download'
    else:
        action = ''

    if urls:
        #若不能合并且soup有效，为外链电子书标题追加后缀以防混淆
        if not can_merge and soup:
            book_title = f"{title} - Articles"

        params = {'userName': userName,
                 'urls': '|'.join(urls),
                 'action': action,
                 'text': mail_text,
                 'key': user.share_links.get('key', ''),
                 'title': book_title,
                 'language': language}
        create_url2book_task(params)

    #推送邮件正文：
    #若不能合并推送（如无外链，或因含有图片/下载等原因分流），且soup有效时，作为独立邮件正文推送
    if soup and not can_merge and (hook_urls or not urls or imgs or isBook):
        if imgs:
            book = html_to_book(str(soup), title, user, imgs)
        else:
            book = (f'{title}.html', str(soup).encode('utf-8'))

        send_to_kindle(user, title, book, fileWithTime=False)
    
    return 'OK'

#解码邮件主题
def DecodeSubject(subject, default='NoSubject'):
    if not subject:
        subject = default
    elif subject.startswith('=?') and subject.endswith('?='):
        decoded_parts = []
        try:
            for s, c in email.header.decode_header(subject):
                if isinstance(s, bytes):
                    decoded_parts.append(s.decode(c or 'us-ascii', errors='replace'))
                else:
                    decoded_parts.append(s)
            return ''.join(decoded_parts).strip()
        except Exception as e:
            pass
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
    for line in text.splitlines():
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
def CreateMailSoup(subject: str, txtBodies: list, htmlBodies: list):
    if not htmlBodies: #此邮件为纯文本邮件，将文本信息转换为HTML格式
        html = ConvertTextToHtml(subject, '\n'.join(txtBodies))
        htmlBodies = [html] if html else []

    if not htmlBodies:
        return None
    
    htmlBodies = [item.replace('<wbr>', '') for item in htmlBodies]
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
#forceLinks: 不管文章内容如何，强制提取链接
def CollectSoupLinks(soup, forceLinks):
    body = soup.body
    links = []
    emptyLineNum = 0 #放宽一点条件，允许链接之间有一个空行，因为有的应用会添加一个空的<div>
    #优先通过显示的文本提取链接，可见即可得
    for txt in body.stripped_strings:
        if IsHyperLink(txt):
            emptyLineNum = 0
            if txt not in links:
                links.append(txt)
        else:
            #如果是多个链接，则必须一行一个，不能留空，除非强制提取链接
            #这个处理是为了去除部分邮件客户端在邮件末尾添加的一个广告链接或签名链接
            if not txt:
                emptyLineNum += 1
            if not forceLinks and emptyLineNum >= 2:
                break

    if not links: #如果在显示文本中找不到连接，则通过a标签进行查找
        links = [item['href'] for item in body.find_all('a', attrs={'href': True})]
            
    #如果有相对路径，则在里面找一个绝对路径，然后转换其他的链接为绝对路径
    hasRelativePath = any(not item.startswith('http') for item in links)
    fullPath = next((item for item in links if item.startswith('http')), '')
    text = ' '.join([txt for txt in body.stripped_strings])
    for item in links: #扣除显示出来的链接文本
        text = text.replace(item, '')

    if hasRelativePath and fullPath:
        links = [(item if item.startswith('http') else urljoin(fullPath, item))
            for item in links]

    #如果字数太多，则认为直接推送正文内容
    if not forceLinks and (len(text) > WORDCNT_THRESHOLD_APMAIL):
        links = []

    return links

#将接收到的邮件暂存到数据库
#暂时不支持保存附件
def SaveInEmailToDb(user, sender, to, subject, txtBodies, htmlBodies, attachments):
    to = ', '.join(to) if isinstance(to, list) else str(to)
    attachNames = [{'name': item[0]} for item in attachments]
    size = sum([len(item) for item in [*txtBodies, *htmlBodies]])

    #GAE对json字段里面的子字段也有1500字节限制，所以这里只能转换为一个字符串
    body = json.dumps({'txtBodies': txtBodies, 'htmlBodies': htmlBodies, 'attachments': attachNames})
    InBox.create(user=user.name, sender=sender, to=to, subject=subject, status='unread', size=size, body=body)

#将接收到的mobi文件转换为epub然后发送到Kindle
#返回一个已经发送的文件名列表
def TransferMobi(attachments, user):
    ret = []
    if not attachments or (user.book_cfg('type') != 'epub'):
        return ret

    for fname, attachData in attachments:
        name, ext = os.path.splitext(fname)
        if ext in (('.mobi', '.prc', '.azw', '.azw3', '.pobi')):
            book = convert_book(attachData, ext[1:], user, options={'dont_save_webshelf': True})
            if book:
                name = os.path.basename(name) + '.epub'
                #这里在 "投递日志" 中记录文件后缀，明确表明是转换过的电子书
                send_to_kindle(user, name, (name, book), fileWithTime=False)
                ret.append(name)
        else:
            default_log.warning(f'Skipping unsupported mail attachment: {fname}')
    return ret

#webmail网页
@bpInBoundEmail.route("/webmail", endpoint='WebmailRoute')
@login_required()
def WebmailRoute(user: KeUser):
    return render_template('webmail.html', user=user)

#列出所有的邮件
@bpInBoundEmail.get("/webmail/list", endpoint='WebMailListRoute')
@login_required(forAjax=True)
def WebMailListRoute(user: KeUser):
    includes = request.args.get('includes')
    qry = InBox.select().where(InBox.user == user.name).dicts()
    if includes != 'all': #剔除已经被标识为删除的邮件
        all_mails = sorted((item for item in qry if item.get('status') != 'deleted'), 
            key=itemgetter('datetime'), reverse=True)
    else:
        all_mails = sorted(qry, key=itemgetter('datetime'), reverse=True)

    for m in all_mails:
        m.pop('body', None)
        m.pop('attachments', None)
        date = m['datetime'] + datetime.timedelta(hours=user.cfg('timezone'))
        m['datetime'] = date.strftime("%Y-%m-%d %H:%M:%S")
    return {'status': 'ok', 'data': all_mails}

#获取某个邮件的文本内容
@bpInBoundEmail.get("/webmail/content/<id_>", endpoint='WebMailContentRoute')
@login_required(forAjax=True)
def WebMailContentRoute(id_: str, user: KeUser):
    dbItem = InBox.get_by_id_or_none(id_)
    content = ''
    body = dbItem.body if dbItem else ''
    try:
        if body and not isinstance(body, dict):
            body = json.loads(body)
        if body:
            content = body.get('htmlBodies') or body.get('txtBodies') or []
            content.append('<br/>') #添加附件名字
            content.extend([f'&#128206; {item.get("name")}' for item in (body.get('attachments') or [])])
            content = '<br/>'.join(content).replace('\r\n', '<br/>').replace('\n', '<br/>')
    except Exception as e:
        default_log.warning(f'Get mail content failed: {id_}, {e}')
        pass
    return {'status': 'ok', 'content': content}

#设置某个邮件的已读状态
@bpInBoundEmail.post("/webmail/status", endpoint='WebMailStatusPost')
@login_required(forAjax=True)
def WebMailStatusPost(user: KeUser):
    id_ = request.form.get('id')
    status = request.form.get('status')
    dbItem = InBox.get_by_id_or_none(id_)
    if dbItem and status:
        dbItem.status = status
        dbItem.save()
        return {'status': 'ok'}
    else:
        return {'status': _("Some parameters are missing or wrong.")}

#删除一个或多个邮件
@bpInBoundEmail.post("/webmail/delete", endpoint='WebMailDeletePost')
@login_required(forAjax=True)
def WebMailDeletePost(user: KeUser):
    ids = request.form.get('ids', '')
    if not ids:
        return {'status': _("Some parameters are missing or wrong.")}

    for id_ in ids.split(','):
        dbItem = InBox.get_by_id_or_none(id_)
        if dbItem: #这里不删除，只是做一个删除标识，一天以后由RemoveLogs()自动清理
            dbItem.status = 'deleted'
            dbItem.save()
    return {'status': 'ok'}

#取消删除一个或多个邮件
@bpInBoundEmail.post("/webmail/undelete", endpoint='WebMailUnDeletePost')
@login_required(forAjax=True)
def WebMailUnDeletePost(user: KeUser):
    ids = request.form.get('ids', '')
    if not ids:
        return {'status': _("Some parameters are missing or wrong.")}

    for id_ in ids.split(','):
        dbItem = InBox.get_by_id_or_none(id_)
        if dbItem:
            dbItem.status = 'read'
            dbItem.save()
    return {'status': 'ok'}

#回复或转发邮件
@bpInBoundEmail.post("/webmail/send", endpoint='WebMailReplyPost')
@login_required(forAjax=True)
def WebMailReplyPost(user: KeUser):
    form = request.form
    to = form.get('to')
    subject = form.get('subject')
    content = form.get('content', '')
    text = form.get('text', '')
    attachment = form.get('attachment')
    name = form.get('attach_name')
    if not all((to, subject, content, text)):
        return {'status': _("Some parameters are missing or wrong.")}

    attachments = [(name, attachment.encode('utf-8'))] if attachment and name else None
    status = send_html_mail(user, to, subject, content, body=text, attachments=attachments)
    return {'status': status}
