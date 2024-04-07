#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#保存到evernote或分享到社交媒体功能

from urllib.parse import unquote
from bs4 import BeautifulSoup
from flask import Blueprint, render_template, request, current_app as app
from flask_babel import gettext as _
from calibre.web.feeds.news import recursive_fetch_url
import readability
from ..base_handler import *
from ..back_end.db_models import *
from ..back_end.send_mail_adpt import send_html_mail
from ..utils import hide_email, ke_decrypt
from ..lib.pocket import Pocket
from ..lib.wallabag import WallaBag
from ..lib.urlopener import UrlOpener
from filesystem_dict import FsDictStub

bpShare = Blueprint('bpShare', __name__)

SHARE_INFO_TPL = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        <title>{title}</title></head><body><p style="text-align:center;font-size:1.5em;">
        {info}</p><br/><p style="text-align:right;color:silver;">by KindleEar &nbsp;</p></body></html>"""

SHARE_IMAGE_EMBEDDED = True

@bpShare.route("/share")
def Share():
    get_args = request.args.get
    action = get_args('act')
    userName = get_args('u')
    url = get_args('url')
    title = get_args('t')
    key = get_args('k')
    if not all((action, userName, url, key)):
        return _("Some parameters are missing or wrong.")
    
    user = KeUser.get_or_none(KeUser.name == userName)
    if not user or not user.kindle_email or user.share_links.get('key') != key:
        return _('The username does not exist or the email is empty.')
        
    url = unquote(url)
    
    if action in ('Evernote', 'Wiz'):
        return SaveToEvernoteWiz(user, action, url, title)
    elif action == 'Pocket':
        return SaveToPocket(user, action, url, title)
    elif action == 'Instapaper':
        return SaveToInstapaper(user, action, url, title)
    elif action == 'wallabag':
        return SaveToWallabag(user, action, url, title)
    else:
        return _('Unknown command: {}').format(action)
    
def SaveToEvernoteWiz(user, action, url, title):
    to = user.share_links.get(action, {}).get('email', '')
    html_title = f'Share to {action}'
    if not to:
        return SHARE_INFO_TPL.format(title=html_title, info=_("There is no {} email yet.").format(action))
    
    html = b''
    fs = FsDictStub(None)
    res, paths, failures = recursive_fetch_url(url, fs)
    if res:
        raw = fs.read(res)
        positives = ['image-block', 'image-block-caption', 'image-block-ins']
        try:
            doc = readability.Document(raw, positive_keywords=positives, url=url)
            summary = doc.summary(html_partial=False)
        except:
            summary = raw
            
        soup = BeautifulSoup(summary, 'lxml')
        p = soup.new_tag('p', style='font-size:80%;color:grey;') #插入源链接
        a = soup.new_tag('a', href=url)
        a.string = url
        p.string = 'origin : '
        p.append(a)
        soup.html.body.insert(0, p)
        
        #标注图片位置
        attachments = []
        for img in soup.find_all('img', attrs={'src': True}):
            src = img['src']
            data = fs.read(os.path.join(fs.path, src))
            if not data:
                continue

            if src.startswith('images/'):
                src = src[7:]
            img['src'] = src
            attachments.append((src, data))
            p = soup.new_tag('p')
            p.string = 'Image : ' + src
            img.insert_after(p)

        try:
            title = soup.html.head.title.string
        except:
            pass
        html = str(soup)

    info = [title, '<br/>']
    account = f'{action} <{hide_email(to)}>'
    if html:
        send_html_mail(user, to, title, html, attachments)
        info.append(_("Saved to your {} account.").format(account))
    else:
        save_delivery_log(user, title, 0, status='fetch failed', to=to)
        info.append(_("Failed save to {}.").format(account))
        info.append(_('Reason :'))
        info.append('fetch failed')

    return SHARE_INFO_TPL.format(title=html_title, info='<br/>'.join(info))

def SaveToPocket(user, action, url, title):
    accessToken = user.share_links.get('Pocket' , {}).get('access_token', '')
    html_title = 'Share to Pocket'
    if not accessToken:
        return SHARE_INFO_TPL.format(title=html_title, info=_('Unauthorized {} account!').format('Pocket'))
        
    pocket = Pocket(app.config['POCKET_CONSUMER_KEY'])
    pocket.set_access_token(accessToken)
    info = [title, '<br/>']
    try:
        item = pocket.add(url=url, title=title, tags='KindleEar')
    except Exception as e:
        info.append(_("Failed save to {}.").format('Pocket'))
        info.append(_('Reason :'))
        info.append(str(e))
    else:
        info.append(_("Saved to your {} account.").format('Pocket'))
        info.append(_('See details below:'))
        info.append(repr(item))
    
    return SHARE_INFO_TPL.format(title=html_title, info='<br/>'.join(info))
    
def SaveToInstapaper(user, action, url, title):
    INSTAPAPER_API_ADD_URL = 'https://www.instapaper.com/api/add'
    
    instapaper = user.share_links.get('Instapaper', {})
    userName = instapaper.get('username', '')
    password = instapaper.get('password', '')
    html_title = 'Share to Instapaper'
    if not userName or not password:
        return SHARE_INFO_TPL.format(title=html_title, info=_('The username or password is empty.'))
    
    opener = UrlOpener()
    password = ke_decrypt(password, user.secret_key)
    data = {'username': userName, 'password': password, 'title': title.encode('utf-8'), 'selection': 'KindleEar', 'url': url}
    ret = opener.open(INSTAPAPER_API_ADD_URL, data=data)
    info = [title, '<br/>']
    if ret.status_code in (200, 201):
        info.append(_("Saved to your {} account.").format('Instapaper'))
    else:
        reason = _("The username does not exist or password is wrong.") if ret.status_code == 403 else _('Unknown: {}').format(ret.status_code)
        info.append(_("Failed save to {}.").format('Instapaper'))
        info.append(_('Reason :'))
        info.append(reason)
        
    return SHARE_INFO_TPL.format(title=html_title, info='<br/>'.join(info))

def SaveToWallabag(user, action, url, title):
    config = user.share_links.get('wallabag', {})
    config['password'] = ke_decrypt(config.get('password', ''), user.secret_key)
    wallabag = WallaBag(config, default_log)
    ret = wallabag.add(url, title=title)
    if ret['changed']: #保存新的token
        shareLinks = user.share_links
        shareLinks['wallabag'] = wallabag.config
        user.share_links = shareLinks
        user.save()

    info = [title, '<br/>']
    if ret['resp']:
        info.append(_("Saved to your {} account.").format('wallabag'))
    else:
        info.append(_("Failed save to {}.").format('wallabag'))
        info.append(_('Reason :'))
        info.append(ret['msg'])
        
    return SHARE_INFO_TPL.format(title='Share to wallabag', info='<br/>'.join(info))