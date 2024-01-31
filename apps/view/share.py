#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#保存到evernote或分享到社交媒体功能

import hashlib
from urllib.parse import unquote_plus
from bs4 import BeautifulSoup
from flask import Blueprint, render_template, request
from flask_babel import gettext as _
from apps.base_handler import *
from apps.back_end.db_models import *
from apps.utils import hide_email, ke_encrypt, ke_decrypt
from apps.back_end.send_mail_adpt import send_html_mail
from books.base_url_book import BaseUrlBook
from lib.pocket import Pocket
from lib.urlopener import UrlOpener
from config import POCKET_CONSUMER_KEY

bpShare = Blueprint('bpShare', __name__)

SHARE_INFO_TPL = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        <title>{title}</title></head><body><p style="text-align:center;font-size:1.5em;">{info}</p></body></html>"""

@bpShare.route("/share")
def Share():
    args = request.args
    action = args.get('act')
    userName = args.get('u')
    url = args.get('url')
    title = args.get('t')
    key = args.get('k')
    if not all((action, userName, url, key)):
        return "Some parameter is missing or wrong."
    
    user = KeUser.get_one(KeUser.name == userName)
    if not user or not user.kindle_email or not user.share_key != key:
        return "The user does not exist."
    
    url = unquote_plus(url)
    
    #from lib.debug_utils import debug_mail
    #debug_mail(content)
    
    if action in ('evernote', 'wiz'): #保存至evernote/wiz
        return SaveToEvernoteWiz(user, action, url, title)
    elif action == 'pocket': #保存到pocket
        return SaveToPocket(user, action, url, title)
    elif action == 'instapaper':
        return SaveToInstapaper(user, action, url, title)
    else:
        return "Unknown action type : {}".format(action)
    
def SaveToEvernoteWiz(user, action, orgUrl):
    global default_log
    evernote = user.share_links.get('evernote', {})
    wiz = user.share_links.get('wiz', {})
    evernoteMail = evernote.get('email')
    wizMail = wiz.get('email')
    if action == 'evernote' and not evernoteMail:
        default_log.warning('There is no evernote mail yet.')
        return "There is no evernote mail yet."
    elif action == 'wiz' and wizMail:
        default_log.warning('There is no wiz mail yet.')
        return "There is no wiz mail yet."
        
    book = BaseUrlBook(user=user)
    rssBook = user.my_rss_book
    book.title = book.description = action
    book.language = rssBook.language
    book.feeds = [(action, orgUrl)]
    
    attachments = [] #(filename, attachment),]
    html = ''
    title = action
    
    #每次返回一个命名元组，可能为 ItemHtmlTuple, ItemImageTuple, ItemCssTuple(在这里忽略)
    for item in book.Items():
        if isinstance(item, ItemImageTuple):
            attachments.append((item.fileName, item.content))
        elif isinstance(item, ItemHtmlTuple):
            soup = item.soup
            
            #插入源链接
            p = soup.new_tag('p', style='font-size:80%;color:grey;')
            a = soup.new_tag('a', href=item.url)
            a.string = url
            p.string = 'origin : '
            p.append(a)
            soup.html.body.insert(0, p)
            
            #标注图片位置
            for img in soup.find_all('img', attrs={'src': True}):
                p = soup.new_tag('p')
                p.string = 'Image : ' + img['src']
                img.insert_after(p)
                
            try:
                title = soup.html.head.title.string
            except:
                title = item.title
            
            html = str(soup)
            
    to = wizMail if action == 'wiz' else evernoteMail
    if (';' in to) or (',' in to):
        to = to.replace(',', ';').replace(' ', '').split(';')
    
    if html:
        send_html_mail(user.name, to, title, html, attachments, user.timezone)
        info = _("'{title}'<br/><br/>Saved to {act} [{email}] success.").format(title=title, act=action, email=hide_email(to))
        info += '<br/><p style="text-align:right;color:silver;">by KindleEar </p>'
        default_log.info(info)
        info = SHARE_INFO_TPL.format(title=title, info=info)
        return info
    else:
        save_delivery_log(user.name, to, title, 0, status='fetch failed', tz=user.timezone)
        default_log.info("[Share] Fetch url failed.")
        return "[Share] Fetch url failed."

def SaveToPocket(user, action, orgUrl, title):
    pocket = user.share_links.get('pocket' , {})
    accessToken = pocket.get('access_token')
    if not accessToken:
        info = SHARE_INFO_TPL.format(title='Pocket unauthorized', info='Unauthorized Pocket!<br/>Please authorize your KindleEar application firstly.')
        return info
        
    pocket = Pocket(POCKET_CONSUMER_KEY)
    pocket.set_access_token(accessToken)
    try:
        item = pocket.add(url=orgUrl, title=title, tags='KindleEar')
    except Exception as e:
        info = SHARE_INFO_TPL.format(title='Failed to save', info=_('Failed save to Pocket.<br/>') + str(e))
    else:
        info = _("'{}'<br/><br/>Saved to your Pocket account.").format(title)
        info += '''<br/><p style="text-align:right;color:red;">by KindleEar &nbsp;</p>
            <br/><hr/><p style="color:silver;">'''
        info += _('See details below:<br/><br/>{}').format(repr(item))
        info = SHARE_INFO_TPL.format(title='Saved to pocket', info=info)
    
    return info
    
def SaveToInstapaper(user, action, orgUrl, title):
    INSTAPAPER_API_ADD_URL = 'https://www.instapaper.com/api/add'
    
    instapaper = user.share_links.get('instapaper', {})
    userName = instapaper.get('username')
    password = instapaper.get('password')
    if not userName or not password:
        return SHARE_INFO_TPL.format(title='No authorize info', info='Instapaper username and password have to provided fistly!<br/>Please fill them in your KindleEar application.')
    
    opener = UrlOpener()
    password = ke_decrypt(password, user.secret_key or '')
    apiParameters = {'username': userName, 'password':password, 'title':title.encode('utf-8'), 
                    'selection':'KindleEar', 'url':orgUrl}
    ret = opener.open(INSTAPAPER_API_ADD_URL, data=apiParameters)
    if ret.status_code in (200, 201):
        info = _("'{}'<br/><br/>Saved to your Instapaper account.").format(title)
        info += '<br/><p style="text-align:right;color:red;">by KindleEar &nbsp;</p>'
        info = SHARE_INFO_TPL.format(title='Saved to Instapaper', info=info)
    elif ret.status_code == 403:
        info = _("Failed save to Instapaper<br/>'{}'<br/><br/>Reason : Invalid username or password.").format(title)
        info += '<br/><p style="text-align:right;color:red;">by KindleEar &nbsp;</p>'
        info = T_INFO % ('Failed to save', info)
    else:
        info = _("Failed save to Instapaper<br/>'{}'<br/><br/>Reason : Unknown({}).").format(title, ret.status_code)
        info += '<br/><p style="text-align:right;color:red;">by KindleEar &nbsp;</p>'
        info = SHARE_INFO_TPL.format(title='Failed to save', info=info)
    
    return info
    