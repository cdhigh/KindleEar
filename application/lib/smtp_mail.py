#!/usr/bin/env python3
# encoding: UTF-8
#使用SMTP发送邮件

import smtplib
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.encoders import encode_base64
from email.mime.multipart import MIMEMultipart

def smtp_send_mail(sender, to, subject, body, host, username, password, port=None, 
    html=None, attachments=None, encoding='utf-8'):
    if ':' in host:
        host, port = host.split(':', 2)
        port = int(port)
    else:
        port = 25
    
    to = to if isinstance(to, list) else [to]
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
        encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        message.attach(part)

    with smtplib.SMTP_SSL(host=host, port=port) as smtp_server:
        smtp_server.connect(host, port)
        smtp_server.ehlo()
        smtp_server.starttls()
        smtp_server.ehlo()
        smtp_server.login(user=username, password=password)
        smtp_server.sendmail(sender, to, message.as_string())
