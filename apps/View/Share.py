#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>

import web, urllib, urlparse

from google.appengine.api import mail
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import hide_email, etagged

from bs4 import BeautifulSoup
from books.base import BaseUrlBook
from lib.pocket import Pocket

from config import SHARE_FUCK_GFW_SRV, POCKET_CONSUMER_KEY

class Share(BaseHandler):
    """ 保存到evernote或分享到社交媒体 """
    __url__ = "/share"
    SHARE_IMAGE_EMBEDDED = True
    
    @etagged()
    def GET(self):
        import urlparse,urllib
        action = web.input().get('act')
        username = web.input().get("u")
        url = web.input().get("url")
        if not username or not url or not action:
            return "Some parameter is missing or wrong!<br />"
        
        user = KeUser.all().filter("name = ", username).get()
        if not user or not user.kindle_email:
            return "User not exist!<br />"
        
        #global log
        
        url = urllib.unquote(url)
                
        if action in ('evernote', 'wiz'): #保存至evernote/wiz
            if action=='evernote' and (not user.evernote or not user.evernote_mail):
                main.log.warn('No have evernote mail yet.')
                return "No have evernote mail yet."
            elif action=='wiz' and (not user.wiz or not user.wiz_mail):
                main.log.warn('No have wiz mail yet.')
                return "No have wiz mail yet."
                
            book = BaseUrlBook()
            book.title = book.description = action
            book.language = user.ownfeeds.language
            book.keep_image = user.ownfeeds.keep_image
            book.network_timeout = 60
            book.feeds = [(action,url)]
            book.url_filters = [flt.url for flt in user.urlfilter]
            
            attachments = [] #(filename, attachment),]
            html = ''
            title = action
            
            # 对于html文件，变量名字自文档
            # 对于图片文件，section为图片mime,url为原始链接,title为文件名,content为二进制内容
            for sec_or_media, url, title, content, brief, thumbnail in book.Items():
                if sec_or_media.startswith(r'image/'):
                    if self.SHARE_IMAGE_EMBEDDED:
                        attachments.append(mail.Attachment(title,
                            content,content_id='<%s>'%title))
                    else:
                        attachments.append((title,content))
                else:
                    soup = BeautifulSoup(content, 'lxml')
                    
                    #插入源链接
                    p = soup.new_tag('p', style='font-size:80%;color:grey;')
                    a = soup.new_tag('a', href=url)
                    a.string = url
                    p.string = 'origin : '
                    p.append(a)
                    soup.html.body.insert(0,p)
                    
                    if self.SHARE_IMAGE_EMBEDDED:
                        #内嵌图片标识
                        for img in soup.find_all('img', attrs={'src':True}):
                            img['src'] = 'cid:' + img['src']
                    else:
                        #标注图片位置
                        for img in soup.find_all('img', attrs={'src':True}):
                            p = soup.new_tag('p')
                            p.string = 'Image : ' + img['src']
                            img.insert_after(p)
                        
                    try:
                        title = unicode(soup.html.head.title.string)
                    except:
                        pass
                    
                    html = unicode(soup)
                    
            to = user.wiz_mail if action=='wiz' else user.evernote_mail
            if html:
                self.SendHtmlMail(username, to, title, html.encode('utf-8'), attachments, user.timezone)
                info = _("'%(title)s'<br/><br/>Saved to %(act)s [%(email)s] success.") % ({'title':title,'act':action,'email':hide_email(to)})
                info += '<br/><p style="text-align:right;color:silver;">by KindleEar </p>'
                main.log.info(info)
                web.header('Content-type', "text/html; charset=utf-8")
                info = u"""<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
                    <title>%s</title></head><body><p style="text-align:center;font-size:1.5em;">%s</p></body></html>""" % (title, info)
                return info.encode('utf-8')
            else:
                self.deliverlog(username, to, title, 0, status='fetch failed', tz=user.timezone)
                main.log.info("[Share]Fetch url failed.")
                return "[Share]Fetch url failed."
        elif action == 'xpocket': #保存到pocket
            web.header('Content-type', "text/html; charset=utf-8")
            
            T_INFO = u"""<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
                <title>%s</title></head><body><p style="text-align:center;font-size:1.5em;">%s</p></body></html>"""
            if not user.xpocket_access_token:
                info = T_INFO % ('Pocket unauthorized', 'Unauthorized Pocket!<br/>Please authorize your KindleEar application firstly.')
                return info.encode('utf-8')
                
            title = web.input().get('t', '') 
            tkHash = web.input().get("h", '')
            if user.xpocket_acc_token_hash != tkHash:
                info = T_INFO % ('Action rejected', 'Hash not match!<br/>KindleEar refuse to execute your command.')
                return info.encode('utf-8')
                
            pocket = Pocket(POCKET_CONSUMER_KEY)
            pocket.set_access_token(user.xpocket_access_token)
            try:
                item = pocket.add(url=url, title=title, tags='KindleEar')
            except Exception as e:
                info = T_INFO % ('Failed to save', _('Failed save to Pocket.<br/>') + str(e))
            else:
                info = _("'%s'<br/><br/>Saved to your Pocket account.") % title
                info += u'''<br/><p style="text-align:right;color:red;">by KindleEar &nbsp;</p>
                    <br/><hr/><p style="color:silver;">'''
                info += _('See details below:<br/><br/>%s') % repr(item)
                info = T_INFO % ('Saved to pocket', info)
            
            return info.encode('utf-8')
        else:
            return "Unknown action type : %s !" % action
        