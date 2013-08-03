#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
 将发往xxx@appid.appspotmail.com的邮件正文（不是附件）转换成附件
 发往admin的kindle邮箱。需要在白名单中增加源发件人地址。
"""
from email.Header import decode_header
from email.utils import parseaddr, collapse_rfc2231_value
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
        if hasattr(message, 'subject'):
            subject = decode_subject(message.subject)
        else:
            subject = u"NoSubject"
        sender = parseaddr(message.sender)[1]
        
        #白名单机制
        if not WhiteList.all().filter('mail = ', sender).get():
            self.response.out.write("Spam mail!")
            return
        
        admin = KeUser.all().filter('name = ', 'admin').get()
        if not admin or not admin.kindle_email:
            self.response.out.write('No admin account or no email configured!')
            return
        
        #bodies = message.bodies('text/plain')
        html_bodies = message.bodies('text/html')
        allBodies = [body.decode() for content_type, body in html_bodies]
        allBodies = u'<hr />'.join(allBodies)
        
        html = u"""<html><head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        <title>%s</title></head><body>%s</body></html>"""
        html = html % (subject, allBodies)
        html = html.encode("utf-8")
        BaseHandler.SendToKindle(admin.kindle_email,subject[:15],'html',
            html,filewithtime=False)
        self.response.out.write('Done')

appmail = webapp2.WSGIApplication([HandleMail.mapping()], debug=True)
