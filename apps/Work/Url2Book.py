#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#中文讨论贴：http://www.hi-pda.com/forum/viewthread.php?tid=1213082
#Author:
# cdhigh <https://github.com/cdhigh>
#Contributors:
# rexdf <https://github.com/rexdf>

import web
import jinja2
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import InsertToc, local_time
from lib.makeoeb import *

from books.base import BaseUrlBook

#import main

class Url2Book(BaseHandler):
    """ 抓取指定链接，转换成附件推送 """
    __url__ = "/url2book"
    def GET(self):
        username = web.input().get("u")
        urls = web.input().get("urls")
        subject = web.input().get("subject")
        to = web.input().get("to")
        language = web.input().get("lng")
        keepimage = bool(web.input().get("keepimage") == '1')
        booktype = web.input().get("type", "mobi")
        tz = int(web.input().get("tz", TIMEZONE))
        if not all((username,urls,subject,to,language,booktype,tz)):
            return "Some parameter missing!<br />"
        
        #global log
        
        if booktype == 'Download': #直接下载电子书并推送
            from lib.filedownload import Download
            for url in urls.split('|'):
                dlinfo, filename, content = Download(url)
                #如果标题已经给定了文件名，则使用标题文件名
                if '.' in subject and (1 < len(subject.split('.')[-1]) < 5):
                    filename = subject
                    
                if content:
                    self.SendToKindle(username, to, filename, '', content, tz)
                else:
                    if not dlinfo:
                        dlinfo = 'download failed'
                    self.deliverlog(username, to, filename, 0, status=dlinfo,tz=tz)
                main.log.info("%s Sent!" % filename)
            return "%s Sent!" % filename
            
        user = KeUser.all().filter("name = ", username).get()
        if not user or not user.kindle_email:
            return "User not exist!<br />"
            
        book = BaseUrlBook()
        book.title = book.description = subject
        book.language = language
        book.keep_image = keepimage
        book.network_timeout = 60
        book.feeds = [(subject,url) for url in urls.split('|')]
        book.url_filters = [flt.url for flt in user.urlfilter]
        
        opts = oeb = None
        
        # 创建 OEB
        opts = getOpts(user.device)
        oeb = CreateOeb(main.log, None, opts)
        oeb.container = ServerContainer(main.log)
        
        if len(book.feeds) > 1:
            setMetaData(oeb, subject, language, local_time(tz=tz))
            id, href = oeb.manifest.generate('masthead', DEFAULT_MASTHEAD)
            oeb.manifest.add(id, href, MimeFromFilename(DEFAULT_MASTHEAD))
            oeb.guide.add('masthead', 'Masthead Image', href)
        else:
            setMetaData(oeb, subject, language, local_time(tz=tz), pubtype='book:book:KindleEar')
        
        # id, href = oeb.manifest.generate('cover', DEFAULT_COVER)
        # item = oeb.manifest.add(id, href, MimeFromFilename(DEFAULT_COVER))
        # oeb.guide.add('cover', 'Cover', href)
        # oeb.metadata.add('cover', id)
        
        # 对于html文件，变量名字自文档
        # 对于图片文件，section为图片mime,url为原始链接,title为文件名,content为二进制内容
        itemcnt,hasimage = 0,False
        sections = {subject:[]}
        toc_thumbnails = {} #map img-url -> manifest-href
        for sec_or_media, url, title, content, brief, thumbnail in book.Items(opts,user):
            if sec_or_media.startswith(r'image/'):
                id, href = oeb.manifest.generate(id='img', href=title)
                item = oeb.manifest.add(id, href, sec_or_media, data=content)
                if thumbnail:
                    toc_thumbnails[url] = href
                itemcnt += 1
                hasimage = True
            else:
                if len(book.feeds) > 1:
                    sections[subject].append((title,brief,thumbnail,content))
                else:
                    id, href = oeb.manifest.generate(id='page', href='page.html')
                    item = oeb.manifest.add(id, href, 'application/xhtml+xml', data=content)
                    oeb.spine.add(item, False)
                    oeb.toc.add(title, href)
                itemcnt += 1
            
        if itemcnt > 0:
            if len(book.feeds) > 1:
                InsertToc(oeb, sections, toc_thumbnails)
                # elif not hasimage: #单文章没有图片则去掉封面
                # href = oeb.guide['cover'].href
                # oeb.guide.remove('cover')
                # item = oeb.manifest.hrefs[href]
                # oeb.manifest.remove(item)
                # oeb.metadata.clear('cover')
                
            oIO = byteStringIO()
            o = EPUBOutput() if booktype == "epub" else MOBIOutput()
            o.convert(oeb, oIO, opts, main.log)
            self.SendToKindle(username, to, book.title, booktype, str(oIO.getvalue()), tz)
            rs = "%s(%s).%s Sent!"%(book.title, local_time(tz=tz), booktype)
            main.log.info(rs)
            return rs
        else:
            self.deliverlog(username, to, book.title, 0, status='fetch failed',tz=tz)
            rs = "[Url2Book]Fetch url failed."
            main.log.info(rs)
            return rs


