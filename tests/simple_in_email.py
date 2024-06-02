#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import os, requests
from urllib.parse import quote, urljoin
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formatdate
from email.encoders import encode_base64

def build_mail(sender, to, subject, text, html=None, files=None):
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = to
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach(MIMEText(text))
    if html:
        msg.attach(MIMEText(html, 'html'))

    for f in (files or []):
        part = MIMEBase('application', "octet-stream")
        part.set_payload(open(f, 'rb').read())
        encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(f)}"')
        msg.attach(part)

    return msg.as_string()

#data是一个字典{}
def postmail(sender, to, subject, text, html=None, files=None, mType=''):
    to = f'{to}@kindleear.appspotmail.com'
    url = f'/_ah/mail/{quote(to)}' if mType == 'gae' else '/mail'
    url = urljoin('http://localhost:5000/', url)
    data = {'sender': sender, 'to': to, 'subject': subject, 'text': text, 'html': html,
        'files': files}
    return requests.post(url, data=build_mail(**data))

html = '<div><a href="https://www.donga.com/news/Economy/article/all/20101102/32286302/1">https://www.donga.com/news/Economy/article/all/20101102/32286302/1</a></div><div>​</div><div>​<a href="https://www.donga.com/news/Politics/article/all/20101009/31731055/2">https://www.donga.com/news/Politics/article/all/20101009/31731055/2</a></div><div>​</div><div>​<a href="https://biz.chosun.com/site/data/html_dir/2010/08/04/2010080400160.html">https://biz.chosun.com/site/data/html_dir/2010/08/04/2010080400160.html</a></div><div>​</div><div>​<a href="https://www.chosun.com/site/data/html_dir/2010/11/01/2010110101133.html">https://www.chosun.com/site/data/html_dir/2010/11/01/2010110101133.html</a></div><div>​</div><div>​<a href="https://ko.m.wikisource.org/wiki/G20_%EC%A0%95%EC%83%81%ED%9A%8C%EC%9D%98_%EA%B2%BD%ED%98%B8%EC%95%88%EC%A0%84%EC%9D%84_%EC%9C%84%ED%95%9C_%ED%8A%B9%EB%B3%84%EB%B2%95">https://ko.m.wikisource.org/wiki/G20_%EC%A0%95%EC%83%81%ED%9A%8C%EC%9D%98_%EA%B2%BD%ED%98%B8%EC%95%88%EC%A0%84%EC%9D%84_%EC%9C%84%ED%95%9C_%ED%8A%B9%EB%B3%84%EB%B2%95</a></div><br/>'

postmail('ak@gmail.com', 'read', 'test !lang=ko', 'delivery from ke', html)
