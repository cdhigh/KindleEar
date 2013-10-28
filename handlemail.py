#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
将发到xxx@appid.appspotmail.com的邮件正文转成附件发往管理员的kindle邮箱。
"""
import re
from email.Header import decode_header
from email.utils import parseaddr, collapse_rfc2231_value
from bs4 import BeautifulSoup
import webapp2
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.api import taskqueue

from main import KeUser, WhiteList, BaseHandler
from config import DELETE_CSS_FOR_APPSPOTMAIL

def decode_subject(subject):
    if subject[0:2] == '=?' and subject[-2:] == '?=':
        subject = u''.join(unicode(s, c or 'us-ascii') for s, c in decode_header(subject))
    else:
        subject = unicode(collapse_rfc2231_value(subject))
    return subject

class HandleMail(InboundMailHandler):
    def receive(self, message):
        sender = parseaddr(message.sender)[1]
        mailhost = sender.split('@')[1] if sender and '@' in sender else None
        if (not sender or not mailhost) or \
            (not WhiteList.all().filter('mail = ', '*').get()
            and not WhiteList.all().filter('mail = ', sender.lower()).get()
            and not WhiteList.all().filter('mail = ', '@' + mailhost.lower()).get()):
            self.response.out.write("Spam mail!")
            default_log.warn('Spam mail from : %s' % sender)
            return
        
        if hasattr(message, 'subject'):
            subject = decode_subject(message.subject)
        else:
            subject = u"NoSubject"
            
        admin = KeUser.all().filter('name = ', 'admin').get()
        if not admin or not admin.kindle_email:
            self.response.out.write('No admin account or no email configured!')
            return
        
        txt_bodies = message.bodies('text/plain')
        html_bodies = message.bodies('text/html')
        try:
            allBodies = [body.decode() for ctype, body in html_bodies]
        except:
            default_log.warn('Decode html bodies of mail failed.')
            allBodies = []
        if len(allBodies) == 0: #此邮件为纯文本邮件
            try:
                allBodies = [body.decode() for ctype, body in txt_bodies]
            except:
                default_log.warn('Decode text bodies of mail failed.')
                allBodies = []
            bodies = u''.join(allBodies)
            if not bodies:
                return
            if len(bodies) < 100: #可能是链接
                R = r"""^(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>???“”‘’]))"""
                M = re.match(R, bodies)
                if M:
                    bodies = '<a href="%s">%s</a>' % (M.group(),M.group())
            bodies = u"""<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
                    <title>%s</title></head><body>%s</body></html>""" %(subject,bodies)
            allBodies = [bodies.encode('utf-8')]
        
        soup = BeautifulSoup(allBodies[0], 'lxml')
        h = soup.find('head')
        if not h:
            h = soup.new_tag('head')
            soup.html.insert(0, h)
        t = soup.find('title')
        if not t:
            t = soup.new_tag('title')
            t.string = subject
            soup.html.head.insert(0, t)
        
        if len(allBodies) > 1:
            for o in allBodies[1:]:
                so = BeautifulSoup(o, 'lxml')
                b = so.find('body')
                if not b:
                    continue
                for c in b.contents:
                    soup.body.append(c)
        
        #只有一个链接并且邮件字数很少则认为需要抓取网页，否则直接转发邮件正文
        links = list(soup.body.find_all('a',attrs={'href':True}))
        link = links[0]['href'] if links else ''
        if len(links) == 1 and \
            len(''.join([s for s in soup.body.stripped_strings if not s.endswith(link)])) < 100:
                param = {'u':'admin',
                         'url':link, 
                         'type':admin.book_type,
                         'to':admin.kindle_email,
                         'tz':admin.timezone,
                         'subject':subject[:15],
                         'lng':admin.ownfeeds.language,
                         'keepimage':'1' if admin.ownfeeds.keep_image else '0'
                        }
                taskqueue.add(url='/url2book',queue_name="deliverqueue1",method='GET',
                    params=param)
        else: #直接转发邮件正文
            #先判断是否有图片
            from lib.makeoeb import MimeFromFilename
            if hasattr(message, 'attachments'):
                for f,c in message.attachments:
                    if MimeFromFilename(f):
                        hasimage = True
                        break
            else:
                hasimage = False
                
            if hasimage: #有图片的话，要生成MOBI或EPUB才行
                from main import local_time
                from lib.makeoeb import (getOpts, CreateOeb, setMetaData,
                                    ServerContainer, byteStringIO, 
                                    EPUBOutput, MOBIOutput)
                
                #仿照Amazon的转换服务器的处理，去掉CSS
                if DELETE_CSS_FOR_APPSPOTMAIL:
                    tag = soup.find('style', attrs={'type':'text/css'})
                    if tag:
                        tag.extract()
                    for tag in soup.find_all(attrs={'style':True}):
                        del tag['style']
                
                #将图片的src的文件名调整好
                for img in soup.find_all('img',attrs={'src':True}):
                    if img['src'].lower().startswith('cid:'):
                        img['src'] = img['src'][4:]
                
                opts = getOpts()
                oeb = CreateOeb(default_log, None, opts)
                
                setMetaData(oeb, subject[:15], admin.ownfeeds.language, 
                    local_time(tz=admin.timezone), pubtype='book:book:KindleEar')
                oeb.container = ServerContainer(default_log)
                id, href = oeb.manifest.generate(id='page', href='page.html')
                item = oeb.manifest.add(id, href, 'application/xhtml+xml', data=unicode(soup))
                oeb.spine.add(item, False)
                oeb.toc.add(subject, href)
                
                for filename,content in message.attachments:
                    mimetype = MimeFromFilename(filename)
                    if mimetype:
                        try:
                            content = content.decode()
                        except:
                            pass
                        else:
                            id, href = oeb.manifest.generate(id='img', href=filename)
                            item = oeb.manifest.add(id, href, mimetype, data=content)
                
                oIO = byteStringIO()
                o = EPUBOutput() if admin.book_type == "epub" else MOBIOutput()
                o.convert(oeb, oIO, opts, default_log)
                BaseHandler.SendToKindle('admin', admin.kindle_email, subject[:15], 
                    admin.book_type, str(oIO.getvalue()), admin.timezone)
            else: #没有图片则直接推送HTML文件，阅读体验更佳
                m = soup.find('meta', attrs={"http-equiv":"Content-Type"})
                if not m:
                    m = soup.new_tag('meta', content="text/html; charset=utf-8")
                    m["http-equiv"] = "Content-Type"
                    soup.html.head.insert(0,m)
                else:
                    m['content'] = "text/html; charset=utf-8"
                
                html = unicode(soup).encode('utf-8')
                BaseHandler.SendToKindle('admin', admin.kindle_email, subject[:15], 'html',
                    html, admin.timezone, False)
        self.response.out.write('Done')

appmail = webapp2.WSGIApplication([HandleMail.mapping()], debug=True)
