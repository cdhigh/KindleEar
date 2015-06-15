#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#中文讨论贴：http://www.hi-pda.com/forum/viewthread.php?tid=1213082
#Author:
# cdhigh <https://github.com/cdhigh>
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
        elif len(bks)>1 and DEFAULT_COVER:
            #将所有书籍的封面拼贴成一个
            #如果DEFAULT_COVER=None说明用户不需要封面
            id_, href = oeb.manifest.generate('cover', 'cover.jpg')
            item = oeb.manifest.add(id_, href, 'image/jpeg', data=self.MergeCovers(bks,opts))
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
            try: #书的质量可能不一，一本书的异常不能影响推送
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
            except Exception as e:
                main.log.warn("Failure in pushing book '%s' : %s" % (book.title, str(e)))
                continue
                
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
            
    def MergeCovers(self, bks, opts):
        "将所有书籍的封面拼起来，为了更好的效果，请保证图片的大小统一。"
        from StringIO import StringIO
        from PIL import Image
        import random
        
        coverfiles = []
        for bk in bks:
            if bk.builtin:
                book = BookClass(bk.title)
                if book and book.coverfile:
                    coverfiles.append(book.coverfile)
                    
        num_imgs = len(coverfiles)
        if num_imgs > 9:#大于9个则随机选择9个
            coverfiles = random.sample(coverfiles, 9)
            num_imgs = 9
        
        imgs_orig = []
        srvcontainer = ServerContainer()
        for cv in coverfiles:
            try:
                img = Image.open(StringIO(srvcontainer.read(cv)))
            except Exception as e:
                continue
            else:
                imgs_orig.append(img)
        num_imgs = len(imgs_orig)
        if num_imgs == 0:
            return srvcontainer.read(DEFAULT_COVER)
        
        #所有图像的宽高最大值，保证粘贴过程不丢失任何像素
        w = max([im.size[0] for im in imgs_orig])
        h = max([im.size[1] for im in imgs_orig])
        
        if num_imgs == 1:
            pos_info = [(0,0)]
            new_size = (w,h)
        elif num_imgs <=4:
            pos_info = [(0,0),(w,0),(0,h),(w,h)]
            new_size = (w*2,h*2)
        elif num_imgs in (5,6): #1个大的，4个或5个小的
            pos_info = [[(0,0,w*2,h*2),(w*2,0),(w*2,h),(0,h*2),(w,h*2),(w*2,h*2)],
            [(w,0,w*2,h*2),(0,0),(0,h),(0,h*2),(w,h*2),(w*2,h*2)],
            [(0,h,w*2,h*2),(0,0),(w,0),(w*2,0),(w*2,h),(w*2,h*2)],
            [(0,0),(w,0),(w*2,0),(0,h),(w,h,w*2,h*2),(0,h*2)]]
            pos_info = random.choice(pos_info)
            if num_imgs == 5:
                pos_info = [pos_info[0]] + random.sample(pos_info[1:],4)
            new_size = (w*3,h*3)
        else:
            pos_info = [(0,0),(w,0),(w*2,0),(0,h),(w,h),(w*2,h),(0,h*2),(w,h*2),(w*2,h*2)]
            new_size = (w*3,h*3)
            
        #随机安排每个图片的位置
        random.shuffle(pos_info)
        
        imgnew = Image.new('L' if opts.graying_image else 'RGB', new_size, 'white')
        for idx,img in enumerate(imgs_orig):
            pos = pos_info[idx]
            if len(pos) > 2:
                img = img.resize(pos[2:])
                pos = pos[:2]
            imgnew.paste(img, pos)
        
        rw,rh = opts.reduce_image_to
        ratio = min(float(rw)/float(new_size[0]), float(rh)/float(new_size[0]))
        imgnew = imgnew.resize((int(new_size[0]*ratio), int(new_size[1]*ratio)))
        data = StringIO()
        imgnew.save(data, 'JPEG')
        return data.getvalue()
        