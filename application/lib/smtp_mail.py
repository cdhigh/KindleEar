#!/usr/bin/env python3
# encoding: UTF-8
#使用SMTP发送邮件
#Author: cdhigh <https://github.com/cdhigh>
import smtplib
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.encoders import encode_base64
from email.mime.multipart import MIMEMultipart

def smtp_send_mail(sender, to, subject, body, host, username, password, port=None, 
    html=None, attachments=None, encoding='utf-8'):
    if ':' in host:
        host, port = host.split(':', 1)
        port = int(port)
    elif not port:
        port = 587 #587-TLS, 465-SSL, 25-Nocrpt
    else:
        port = int(port)
    
    to = [to] if isinstance(to, str) else to
    message = MIMEMultipart('alternative') if html else MIMEMultipart()
    message['Subject'] = subject
    message['From'] = sender
    message['To'] = ', '.join(to)
    message.attach(MIMEText(body, 'plain', _charset=encoding))
    if html:
        message.attach(MIMEText(html, 'html', _charset=encoding))
    
    for filename, content in (attachments or []):
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(content)
        part.add_header('Content-Disposition', 'attachment', filename=('utf-8', '', filename))
        encode_base64(part)
        message.attach(part)

    klass = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
    with klass(host=host, port=port) as server:
        #server.set_debuglevel(0) #0-no debug info, 1-base, 2- verbose
        server.connect(host, port)
        server.ehlo()
        if port == 587:
            server.starttls()
            server.ehlo()
        server.login(user=username, password=password)
        server.sendmail(sender, to, message.as_string())

