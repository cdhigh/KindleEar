#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#主要针对网页显示之类的一些公共支持工具函数

import os, datetime, hashlib, time, base64
from urllib.parse import urlparse
from bottle import request, redirect
from bs4 import BeautifulSoup
from apps.db_models import *
from google.appengine.api import mail
import sendgrid
from sendgrid.helpers.mail import Email, Content, Mail, Attachment
from google.appengine.api.mail_errors import (InvalidSenderError,
                                           InvalidAttachmentTypeError)
from google.appengine.runtime.apiproxy_errors import (OverQuotaError,
                                                DeadlineExceededError)

#一些共同的工具函数，工具函数都是小写+下划线形式

#安装多语种支持插件，设置网页显示语种，在每个请求前执行
def set_session_lang():
    session = current_session()
    if not session.lang:
        session.lang = browser_lang()
        session.save()
    install_translation(session.lang)
    
#安装网页多语种支持翻译器，当前使用Python内置的gettext翻译器
#lang: 语言名字，可选列表在main.py|supported_languages
def install_translation(lang):
    global jinja2Env #builtins dict
    trans = gettext.translation('lang', 'i18n', languages=[lang])
    trans.install(True)
    jinja2Env.install_gettext_translations(trans)

#获取当前session，返回一个类字典，可以通过字符串访问，也可以通过属性来访问
def current_session():
    return request.environ.get('beaker.session', {})

#判断是否已经登录，返回 True/False
def logined():
    return True if request.environ.get('beaker.session', {}).login == 1 else False

#如果对应的用户没有登录，则跳转到登录界面，此函数不会再返回，如果已经登录，返回当前session实例
#userName: 为空对应任意用户，否则仅判断特定用户
#forAjax: 网页Javascript脚本和服务器通讯使用
def login_required(userName=None, forAjax=False):
    session = current_session()
    if (session.login != 1) or (username and userName != session.userName):
        redirect('/needloginforajax' if forAjax else '/login')
    else:
        return session

#查询当前登录用户名，如果没有登录，则跳转到登录界面
#返回一个数据库行实例，而不是一个字符串
def get_current_user(forAjax=False):
    session = current_session()
    userName = session.userName
    if (session.login != 1) or not userName:
        redirect('/needloginforajax' if forAjax else '/login')

    u = KeUser.all().filter("name = ", userName).get()
    if not u:
        redirect('/needloginforajax' if forAjax else '/login')
    return u

#获取sendgrid的apikey，返回(enable, apikey)
def get_sg_apikey(userName):
    user = KeUser.all().filter("name = ", userName).get()
    return (user.sg_enable, user.sg_apikey) if user else (False, "")

#返回用户浏览器支持的语种
def browser_lang():
    global supported_languages #builtins dict
    availableLanguages = supported_languages
    lang = request.environ.get('HTTP_ACCEPT_LANGUAGE', "en")
    #分析浏览器支持那些语种，为了效率考虑就不用全功能的分析语种和排序了
    #此字符串类似：zh-cn,en;q=0.8,ko;q=0.5,zh-tw;q=0.3
    langs = lang.lower().replace(';', ',').replace('_', '-').split(',')
    langs = [c.strip() for c in langs if '=' not in c]
    baseLangs = [c.split('-')[0] for c in langs if '-' in c]
    langs.extend(baseLangs)
    
    for c in langs: #浏览器直接支持的语种
        if c in availableLanguages:
            return c

    for c in langs: #同一语种的其他可选语言
        for sl in availableLanguages:
            if sl.startswith(c):
                return sl

    return availableLanguages[0]
    
#记录投递记录到数据库
def deliver_log(name, to, book, size, status='ok', tz=TIMEZONE):
    global default_log
    try:
        dl = DeliverLog(username=name, to=to, size=size,
           time=local_time(tz=tz), datetime=datetime.datetime.utcnow(),
           book=book, status=status)
        dl.put()
    except Exception as e:
        default_log.warn('DeliverLog failed to save: {}'.format(e))

def sendgrid_sendmail(apikey, src, to, subject, body, attachments):
    global default_log
    fileName, data = attachments[0]
    sg = sendgrid.SendGridAPIClient(apikey=apikey)
    content = Content("text/plain", body)
    encoded = base64.b64encode(data).decode()

    attachment = Attachment()
    attachment.content = encoded
    attachment.type = "application/x-mobipocket-ebook"
    attachment.filename = fileName
    attachment.disposition = "attachment"
    attachment.content_id = "kindleear"

    mail = Mail(Email(src), subject, Email(to), content)
    mail.add_attachment(attachment)
    response = sg.client.mail.send.post(request_body=mail.get())
    if response.status_code == 202:
        default_log.warn('Sendgrid succeed send mail : {}'.format(fileName))
    else:
        default_log.warn('Sendgrid send mail failed, error code: {}'.format(response.status_code))
    return response.status_code

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
    
    sgEnable, sgApikey = get_sg_apikey(userName)
    for i in range(SENDMAIL_RETRY_CNT + 1):
        try:
            if sgEnable and sgApikey:
                sendgrid_sendmail(sgApikey, SRC_EMAIL, to, mailSubject, "Deliver from KindleEar", attachments=[(filename, attachment),])
            else:
                mail.send_mail(SRC_EMAIL, to, mailSubject, "Deliver from KindleEar", attachments=[(filename, attachment),])
        except OverQuotaError as e:
            deliver_log(userName, str(to), title, len(attachment), tz=tz, status='over quota')
            if i < SENDMAIL_RETRY_CNT:
                default_log.warn('Overquota when sendmail to {}, retry!'.format(to))
                time.sleep(10)
            else:
                default_log.warn('Overquota when sendmail to {}.'.format(to))
                break
        except InvalidSenderError as e:
            default_log.warn('UNAUTHORIZED_SENDER when sendmail to {}'.format(to))
            deliver_log(userName, str(to), title, len(attachment), tz=tz, status='wrong SRC_EMAIL')
            break
        except InvalidAttachmentTypeError as e: #继续发送一次
            fileName = fileName.replace('.', '_')
            title = title.replace('.', '_')
        except DeadlineExceededError as e:
            status = "sendgrid timeout" if sgEnable and sgApikey else "timeout"
            deliver_log(userName, str(to), title, len(attachment), tz=tz, status=status)
            if i < SENDMAIL_RETRY_CNT:
                default_log.warn('Timeout when sendmail to {}:{}, retry!'.format(to, str(e)))
                time.sleep(5)
            else:
                default_log.warn('Timeout when sendmail to {}:{}'.format(to, str(e)))
                break
        except Exception as e:
            status = "sendgrid failed" if sgEnable and sgApikey else "send failed"
            deliver_log(userName, str(to), title, len(attachment), tz=tz, status=status)
            if i < SENDMAIL_RETRY_CNT:
                default_log.warn('sendgrid sendmail to {} failed: {}'.format(to, str(e)))
                time.sleep(5)
            else:
                default_log.warn('sendmail to {} failed: {}'.format(to, str(e)))
                break
        else:
            status = "sendgrid ok" if sgEnable and sgApikey else "ok"
            deliver_log(userName, str(to), title, len(attachment), tz=tz, status=status)
            break

#发送一个HTML邮件
#userName: 用户名
#to: 收件地址，可以是一个单独的字符串，或一个字符串列表，对应发送到多个地址
#title: 邮件标题
#html: 邮件正文的HTML内容
#attachments: 附件文件名和二进制内容，[(fileName, content),...]
#tz: 时区
#textContent: 可选的额外文本内容
def send_html_mail(userName, to, title, html, attachments, tz=TIMEZONE, textContent=None):
    global default_log
    if not textContent or not isinstance(textContent, str):
        textContent = "Deliver from KindlerEar, refers to html part."
    
    if isinstance(html, str):
        html = html.encode("utf-8")
        
    for i in range(SENDMAIL_RETRY_CNT + 1):
        try:
            if attachments:
                if html:
                    mail.send_mail(SRC_EMAIL, to, title, textContent, html=html, attachments=attachments)
                else:
                    mail.send_mail(SRC_EMAIL, to, title, textContent, attachments=attachments)
            else:
                if html:
                    mail.send_mail(SRC_EMAIL, to, title, textContent, html=html)
                else:
                    mail.send_mail(SRC_EMAIL, to, title, textContent)
        except OverQuotaError as e:
            default_log.warn('Overquota when sendmail to {}:{}'.format(to, str(e)))
            deliver_log(userName, str(to), title, 0, tz=tz, status='over quota')
            break
        except InvalidSenderError as e:
            default_log.warn('UNAUTHORIZED_SENDER when sendmail to {}:{}'.format(to, str(e)))
            deliver_log(userName, str(to), title, 0, tz=tz, status='wrong SRC_EMAIL')
            break
        except InvalidAttachmentTypeError as e:
            default_log.warn('InvalidAttachmentTypeError when sendmail to {}:{}'.format(to, str(e)))
            deliver_log(userName, str(to), title, 0, tz=tz, status='invalid postfix')
            break
        except DeadlineExceededError as e:
            if i < SENDMAIL_RETRY_CNT:
                default_log.warn('Timeout when sendmail to {}:{}, retry!'.format(to, str(e)))
                time.sleep(5)
            else:
                default_log.warn('Timeout when sendmail to {}:{}'.format(to, str(e)))
                deliver_log(userName, str(to), title, 0, tz=tz, status='timeout')
                break
        except Exception as e:
            default_log.warn('Sendmail to %s failed:%s.<%s>' % (to, str(e), type(e)))
            deliver_log(userName, str(to), title, 0, tz=tz, status='send failed')
            break
        else:
            if attachments:
                size = len(html or textContent) + sum([len(c) for f, c in attachments])
            else:
                size = len(html or textContent)
            deliver_log(userName, str(to), title, size, tz=tz)
            break

def render_page(templateFile, title='KindleEar', **kwargs):
    global jinja2Env
    session = current_session()
    kwargs.setdefault('nickname', session.get('username', ''))
    kwargs.setdefault('lang', session.get('lang', 'en'))
    kwargs.setdefault('version', __Version__)
    html = jinja2Env.get_template(templateFile).render(title=title, **kwargs)
    
    #将内部的小图像转换为内嵌的base64编码格式，减小http请求数量，提升效率
    soup = BeautifulSoup(html, 'lxml')
    for img in soup.find_all('img'):
        imgUrl = img['src'] if 'src' in img.attrs else ''
        if not imgUrl or imgUrl.startswith('data:'):
            continue
        
        #假定没有外链的图片，所有的图片都是本站的
        parts = urlparse(imgUrl)
        imgPath = parts.path
        if imgPath.startswith('/'):
            imgPath = imgPath[1:]
        
        d = ''
        try: #这个在调试环境是不行的，不过部署好就可以用了
            with open(imgPath, "rb") as f:
                d = f.read()
        except Exception as e:
            continue
        else:
            mime = imghdr.what(None, d)
            if mime:
                base64str = base64.b64encode(d)
                if len(base64str) < 30000:
                    data = 'data:image/{};base64,{}'.format(mime, base64str)
                    img['src'] = data
        
    return str(soup)
