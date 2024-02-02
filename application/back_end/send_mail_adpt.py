#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#封装发送邮件的一些函数
#Author: cdhigh <https://github.com/cdhigh>
#gae mail api
#https://cloud.google.com/appengine/docs/standard/python3/reference/services/bundled/google/appengine/api/mail
#https://cloud.google.com/appengine/docs/standard/python3/services/mail

from config import *

if SEND_MAIL_SERVICE == "gae":
    from google.appengine.api.mail import send_mail
    from google.appengine.api.mail_errors import InvalidSenderError, InvalidAttachmentTypeError, InvalidEmailError
    from google.appengine.runtime.apiproxy_errors import OverQuotaError, DeadlineExceededError
elif SEND_MAIL_SERVICE == "sendgrid":
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Email, Content, Mail, Attachment
elif SEND_MAIL_SERVICE == "smtp":
    from smtp_mail import send_smtp_mail

#发送邮件
#userName: 用户名
#to: 收件地址，可以是一个单独的字符串，或一个字符串列表，对应发送到多个地址
#title: 邮件标题
#bookType: 书籍类型 epub 或 mobi
#attachment: 附件二进制内容
#tz: 时区
#fileWithTime: 发送的附件文件名是否附带当前时间
def send_to_kindle(userName, to, title, bookType, attachment, tz=TIMEZONE, fileWithTime=True):
    global default_log
    lcTime = local_time('%Y-%m-%d_%H-%M', tz)
    mailSubject = "KindleEar {}".format(lcTime)
    lcTime = "({})".format(lcTime) if fileWithTime else ""
    ext = ".{}".format(bookType) if bookType else ""
    fileName = "{}{}{}".format(title, lcTime, ext)
    
    try:
        send_mail(SRC_EMAIL, to, mailSubject, "Deliver from KindleEar", attachments=[(fileName, attachment),])
    except Exception as e:
        record_sendmail_Error(userName, to, title, len(attachment), tz, e)
    else:
        save_delivery_log(userName, to, title, len(attachment), tz=tz, status='ok')

#发送一个HTML邮件
#userName: 用户名
#to: 收件地址，可以是一个单独的字符串，或一个字符串列表，对应发送到多个地址
#title: 邮件标题
#html: 邮件正文的HTML内容
#attachments: 附件文件名和二进制内容，[(fileName, content),...]
#tz: 时区
#textContent: 可选的额外文本内容
def send_html_mail(userName, to, title, html, attachments, tz=TIMEZONE, textContent=None):
    if not textContent or not isinstance(textContent, str):
        textContent = "Deliver from KindlerEar, refers to html part."
    
    if isinstance(html, str):
        html = html.encode("utf-8")
    
    extraArgs = {}
    if html:
        extraArgs['html'] = html
    if attachments:
        extraArgs['attachments'] = attachments

    try:
        send_mail(SRC_EMAIL, to, title, textContent, **extraArgs)
    except Exception as e:
        record_sendmail_Error(userName, to, title, len(attachment), tz, e)
    else:
        size = len(html or textContent) + sum([len(c) for f, c in (attachments or [])])
        save_delivery_log(userName, to, title, size, tz=tz)

if SEND_MAIL_SERVICE == "gae":
    #记录GAE发送邮件的异常
    def record_sendmail_Error(userName, to, title, bookSize, tz, e):
        global default_log
        if isinstance(e, OverQuotaError):
            info = 'Overquota when sendmail to {}.'.format(to)
            status = 'over quota'
        elif isinstance(e, InvalidSenderError):
            info = 'UNAUTHORIZED_SENDER when sendmail to {}'.format(to)
            status = 'wrong SRC_EMAIL'
        elif isinstance(e, InvalidAttachmentTypeError):
            info ='InvalidAttachmentTypeError when sendmail to {}'.format(to)
            status = 'wrong SRC_EMAIL'
        elif isinstance(e, DeadlineExceededError):
            info = 'Timeout when sendmail to {}'.format(to)
            status = "timeout"
        elif isinstance(e, InvalidEmailError):
            info = 'Invalid email address {}'.format(to)
            status = "invalid address"
        else:
            info = 'sendmail to {} failed: {}'.format(to, str(e))
            status = "failed"
        default_log.warning(info)
        save_delivery_log(userName, to, title, bookSize, tz=tz, status=status)
elif SEND_MAIL_SERVICE == "sendgrid":
    #SendGrid发送邮件
    #sender:: 发送者地址
    #to: 收件地址，可以是一个单独的字符串，或一个字符串列表，对应发送到多个地址
    #subject: 邮件标题
    #body: 邮件正文纯文本内容
    #html: 邮件正文HTML
    #attachment: [(fileName, attachment),]
    #tz: 时区
    def send_mail(sender, to, subject, body, html=None, attachments=None):
        global default_log
        sgClient = SendGridAPIClient(SENDGRID_APIKEY)
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
            default_log.warning('Sendgrid failed, error code: {}'.format(response.status_code))

    #记录SendGrid发送邮件的异常
    def record_sendmail_Error(userName, to, title, bookSize, tz, e):
        global default_log
        default_log.warning('Sendgrid failed, error: {}'.format(e))
        save_delivery_log(userName, to, title, bookSize, tz=tz, status="failed")
elif SEND_MAIL_SERVICE == "smtp":
    def send_mail(sender, to, subject, body, html=None, attachments=None):
        send_smtp_mail(sender=sender, to=to, subject=subject, text=body, smtp_host=SMTP_HOST, 
            username=SMTP_USER, password=SMTP_PASSWORD, smtp_port=SMTP_PORT, 
            attachments=attachments)
    
    #记录SMTP发送邮件的异常
    def record_sendmail_Error(userName, to, title, bookSize, tz, e):
        global default_log
        default_log.warning('Send mail by smtp failed, error: {}'.format(e))
        save_delivery_log(userName, to, title, bookSize, tz=tz, status="failed")
