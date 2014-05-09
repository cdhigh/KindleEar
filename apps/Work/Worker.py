#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#中文讨论贴：http://www.hi-pda.com/forum/viewthread.php?tid=1213082
#Contributors:
# rexdf <https://github.com/rexdf>

import datetime,time
import web

from collections import OrderedDict
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import InsertToc, local_time
from lib.makeoeb import *
from books import BookClasses, BookClass
from books.base import BaseFeedBook

#import main

class Worker(BaseHandler):
    """ 实际下载文章和生成电子书并且发送邮件 """
    __url__ = "/worker"
    def GET(self):
        username = web.input().get("u")
        bookid = web.input().get("id")
        
        user = KeUser.all().filter("name = ", username).get()
        if not user:
            return "User not exist!<br />"
        
        to = user.kindle_email
        booktype = user.book_type
        titlefmt = user.titlefmt
        tz = user.timezone
        
        bookid = bookid.split(',') if ',' in bookid else [bookid]
        bks = []
        for id in bookid:
            try:
                bks.append(Book.get_by_id(int(id)))
            except:
                continue
                #return "id of book is invalid or book not exist!<br />"
        
        if len(bks) == 0:
            return "No have book to push!"
        elif len(bks) == 1:
            book4meta = BookClass(bks[0].title) if bks[0].builtin else bks[0]
        else: #多本书合并推送时使用“自定义RSS”的元属性
            book4meta = user.ownfeeds
        
        if not book4meta:
            return "No have book to push.<br />"
            
        opts = oeb = None
        
        # 创建 OEB
        #global log
        opts = getOpts(user.device)
        oeb = CreateOeb(main.log, None, opts)
        title = "%s %s" % (book4meta.title, local_time(titlefmt, tz)) if titlefmt else book4meta.title
        
        setMetaData(oeb, title, book4meta.language, local_time("%Y-%m-%d",tz), 'KindleEar')
        oeb.container = ServerContainer(main.log)
        
        #guide
        if len(bks)==1 and bks[0].builtin:
            mhfile = book4meta.mastheadfile
            coverfile = book4meta.coverfile
        else:
            mhfile = DEFAULT_MASTHEAD
            coverfile = DEFAULT_COVER_BV if user.merge_books else DEFAULT_COVER
        
        if mhfile:
            id_, href = oeb.manifest.generate('masthead', mhfile) # size:600*60
            oeb.manifest.add(id_, href, MimeFromFilename(mhfile))
            oeb.guide.add('masthead', 'Masthead Image', href)
        
        if coverfile:
            id_, href = oeb.manifest.generate('cover', coverfile)
            item = oeb.manifest.add(id_, href, MimeFromFilename(coverfile))
            oeb.guide.add('cover', 'Cover', href)
            oeb.metadata.add('cover', id_)
        
        itemcnt,imgindex = 0,0
        sections = OrderedDict()
        toc_thumbnails = {} #map img-url -> manifest-href
        for bk in bks:
            if bk.builtin:
                book = BookClass(bk.title)
                if not book:
                    main.log.warn('not exist book <%s>' % bk.title)
                    continue
                book = book(imgindex=imgindex)
                book.url_filters = [flt.url for flt in user.urlfilter]
                if bk.needs_subscription: #需要登录
                    subs_info = user.subscription_info(bk.title)
                    if subs_info:
                        book.account = subs_info.account
                        book.password = subs_info.password
            else: # 自定义RSS
                if bk.feedscount == 0:
                    continue  #return "the book has no feed!<br />"
                book = BaseFeedBook(imgindex=imgindex)
                book.title = bk.title
                book.description = bk.description
                book.language = bk.language
                book.keep_image = bk.keep_image
                book.oldest_article = bk.oldest_article
                book.fulltext_by_readability = True
                feeds = bk.feeds
                book.feeds = [(feed.title, feed.url, feed.isfulltext) for feed in feeds]
                book.url_filters = [flt.url for flt in user.urlfilter]            
            
            # 对于html文件，变量名字自文档,thumbnail为文章第一个img的url
            # 对于图片文件，section为图片mime,url为原始链接,title为文件名,content为二进制内容,
            #    img的thumbail仅当其为article的第一个img为True
            for sec_or_media, url, title, content, brief, thumbnail in book.Items(opts,user):
                if not sec_or_media or not title or not content:
                    continue
                
                if sec_or_media.startswith(r'image/'):
                    id_, href = oeb.manifest.generate(id='img', href=title)
                    item = oeb.manifest.add(id_, href, sec_or_media, data=content)
                    if thumbnail:
                        toc_thumbnails[url] = href
                    imgindex += 1
                else:
                    #id, href = oeb.manifest.generate(id='feed', href='feed%d.html'%itemcnt)
                    #item = oeb.manifest.add(id, href, 'application/xhtml+xml', data=content)
                    #oeb.spine.add(item, True)
                    sections.setdefault(sec_or_media, [])
                    sections[sec_or_media].append((title, brief, thumbnail, content))
                    itemcnt += 1
                    
        if itemcnt > 0:
            InsertToc(oeb, sections, toc_thumbnails)
            oIO = byteStringIO()
            o = EPUBOutput() if booktype == "epub" else MOBIOutput()
            o.convert(oeb, oIO, opts, main.log)
            ultima_log = DeliverLog.all().order('-time').get()
            if ultima_log:
                diff = datetime.datetime.utcnow() - ultima_log.datetime
                if diff.days * 86400 + diff.seconds < 5:
                    time.sleep(8)
            self.SendToKindle(username, to, book4meta.title, booktype, str(oIO.getvalue()), tz)
            rs = "%s(%s).%s Sent!"%(book4meta.title, local_time(tz=tz), booktype)
            main.log.info(rs)
            return rs
        else:
            self.deliverlog(username, to, book4meta.title, 0, status='nonews',tz=tz)
            rs = "No new feeds."
            main.log.info(rs)
            return rs