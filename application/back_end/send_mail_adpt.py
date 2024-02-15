#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#封装发送邮件的一些函数
#Author: cdhigh <https://github.com/cdhigh>
#gae mail api
#https://cloud.google.com/appengine/docs/standard/python3/reference/services/bundled/google/appengine/api/mail
#https://cloud.google.com/appengine/docs/standard/python3/services/mail
import os, datetime, zipfile
from ..utils import local_time, ke_decrypt
from ..base_handler import save_delivery_log

try:
    from google.appengine.api import mail as gae_mail
    from google.appengine.api.mail_errors import InvalidSenderError, InvalidAttachmentTypeError, InvalidEmailError
    from google.appengine.runtime.apiproxy_errors import OverQuotaError, DeadlineExceededError
except ImportError:
    gae_mail = None

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Email, Content, Mail, Attachment
except ImportError:
    SendGridAPIClient = None

try:
    from smtp_mail import smtp_send_mail
except ImportError:
    smtp_send_mail = None

#发送邮件
#title: 邮件标题
#attachment: 附件二进制内容，或元祖 (filename, content)
#fileWithTime: 发送的附件文件名是否附带当前时间
def send_to_kindle(user, title, attachment, fileWithTime=True):
    lcTime = local_time('%Y-%m-%d_%H-%M', user.timezone)
    subject = f"KindleEar {lcTime}"

    if not isinstance(attachment, tuple):
        lcTime = "({})".format(lcTime) if fileWithTime else ""
        fileName = f"{title}{lcTime}.{user.book_type}"
        attachment = (fileName, attachment)

    if not isinstance(attachment, list):
        attachments = [attachment]
    
    status = 'ok'
    body = "Deliver from KindleEar"
    try:
        send_mail(user, user.kindle_email, subject, body, attachments)
    except Exception as e:
        status = str(e)
        default_log.warning(f'Failed to send mail "{title}": {status}')
    
    save_delivery_log(user, title, len(attachment), status=status)

#统一的发送邮件函数
def send_mail(user, to, subject, body, attachments=None, html=None):
    if not isinstance(to, list) and (',' in to):
        to = to.split(',')
    sm_service = user.send_mail_service
    srv_type = sm_service.get('service', 'gae')
    data = {'sender': os.getenv('SRC_EMAIL'), 'to': to, 'subject': subject, 'body': body}
    if attachments:
        data['attachments'] = attachments
    if html:
        if isinstance(html, str):
            html = html.encode("utf-8")
        data['html'] = html

    default_log.info(f'Sending email using service : {srv_type}')
    if srv_type == 'gae':
        gae_mail.send_mail(**data)
    elif srv_type == 'sendgrid':
        apikey = sm_service.get('apikey', '')
        grid_send_mail(apikey=apikey, **data)
    elif srv_type == 'smtp':
        data['host'] = sm_service.get('host', '')
        data['port'] = sm_service.get('port', 587)
        data['username'] = sm_service.get('username', '')
        data['password'] = ke_decrypt(sm_service.get('password', ''), user.secret_key)
        smtp_send_mail(**data)
    elif srv_type == 'local':
        save_mail_to_local(sm_service.get('save_path', 'tests/debug_mail'), **data)
    else:
        raise ValueError(f'Unknown send mail service [{srv_type}]')

#发送一个HTML邮件
#user: KeUser实例
#to: 收件地址，可以是一个单独的字符串，或一个字符串列表，对应发送到多个地址
#subject: 邮件标题
#html: 邮件正文的HTML内容
#attachments: 附件文件名和二进制内容，[(fileName, content),...]
#body: 可选的额外文本内容
def send_html_mail(user, to, subject, html, attachments=None, body=None):
    if not body or not isinstance(body, str):
        body = "Deliver from KindlerEar, refers to html part."
    
    status = 'ok'
    try:
        send_mail(user, to, subject, body, attachments=attachments, html=html)
    except Exception as e:
        status = str(e)
    
    size = len(html or body) + sum([len(c) for f, c in (attachments or [])])
    save_delivery_log(user, subject, size, status=status, to=to)

#SendGrid发送邮件
#sender:: 发送者地址
#to: 收件地址，可以是一个单独的字符串，或一个字符串列表，对应发送到多个地址
#subject: 邮件标题
#body: 邮件正文纯文本内容
#html: 邮件正文HTML
#attachment: [(fileName, attachment),]
#tz: 时区
def grid_send_mail(apikey, sender, to, subject, body, html=None, attachments=None):
    global default_log
    sgClient = SendGridAPIClient(apikey)
    bodyContent = Content("text/plain", body)
    htmlContent = Content("text/html", html) if html else None
    message = Mail(from_email=sender, to_emails=to, subject=subject, plain_text_content=bodyContent, 
        html_content=htmlContent)

    for fileName, data in (attachments or []):
        attachedFile = Attachment(
            file_content=FileContent(base64.b64encode(data).decode()),
            file_name=FileName(fileName),
            file_type=FileType("application/x-mobipocket-ebook"),
            disposition=Disposition("attachment"),
            content_id="KindleEar")
        message.add_attachment(attachedFile)

    response = sgClient.send(message)
    if response.status_code not in (200, 202):
        raise Exception(f'sendgrid failed: {response.status_code}')
    
def save_mail_to_local(dest_dir, subject, body, attachments=None, html=None, **kwargs):
    attachments = attachments or []
    mailDir = os.path.join(appDir, dest_dir)
    if not os.path.exists(mailDir):
        os.makedirs(mailDir)

    subject = subject.replace(':', '_').replace('/', '_').replace('\\', '_').replace('?', '_').replace('*', '_')
    now = str(datetime.datetime.now().strftime('%H-%M-%S'))
    if len(body) < 100 and not html and len(attachments) == 1:
        filename, content = attachments[0]
        b, ext = os.path.splitext(filename)
        mailFilename = os.path.join(mailDir, f'{b}_{now}{ext}')
        with open(mailFilename, 'wb') as f:
            f.write(content)
    else:
        mailFilename = os.path.join(mailDir, f'{subject}_{now}.zip')
        mailFile = zipfile.ZipFile(mailFilename, 'w')
        mailFile.writestr('textbody.txt', body)
        if html:
            mailFile.writestr('index.html', html)
        for fn, content in attachments:
            mailFile.writestr(fn, content)
