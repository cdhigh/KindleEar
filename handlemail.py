#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
将发到xxx@appid.appspotmail.com的邮件正文转成附件发往管理员的kindle邮箱。
"""
from email.Header import decode_header
from email.utils import parseaddr, collapse_rfc2231_value
from bs4 import BeautifulSoup
import webapp2
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler

from main import KeUser, WhiteList, BaseHandler

def decode_subject(subject):
    if subject[0:2] == '=?' and subject[-2:] == '?=':
        subject = u''.join(unicode(s, c or 'us-ascii') for s, c in decode_header(subject))
    else:
        subject = unicode(collapse_rfc2231_value(subject))
    return subject

class HandleMail(InboundMailHandler):
    def receive(self, message):
        sender = parseaddr(message.sender)[1]
        if not WhiteList.all().filter('mail = ', sender).get():
            self.response.out.write("Spam mail!")
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
        allBodies = [body.decode() for ctype, body in html_bodies]
        if len(allBodies) == 0:
            allBodies = [body.decode() for ctype, body in txt_bodies]
            bodies = u''.join(allBodies)
            if not bodies:
                return
            allBodies = [u"""<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
              <title>%s</title></head><body>%s</body></html>""" %(subject,bodies)]
        
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
        m = soup.find('meta', attrs={"http-equiv":"Content-Type"})
        if not m:
            m =  soup.new_tag('meta', content="text/html; charset=utf-8")
            m["http-equiv"] = "Content-Type"
        else:
            m['content'] = "text/html; charset=utf-8"
        
        if len(allBodies) > 1:
            for o in allBodies[1:]:
                so = BeautifulSoup(o, 'lxml')
                b = so.find('body')
                if not b:
                    continue
                for c in b.contents:
                    soup.body.append(c)
        
        html = unicode(soup).encode("utf-8")
        BaseHandler.SendToKindle('admin', admin.kindle_email, subject[:15], 'html',
            html, admin.timezone, False)
        self.response.out.write('Done')

appmail = webapp2.WSGIApplication([HandleMail.mapping()], debug=True)
