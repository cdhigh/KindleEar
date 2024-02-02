#!/usr/bin/env python3
# encoding: UTF-8
#使用SMTP发送邮件

import smtplib
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.encoders import encode_base64
from email.mime.multipart import MIMEMultipart

def send_smtp_mail(sender, to, subject, text, smtp_host, username, password, smtp_port=None, 
    text_html=None, attachments=None, encoding='utf-8'):
    
    if ':' in smtp_host:
        smtp_host, smtp_port = smtp_host.split(':', 2)
        smtp_port = int(smtp_port)
    else:
        smtp_port = 25
    
    to = to if isinstance(to, list) else [to]
    message = MIMEMultipart('alternative') if text_html else MIMEMultipart()
    message['Subject'] = subject
    message['From'] = sender
    message['To'] = ', '.join(to)
    message.attach(MIMEText(text, 'plain', _charset=encoding))
    if text_html:
        message.attach(MIMEText(text_html, 'html', _charset=encoding))
    
    for filename, content in (attachments or {}).items():
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(content)
        encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        message.attach(part)

    smtp = smtplib.SMTP(host=smtp_host, port=smtp_port)
    if username and password:
        smtp.connect(smtp_host, smtp_port)
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(user=username, password=password)
    smtp.sendmail(sender, to, message.as_string())
    smtp.quit()
