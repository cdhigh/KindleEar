#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#保存到evernote或分享到社交媒体功能

from urllib.parse import unquote_plus
import hashlib
from bs4 import BeautifulSoup
from google.appengine.api import mail
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import hide_email, etagged, ke_encrypt, ke_decrypt
from bottle import route, request
from books.base_url_book import BaseUrlBook
from lib.pocket import Pocket
from lib.urlopener import URLOpener
from config import SHARE_FUCK_GFW_SRV, POCKET_CONSUMER_KEY

#控制分享到EverNote时图像文件是直接显示(False)还是做为附件(True)
EMBEDDED_SHARE_IMAGE = True

SHARE_INFO_TPL = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        <title>{title}</title></head><body><p style="text-align:center;font-size:1.5em;">{info}</p></body></html>"""

@route("/share")
def Share(self):
    forms = request.query
    action = forms.act
    userName = forms.u
    url = forms.url
    if not all((userName, url, action)):
        return "Some parameter is missing or wrong!<br />"
    
    user = KeUser.all().filter("name = ", userName).get()
    if not user or not user.kindle_email:
        return "User not exist!<br />"
    
    url = unquote_plus(url)
    
    #from lib.debug_utils import debug_mail
    #debug_mail(content)
    
    if action in ('evernote', 'wiz'): #保存至evernote/wiz
        return SaveToEvernoteWiz(user, action, url)    
    elif action == 'pocket': #保存到pocket
        return SaveToPocket(user, action, url)
    elif action == 'instapaper':
        return SaveToInstapaper(user, action, url)
    else:
        return "Unknown action type : {}".format(action)
    
def SaveToEvernoteWiz(user, action, orgUrl):
    global default_log
    if action == 'evernote' and (not user.evernote or not user.evernote_mail):
        default_log.warn('No have evernote mail yet.')
        return "No have evernote mail yet."
    elif action == 'wiz' and (not user.wiz or not user.wiz_mail):
        default_log.warn('No have wiz mail yet.')
        return "No have wiz mail yet."
        
    book = BaseUrlBook(user=user)
    book.title = book.description = action
    book.language = user.own_feeds.language
    book.keep_image = user.own_feeds.keep_image
    book.feeds = [(action, orgUrl)]
    book.url_filters = [flt.url for flt in user.url_filter]
    
    attachments = [] #(filename, attachment),]
    html = ''
    title = action
    
    # 对于html文件，变量名字自文档
    # 对于图片文件，section为图片mime,url为原始链接,title为文件名,content为二进制内容
    #每次返回一个命名元组，可能为 ItemHtmlTuple, ItemImageTuple, ItemCssTuple(在这里忽略)
    #sec_or_media, url, title, content, brief, thumbnail
    for item in book.Items():
        if isinstance(item, ItemImageTuple):
            if EMBEDDED_SHARE_IMAGE:
                attachments.append(mail.Attachment(item.fileName, item.content, content_id='<{}>'.format(item.fileName)))
            else:
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
            
            if EMBEDDED_SHARE_IMAGE: #内嵌图片标识
                for img in soup.find_all('img', attrs={'src': True}):
                    img['src'] = 'cid:' + img['src']
            else: #标注图片位置
                for img in soup.find_all('img', attrs={'src': True}):
                    p = soup.new_tag('p')
                    p.string = 'Image : ' + img['src']
                    img.insert_after(p)
                
            try:
                title = soup.html.head.title.string
            except:
                title = item.title
            
            html = str(soup)
            
    to = user.wiz_mail if action == 'wiz' else user.evernote_mail
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
        deliver_log(user.name, str(to), title, 0, status='fetch failed', tz=user.timezone)
        default_log.info("[Share] Fetch url failed.")
        return "[Share] Fetch url failed."

def SaveToPocket(user, action, orgUrl):
    if not user.pocket_access_token:
        info = SHARE_INFO_TPL.format(title='Pocket unauthorized', info='Unauthorized Pocket!<br/>Please authorize your KindleEar application firstly.')
        return info
        
    title = request.query.t
    tkHash = request.query.h
    if hashlib.md5(user.pocket_acc_token_hash.encode()).hexdigest() != tkHash:
        info = SHARE_INFO_TPL.format(title='Action rejected', info='Hash not match!<br/>KindleEar refuse to execute your command.')
        return info
        
    pocket = Pocket(POCKET_CONSUMER_KEY)
    pocket.set_access_token(user.pocket_access_token)
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
    
def SaveToInstapaper(user, action, orgUrl):
    INSTAPAPER_API_ADD_URL = 'https://www.instapaper.com/api/add'
    
    if not user.instapaper_username or not user.instapaper_password:
        return SHARE_INFO_TPL.format(title='No authorize info', info='Instapaper username and password have to provided fistly!<br/>Please fill them in your KindleEar application.')
    
    title = request.query.t
    name = request.query.n
    if user.instapaper_username != name:
        return SHARE_INFO_TPL.format(title='Action rejected', info='Username not match!<br/>KindleEar refuse to execute your command.')
        
    opener = UrlOpener()
    password = ke_decrypt(user.instapaper_password, user.secret_key or '')
    apiParameters = {'username': user.instapaper_username, 'password':password, 'title':title.encode('utf-8'), 
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
    