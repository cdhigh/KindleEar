#!/usr/bin/env python
# -*- coding:utf-8 -*-
#Author:
# cdhigh <https://github.com/cdhigh>
"""
将发到string@appid.appspotmail.com的邮件正文转成附件发往kindle邮箱。
"""
import re, logging, zlib, base64, urllib
from email.Header import decode_header
from email.utils import parseaddr, collapse_rfc2231_value
from bs4 import BeautifulSoup
import webapp2
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.api import taskqueue

from apps.dbModels import KeUser, Book, WhiteList
from apps.BaseHandler import BaseHandler
from apps.utils import local_time
from config import *

log = logging.getLogger()

def decode_subject(subject):
    if subject[0:2] == '=?' and subject[-2:] == '?=':
        subject = u''.join(unicode(s, c or 'us-ascii') for s, c in decode_header(subject))
    else:
        subject = unicode(collapse_rfc2231_value(subject))
    return subject

def IsHyperLink(txt):
    #判断一个字符串是否是超链接，返回链接本身，否则空串
    R = r"""^(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>???“”‘’]))"""
    M = re.match(R, txt)
    if M is not None:
        return M.group()
    else:
        return ''

class HandleMail(InboundMailHandler):
    def receive(self, message):
        #如果有多个收件人的话，只解释第一个收件人
        to = parseaddr(message.to)[1]
        to = to.split('@')[0] if to and '@' in to else 'xxx'
        if '__' in to:
            listto = to.split('__')
            username = listto[0] if listto[0] else 'admin'
            to = listto[1]
        else:
            username = 'admin'
            
        user = KeUser.all().filter('name = ', username).get()
        if not user:
            username = 'admin'
            user = KeUser.all().filter('name = ', username).get()
        
        if not user or not user.kindle_email:
            self.response.out.write('No account or no email configured!')
            return
        
        sender = parseaddr(message.sender)[1]
        mailhost = sender.split('@')[1] if sender and '@' in sender else None
        if (not sender or not mailhost) or \
            (not user.whitelist.filter('mail = ', '*').get()
            and not user.whitelist.filter('mail = ', sender.lower()).get()
            and not user.whitelist.filter('mail = ', '@' + mailhost.lower()).get()):
            self.response.out.write("Spam mail!")
            log.warn('Spam mail from : %s' % sender)
            return
        
        if hasattr(message, 'subject'):
            subject = decode_subject(message.subject).strip()
        else:
            subject = u"NoSubject"
        
        #邮件主题中如果在最后添加一个 !links，则强制提取邮件中的链接然后生成电子书
        forceToLinks = False
        forceToArticle = False
        if subject.endswith('!links'):
            subject = subject.replace('!links', '').rstrip()
            forceToLinks = True
        elif subject.find(' !links ') >= 0:
            subject = subject.replace(' !links ', '')
            forceToLinks = True
        
        #如果邮件主题在最后添加一个 !article，则强制转换邮件内容为电子书，忽略其中的链接
        if not forceToLinks:
            if subject.endswith('!article'):
                subject = subject.replace('!article', '').rstrip()
                forceToArticle = True
            elif subject.find(' !article ') >= 0:
                subject = subject.replace(' !article ', '')
                forceToArticle = True
            
        #通过邮件触发一次“现在投递”
        if to.lower() == 'trigger':
            return self.TrigDeliver(subject, username)
        
        #获取和解码邮件内容
        txt_bodies = message.bodies('text/plain')
        html_bodies = message.bodies('text/html')
        try:
            allBodies = [body.decode() for ctype, body in html_bodies]
        except:
            log.warn('Decode html bodies of mail failed.')
            allBodies = []
        
        #此邮件为纯文本邮件
        if len(allBodies) == 0:
            log.info('no html body, use text body.')
            try:
                allBodies = [body.decode() for ctype, body in txt_bodies]
            except:
                log.warn('Decode text bodies of mail failed.')
                allBodies = []
            bodies = u''.join(allBodies)
            if not bodies:
                return
            bodyurls = []
            for l in bodies.split('\n'):
                l = l.strip()
                if not l:
                    continue
                link = IsHyperLink(l)
                if link:
                    bodyurls.append('<a href="%s">%s</a><br />' % (link,link))
                else:
                    break

            bodies = u"""<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
              <title>%s</title></head><body>%s</body></html>""" %(subject,
              ''.join(bodyurls) if bodyurls else bodies)
            allBodies = [bodies.encode('utf-8')]
        
        #开始处理邮件内容
        soup = BeautifulSoup(allBodies[0], 'lxml')
        
        #合并多个邮件文本段
        if len(allBodies) > 1:
            for o in allBodies[1:]:
                so = BeautifulSoup(o, 'lxml')
                b = so.find('body')
                if not b:
                    continue
                for c in b.contents:
                    soup.body.append(c)
        
        #判断邮件内容是文本还是链接（包括多个链接的情况）
        links = []
        body = soup.body if soup.find('body') else soup
        if not forceToArticle: #如果强制转正文就不分析链接了，否则先分析和提取链接
            for s in body.stripped_strings:
                link = IsHyperLink(s)
                if link:
                    if link not in links:
                        links.append(link)
                #如果是多个链接，则必须一行一个，不能留空，除非强制提取链接
                #这个处理是为了去除部分邮件客户端在邮件末尾添加的一个广告链接
                elif not forceToLinks:
                    break
                
        if not links and not forceToArticle: #如果通过正常字符（显示出来的）判断没有链接，则看html的a标签
            links = [link['href'] for link in soup.find_all('a', attrs={'href':True})]
            
            text = ' '.join([s for s in body.stripped_strings])
            
            #如果有相对路径，则在里面找一个绝对路径，然后转换其他
            hasRelativePath = False
            fullPath = ''
            for link in links:
                text = text.replace(link, '')
                if not link.startswith('http'):
                    hasRelativePath = True
                if not fullPath and link.startswith('http'):
                    fullPath = link
            
            if hasRelativePath and fullPath:
                for idx, link in enumerate(links):
                    if not link.startswith('http'):
                        links[idx] = urllib.urljoin(fullPath, link)
            
            #如果字数太多，则认为直接推送正文内容
            if not forceToLinks and (len(links) != 1 or len(text) > WORDCNT_THRESHOLD_FOR_APMAIL):
                links = []
            
        if links:
            #判断是下载文件还是转发内容
            isBook = bool(to.lower() in ('book', 'file', 'download'))
            if not isBook:
                isBook = bool(link[-5:].lower() in ('.mobi','.epub','.docx'))
            if not isBook:
                isBook = bool(link[-4:].lower() in ('.pdf','.txt','.doc','.rtf'))
            isDebug = bool(to.lower() == 'debug')

            if isDebug:
                bookType = 'Debug'
            elif isBook:
                bookType = 'Download'
            else:
                bookType = user.book_type
            
            param = {'u': username,
                     'urls': base64.urlsafe_b64encode(zlib.compress('|'.join(links), 9)),
                     'type': bookType,
                     'to': user.kindle_email,
                     'tz': user.timezone,
                     'subject': subject[:SUBJECT_WORDCNT_FOR_APMAIL],
                     'lng': user.ownfeeds.language,
                     'keepimage': '1' if user.ownfeeds.keep_image else '0'
                    }
            taskqueue.add(url='/url2book', queue_name="deliverqueue1", method='GET',
                params=param, target='worker')
        else: #直接转发邮件正文
            #先判断是否有图片
            from lib.makeoeb import MimeFromFilename
            hasimage = False
            if hasattr(message, 'attachments'):
                for f,c in message.attachments:
                    if MimeFromFilename(f):
                        hasimage = True
                        break
                        
            #先修正不规范的HTML邮件
            h = soup.find('head')
            if not h:
                h = soup.new_tag('head')
                soup.html.insert(0, h)
            t = soup.head.find('title')
            if not t:
                t = soup.new_tag('title')
                t.string = subject
                soup.head.insert(0, t)
            
            #有图片的话，要生成MOBI或EPUB才行
            #而且多看邮箱不支持html推送，也先转换epub再推送
            if hasimage or (user.book_type == "epub"):
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
                oeb = CreateOeb(log, None, opts)
                
                setMetaData(oeb, subject[:SUBJECT_WORDCNT_FOR_APMAIL], 
                    user.ownfeeds.language, local_time(tz=user.timezone), 
                    pubtype='book:book:KindleEar')
                oeb.container = ServerContainer(log)
                id_, href = oeb.manifest.generate(id='page', href='page.html')
                item = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=unicode(soup))
                oeb.spine.add(item, False)
                oeb.toc.add(subject, href)
                
                if hasattr(message, 'attachments'):
                    for filename,content in message.attachments:
                        mimetype = MimeFromFilename(filename)
                        if mimetype:
                            try:
                                content = content.decode()
                            except:
                                pass
                            else:
                                id_, href = oeb.manifest.generate(id='img', href=filename)
                                item = oeb.manifest.add(id_, href, mimetype, data=content)
                
                oIO = byteStringIO()
                o = EPUBOutput() if user.book_type == "epub" else MOBIOutput()
                o.convert(oeb, oIO, opts, log)
                BaseHandler.SendToKindle(username, user.kindle_email, 
                    subject[:SUBJECT_WORDCNT_FOR_APMAIL], 
                    user.book_type, str(oIO.getvalue()), user.timezone)
            else: #没有图片则直接推送HTML文件，阅读体验更佳
                m = soup.find('meta', attrs={"http-equiv":"Content-Type"})
                if not m:
                    m = soup.new_tag('meta', content="text/html; charset=utf-8")
                    m["http-equiv"] = "Content-Type"
                    soup.html.head.insert(0,m)
                else:
                    m['content'] = "text/html; charset=utf-8"
                
                html = unicode(soup).encode('utf-8')
                BaseHandler.SendToKindle(username, user.kindle_email, 
                    subject[:SUBJECT_WORDCNT_FOR_APMAIL], 'html', html, user.timezone, False)
        self.response.out.write('Done')
    
    def TrigDeliver(self, subject, username):
        """ 触发一次推送 
            邮件主题为需要投递的书籍，为空或all则等同于网页的"现在投递"按钮
            如果是书籍名，则单独投递，多个书籍名使用逗号分隔
        """
        if subject.lower() in (u'nosubject', u'all'):
            taskqueue.add(url='/deliver',queue_name="deliverqueue1",method='GET',
                params={'u':username},target='default')
        else:
            bkids = []
            booklist = subject.split(',')
            for b in booklist:
                trigbook = Book.all().filter('title = ', b.strip()).get()
                if trigbook:
                    bkids.append(str(trigbook.key().id()))
                else:
                    log.warn('book not found : %s' % b.strip())
            if bkids:
                taskqueue.add(url='/worker',queue_name="deliverqueue1",method='GET',
                    params={'u':username,'id':','.join(bkids)},target='worker')
                    
        
appmail = webapp2.WSGIApplication([HandleMail.mapping()], debug=False)
