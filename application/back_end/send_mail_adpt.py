#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#封装发送邮件的一些函数
#Author: cdhigh <https://github.com/cdhigh>
#gae mail api
#https://cloud.google.com/appengine/docs/standard/python3/reference/services/bundled/google/appengine/api/mail
#https://cloud.google.com/appengine/docs/standard/python3/services/mail
import os, datetime, zipfile, base64
from ..ke_utils import str_to_bool, sanitize_filename
from ..base_handler import save_delivery_log

#google.appengine will apply patch for os.env module
hideMailLocal = str_to_bool(os.getenv('HIDE_MAIL_TO_LOCAL'))

#判断是否是部署在gae平台
if os.getenv('DATABASE_URL') == 'datastore':
    try:
        from google.appengine.api import mail as gae_mail
    except ImportError:
        gae_mail = None
else:
    gae_mail = None

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Email, Content, Mail, Attachment, FileContent, FileName, FileType, Disposition
except ImportError:
    SendGridAPIClient = None

try:
    from mailjet_rest import Client as MailjetClient
except ImportError:
    MailjetClient = None

from smtp_mail import smtp_send_mail

#返回当前可用的发送邮件服务列表
def avaliable_sm_services():
    sm = {}
    if gae_mail:
        sm['gae'] = 'GAE'
    if smtp_send_mail:
        sm['smtp'] = 'SMTP'
    if SendGridAPIClient:
        sm['sendgrid'] = 'sendgrid'
    if MailjetClient:
        sm['mailjet'] = 'mailjet'
    if not hideMailLocal:
        sm['local'] = 'local (debug)'
    return sm

#发送邮件
#title: 邮件标题
#attachment: 附件二进制内容，或元祖 (filename, content)
#fileWithTime: 发送的附件文件名是否附带当前时间
#to: 目标邮件地址，可以为列表或逗号分隔的字符串，如果为空，则使用kindle_email
def send_to_kindle(user, title, attachment, fileWithTime=True, to=None):
    lcTime = user.local_time('%Y-%m-%d_%H-%M')
    subject = f"KindleEar {lcTime}"
    to = to or user.cfg('kindle_email')

    if not isinstance(attachment, (tuple, list)):
        lcTime = "({})".format(lcTime) if fileWithTime else ""
        fileName = f"{title}{lcTime}.{user.book_cfg('type')}"
        attachment = (fileName, attachment)
    
    if not isinstance(attachment, list):
        attachment = [attachment]

    status = 'ok'
    body = "Deliver from KindleEar"
    try:
        send_mail(user, to, subject, body, attachment)
    except Exception as e:
        status = str(e)[:500]
        default_log.warning(f'Failed to send mail "{title}": {status}')
    
    size = sum([len(a[1]) for a in attachment])
    save_delivery_log(user, title, size, status=status, to=to)

#统一的发送邮件函数
def send_mail(user, to, subject, body, attachments=None, html=None):
    sender = user.cfg('sender')
    if not sender:
        raise ValueError('Email of sender is empty')
    if not to:
        raise ValueError('Email of recipient is empty')
    elif not isinstance(to, list):
        to = to.split(',')
        
    sm_service = user.get_send_mail_service()
    srv_type = sm_service.get('service', '')
    data = {'sender': sender, 'to': to, 'subject': subject, 'body': body}
    if attachments:
        data['attachments'] = attachments
    if html:
        data['html'] = html.encode("utf-8") if isinstance(html, str) else html

    default_log.info(f'Sending email using service : {srv_type}')
    if srv_type == 'gae':
        gae_mail.send_mail(**data)
    elif srv_type == 'sendgrid':
        apikey = sm_service.get('apikey', '')
        grid_send_mail(apikey=apikey, **data)
    elif srv_type == 'mailjet':
        apikey = sm_service.get('apikey', '')
        secret_key = sm_service.get('secret_key', '')
        mailjet_send_mail(apikey=apikey, secret_key=secret_key, **data)
    elif srv_type == 'smtp':
        data['host'] = sm_service.get('host', '')
        data['port'] = sm_service.get('port', 587)
        data['username'] = sm_service.get('username', '')
        data['password'] = sm_service.get('password', '') #获取配置字典时已经解密
        smtp_send_mail(**data)
    elif srv_type == 'local':
        save_mail_to_local(sm_service.get('save_path', 'tests/debug_mail'), **data)
    else:
        raise ValueError(f'Unknown send mail service [{srv_type}]')

#发送一个HTML邮件
#user: KeUser实例
#to: 收件地址列表
#subject: 邮件标题
#html: 邮件正文的HTML内容
#attachments: 附件文件名和二进制内容，[(fileName, content),...]
#body: 可选的额外文本内容
#返回'ok'表示成功，否则返回错误描述字符串
def send_html_mail(user, to, subject, html, attachments=None, body=None):
    if not body or not isinstance(body, str):
        body = "Deliver from KindlerEar, refers to html part."
    
    status = 'ok'
    try:
        send_mail(user, to, subject, body, attachments=attachments, html=html)
    except Exception as e:
        status = str(e)[:500]
    
    size = len(html or body) + sum([len(c) for f, c in (attachments or [])])
    save_delivery_log(user, subject, size, status=status, to=to)
    return status

#SendGrid发送邮件
#sender:: 发送者地址
#to: 收件地址列表
#subject: 邮件标题
#body: 邮件正文纯文本内容
#html: 邮件正文HTML
#attachment: [(fileName, attachment),]
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

#Mailjet发送邮件
#sender:: 发送者地址
#to: 收件地址列表
#subject: 邮件标题
#body: 邮件正文纯文本内容
#html: 邮件正文HTML
#attachment: [(fileName, attachment),]
def mailjet_send_mail(apikey, secret_key, sender, to, subject, body, html=None, attachments=None):
    global default_log
    mjClient = MailjetClient(auth=(apikey, secret_key), version='v3.1')
    to = [{'Email': t, 'Name': t} for t in to]
    data = {'Messages': [{
          "From": {"Email": sender, "Name": sender},
          "To": to,
          "Subject": subject,
          "TextPart": body,
        }],}

    dataDict = data['Messages'][0]
    if html:
        dataDict['HTMLPart'] = html
    if attachments:
        dataDict['Attachments'] = []
        for fileName, content in (attachments or []):
            dataDict['Attachments'].append({"ContentType": "text/plain", "Filename": fileName,
                "Base64Content": base64.b64encode(content).decode()})

        
    resp = mjClient.send.create(data=data)
    if resp.status_code in (200, 202):
        status = resp.json()["Messages"][0]["Status"]
        #print(resp.json())
        if status != "success":
            raise Exception(f'mailjet failed: {status}')
    else:
        raise Exception(f'mailjet failed: {resp.status_code}')
    
def save_mail_to_local(dest_dir, subject, body, attachments=None, html=None, **kwargs):
    attachments = attachments or []
    mailDir = os.path.join(appDir, dest_dir)
    if not os.path.isdir(mailDir):
        os.makedirs(mailDir)

    now = str(datetime.datetime.now().strftime('%H-%M-%S'))
    if len(body) < 100 and not html and len(attachments) == 1:
        filename, content = attachments[0]
        b, ext = os.path.splitext(filename)
        mailFilename = os.path.join(mailDir, f'{sanitize_filename(b)}_{now}{ext}')
        with open(mailFilename, 'wb') as f:
            f.write(content)
    else:
        subject = sanitize_filename(subject)
        mailFilename = os.path.join(mailDir, f'{subject}_{now}.zip')
        mailFile = zipfile.ZipFile(mailFilename, 'w')
        mailFile.writestr('textbody.txt', body)
        if html:
            mailFile.writestr('index.html', html)
        for fn, content in attachments:
            mailFile.writestr(fn, content)
