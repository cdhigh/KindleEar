#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Author:
# cdhigh <https://github.com/cdhigh>
#Contributors:
# rexdf <https://github.com/rexdf>

import datetime, time, imghdr
import web
import StringIO
from PIL import Image
import random

from collections import OrderedDict
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import InsertToc, local_time, get_exc_location
from lib.makeoeb import *
from calibre.ebooks.conversion.mobioutput import MOBIOutput
from calibre.ebooks.conversion.epuboutput import EPUBOutput
from calibre.utils.bytestringio import byteStringIO
from books import BookClasses, BookClass
from books.base import BaseFeedBook, BaseComicBook
from books.comic import ComicBaseClasses, comic_domains

# 实际下载文章和生成电子书并且发送邮件
class Worker(BaseHandler):
    __url__ = "/worker"
    def GET(self):
        username = web.input().get("u")
        bookid = web.input().get("id")
        feedsId = web.input().get("feedsId")
        
        user = KeUser.all().filter("name = ", username).get()
        if not user:
            return "User not exist!<br />"
        
        to = user.kindle_email
        if (';' in to) or (',' in to):
            to = to.replace(',', ';').replace(' ', '').split(';')
        
        booktype = user.book_type #mobi,epub
        bookmode = user.book_mode or 'periodical' #periodical,comic
        titlefmt = user.titlefmt
        tz = user.timezone
        
        bookid = bookid.split(',') if ',' in bookid else [bookid]
        bks = []
        for id_ in bookid:
            try:
                bks.append(Book.get_by_id(int(id_)))
            except:
                main.log.warn("Can't find book {}".format(id_))
                continue
                #return "id of book is invalid or book not exist!<br />"
        
        # Deliver only some feeds in custom rss
        if feedsId:
            feedsId = [int(item) for item in feedsId.split('|') if item.isdigit()]
            feedsId = [Feed.get_by_id(item) for item in feedsId if Feed.get_by_id(item)]

        book4meta = None
        if len(bks) == 0:
            return "No have book to push!"
        elif len(bks) == 1:
            if bks[0].builtin:
                book4meta = BookClass(bks[0].title)
                mhfile = book4meta.mastheadfile
                coverfile = book4meta.coverfile
                if issubclass(book4meta, BaseComicBook): #如果单独推送一个继承自BaseComicBook的书籍，则自动设置为漫画模式
                    bookmode = 'comic'
            else: #单独的推送自定义RSS
                book4meta = bks[0]
                mhfile = DEFAULT_MASTHEAD
                coverfile = DEFAULT_COVER
        else: #多本书合并推送时使用“自定义RSS”的元属性
            book4meta = user.ownfeeds
            mhfile = DEFAULT_MASTHEAD
            coverfile = DEFAULT_COVER_BV if user.merge_books else DEFAULT_COVER
        
        if not book4meta:
            return "No have book to push.<br />"
        # 创建 OEB
        #global log
        opts = getOpts(user.device, bookmode)
        oeb = CreateOeb(main.log, None, opts)
        bookTitle = "%s %s" % (book4meta.title, local_time(titlefmt, tz)) if titlefmt else book4meta.title
        
        if bookmode == 'comic':
            pubtype = 'book:book:KindleEar'
        else:
            pubtype = 'periodical:magazine:KindleEar'
            
        setMetaData(oeb, bookTitle, book4meta.language, local_time("%Y-%m-%d",tz), pubtype=pubtype)
        oeb.container = ServerContainer(main.log)
        
        #guide
        if mhfile:
            id_, href = oeb.manifest.generate('masthead', mhfile) # size:600*60
            oeb.manifest.add(id_, href, MimeFromFilename(mhfile))
            oeb.guide.add('masthead', 'Masthead Image', href)
        
        if coverfile:
            imgData = None
            imgMime = ''
            #使用保存在数据库的用户上传的封面
            if coverfile == DEFAULT_COVER and user.cover:
                imgData = user.cover
                imgMime = 'image/jpeg' #保存在数据库中的只可能是jpeg格式
            elif callable(coverfile): #如果封面需要回调的话
                try:
                    imgData = book4meta().coverfile()
                    if imgData:
                        imgType = imghdr.what(None, imgData)
                        if imgType: #如果是合法图片
                            imgMime = r"image/" + imgType
                        else:
                            main.log.warn(u'content of cover is invalid : [%s].' % bookTitle)
                            imgData = None
                except:
                    main.log.exception(
                        u"Failed to fetch cover for book [%s]" % bookTitle
                    )
                    coverfile = DEFAULT_COVER
                    imgData = None
                    imgMime = ''
            
            if imgData and imgMime:
                id_, href = oeb.manifest.generate('cover', 'cover.jpg')
                item = oeb.manifest.add(id_, href, imgMime, data=imgData)
            else:
                id_, href = oeb.manifest.generate('cover', coverfile)
                item = oeb.manifest.add(id_, href, MimeFromFilename(coverfile))
            oeb.guide.add('cover', 'Cover', href)
            oeb.metadata.add('cover', id_)
        elif len(bks) > 1 and DEFAULT_COVER:
            #将所有书籍的封面拼贴成一个
            #如果DEFAULT_COVER=None说明用户不需要封面
            id_, href = oeb.manifest.generate('cover', 'cover.jpg')
            item = oeb.manifest.add(id_, href, 'image/jpeg', data=self.MergeCovers(bks, opts, user))
            oeb.guide.add('cover', 'Cover', href)
            oeb.metadata.add('cover', id_)
            
        itemcnt, imgindex = 0, 0
        sections = OrderedDict()
        toc_thumbnails = {} #map img-url -> manifest-href
        for bk in bks:
            if bk.builtin:
                cbook = BookClass(bk.title)
                if not cbook:
                    main.log.warn('not exist book <%s>' % bk.title)
                    continue
                book = cbook(imgindex=imgindex, opts=opts, user=user)
                book.url_filters = [flt.url for flt in user.urlfilter]
                if bk.needs_subscription: #需要登录
                    subs_info = user.subscription_info(bk.title)
                    if subs_info:
                        book.account = subs_info.account
                        book.password = subs_info.password
                if issubclass(cbook, BaseComicBook):
                    self.push_comic_book(username, user, book)
                    continue
            else:  # 自定义RSS
                if bk.feedscount == 0:
                    continue  #return "the book has no feed!<br />"
                    
                book = BaseFeedBook(imgindex=imgindex, opts=opts, user=user)
                book.title = bk.title
                book.description = bk.description
                book.language = bk.language
                book.keep_image = bk.keep_image
                book.oldest_article = bk.oldest_article
                book.fulltext_by_readability = True
                feeds = feedsId if feedsId else bk.feeds
                book.feeds = []
                for feed in feeds:
                    if feed.url.startswith(comic_domains):
                        self.ProcessComicRSS(username, user, feed)
                    else:
                        book.feeds.append((feed.title, feed.url, feed.isfulltext))
                book.url_filters = [flt.url for flt in user.urlfilter]
                
            # 对于html文件，变量名字自文档,thumbnail为文章第一个img的url
            # 对于图片文件，section为图片mime,url为原始链接,title为文件名,content为二进制内容,
            #    img的thumbail仅当其为article的第一个img为True
            try: #书的质量可能不一，一本书的异常不能影响其他书籍的推送
                for sec_or_media, url, title, content, brief, thumbnail in book.Items():
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
            except:
                main.log.exception(u"Failed to push <%s>" % book.title)
                continue
        
        volumeTitle = ''
        if itemcnt > 0:
            insertHtmlToc = GENERATE_HTML_TOC
            insertThumbnail = GENERATE_TOC_THUMBNAIL

            InsertToc(oeb, sections, toc_thumbnails, insertHtmlToc, insertThumbnail)
            oIO = byteStringIO()
            o = EPUBOutput() if booktype == "epub" else MOBIOutput()
            o.convert(oeb, oIO, opts, main.log)
            try:
                ultima_log = DeliverLog.all().order('-time').get()
            except:
                ultima_log = sorted(DeliverLog.all(), key=attrgetter('time'), reverse=True)
                ultima_log = ultima_log[0] if ultima_log else None
            if ultima_log:
                diff = datetime.datetime.utcnow() - ultima_log.datetime
                if diff.days * 86400 + diff.seconds < 10:
                    time.sleep(8)
            self.SendToKindle(username, to, book4meta.title + volumeTitle, booktype, str(oIO.getvalue()), tz)
            rs = "%s(%s).%s Sent!"%(book4meta.title, local_time(tz=tz), booktype)
            main.log.info(rs)
            return rs
        else:
            self.deliverlog(username, str(to), book4meta.title + volumeTitle, 0, status='nonews', tz=tz)
            rs = "No new feeds."
            main.log.info(rs)
            return rs
    
    #将所有书籍的封面拼起来，为了更好的效果，请保证图片的大小统一。
    def MergeCovers(self, bks, opts, user):
        coverfiles = []
        callableInstances = []
        for bk in bks:
            if bk.builtin:
                book = BookClass(bk.title)
                if book and book.coverfile:
                    if callable(book.coverfile):
                        instan = book()
                        callableInstances.append(instan)
                        coverfiles.append(instan.coverfile)
                    else:
                        coverfiles.append(book.coverfile)
            elif DEFAULT_COVER:
                coverfiles.append(DEFAULT_COVER)
                
        num_imgs = len(coverfiles)
        if num_imgs > 9:#大于9个则随机选择9个
            coverfiles = random.sample(coverfiles, 9)
            num_imgs = 9
        
        imgs_orig = []
        srvcontainer = ServerContainer()
        for cv in coverfiles:
            img = None
            #使用用户上传的保存在数据库的封面
            if cv == DEFAULT_COVER and user.cover:
                try:
                    img = Image.open(StringIO.StringIO(user.cover))
                except:
                    img = None
            elif callable(cv): #如果封面需要回调的话
                try:
                    data = cv()
                    if data:
                        img = Image.open(StringIO.StringIO(data))
                    else:
                        cv = DEFAULT_COVER
                        img = None
                except Exception as e:
                    main.log.warn('[MergeCovers] Content of cover is invalid : [%s].' % str(e))
                    cv = DEFAULT_COVER
                    img = None
            try:
                if not img:
                    img = Image.open(StringIO.StringIO(srvcontainer.read(cv)))
            except Exception as e:
                main.log.warn('[MergeCovers] Cover file invalid [%s], %s' % (str(cv), str(e)))
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
        elif num_imgs <= 4: #4等分
            pos_info = [(0,0),(w,0),(0,h),(w,h)]
            new_size = (w*2,h*2)
            if num_imgs < 4: #填满4格
                imgs_orig += random.sample(imgs_orig, 4 - num_imgs)
        elif num_imgs in (5,6): #1个大的，5个小的
            pos_info = [[(0,0,w*2,h*2),(w*2,0),(w*2,h),(0,h*2),(w,h*2),(w*2,h*2)],
            [(w,0,w*2,h*2),(0,0),(0,h),(0,h*2),(w,h*2),(w*2,h*2)],
            [(0,h,w*2,h*2),(0,0),(w,0),(w*2,0),(w*2,h),(w*2,h*2)],
            [(0,0),(w,0),(w*2,0),(0,h),(w,h,w*2,h*2),(0,h*2)]]
            pos_info = random.choice(pos_info)
            if num_imgs == 5: #填满6格
                #pos_info = [pos_info[0]] + random.sample(pos_info[1:], 4)
                imgs_orig.append(random.choice(imgs_orig))
            new_size = (w*3,h*3)
        else: #九宫格
            pos_info = [(0,0),(w,0),(w*2,0),(0,h),(w,h),(w*2,h),(0,h*2),(w,h*2),(w*2,h*2)]
            new_size = (w*3,h*3)
            if num_imgs < 9:
                imgs_orig += random.sample(imgs_orig, 9 - num_imgs)
            
        #随机安排每个图片的位置
        random.shuffle(pos_info)
        
        #拼接图片
        imgnew = Image.new('L' if opts.graying_image else 'RGB', new_size, 'white')
        for idx,img in enumerate(imgs_orig):
            pos = pos_info[idx]
            if len(pos) > 2: #如果元素为4个，则前两个是在大图中的位置，后两个是缩小后的图片尺寸
                img = img.resize(pos[2:])
                pos = pos[:2]
            imgnew.paste(img, pos)
        
        #新生成的图片再整体缩小到设定大小
        rw,rh = opts.reduce_image_to
        ratio = min(float(rw) / float(new_size[0]), float(rh) / float(new_size[1]))
        imgnew = imgnew.resize((int(new_size[0] * ratio), int(new_size[1] * ratio)))
        data = StringIO.StringIO()
        imgnew.save(data, 'JPEG')
        return data.getvalue()

    def push_comic_book(self, username, user, book, opts=None):
        if not opts:
            opts = getOpts(user.device, "comic")
        oeb = CreateOeb(main.log, None, opts)
        pubtype = 'book:book:KindleEar'
        language = 'zh-cn'

        setMetaData(
            oeb,
            book.title,
            language,
            local_time("%Y-%m-%d", user.timezone),
            pubtype=pubtype,
        )
        oeb.container = ServerContainer(main.log)

        #guide
        id_, href = oeb.manifest.generate('masthead', DEFAULT_MASTHEAD) # size:600*60
        oeb.manifest.add(id_, href, MimeFromFilename(DEFAULT_MASTHEAD))
        oeb.guide.add('masthead', 'Masthead Image', href)

        id_, href = oeb.manifest.generate('cover', DEFAULT_COVER)
        item = oeb.manifest.add(id_, href, MimeFromFilename(DEFAULT_COVER))

        oeb.guide.add('cover', 'Cover', href)
        oeb.metadata.add('cover', id_)

        itemcnt, imgindex = 0, 0
        sections = OrderedDict()
        toc_thumbnails = {} #map img-url -> manifest-href

        chapters = book.ParseFeedUrls()
        if not chapters:
            self.deliverlog(
                username,
                str(user.kindle_email),
                book.title,
                0,
                status="nonews",
                tz=user.timezone,
            )
            return
        for (
            bookname,
            chapter_title,
            img_list,
            chapter_url,
            next_chapter_index,
        ) in chapters:
            try:
                image_count = 0
                for (
                    mime_or_section,
                    url,
                    filename,
                    content,
                    brief,
                    thumbnail,
                ) in book.gen_image_items(img_list, chapter_url):
                    if not mime_or_section or not filename or not content:
                        continue

                    if mime_or_section.startswith(r"image/"):
                        id_, href = oeb.manifest.generate(id="img", href=filename)
                        item = oeb.manifest.add(
                            id_, href, mime_or_section, data=content
                        )
                        if thumbnail:
                            toc_thumbnails[url] = href
                    else:
                        sections.setdefault(mime_or_section, [])
                        sections[mime_or_section].append(
                            (filename, brief, thumbnail, content)
                        )
                        image_count += 1

                title = book.title + " " + chapter_title
                if not image_count:
                    self.deliverlog(
                        username,
                        str(user.kindle_email),
                        title,
                        0,
                        status="can't download image",
                        tz=user.timezone,
                    )
                    rs = "No new feeds."
                    main.log.info(rs)
                    continue
                insertHtmlToc = False
                insertThumbnail = False
                oeb.metadata.clear("title")
                oeb.metadata.add("title", title)

                InsertToc(oeb, sections, toc_thumbnails, insertHtmlToc, insertThumbnail)
                oIO = byteStringIO()
                o = EPUBOutput() if user.book_type == "epub" else MOBIOutput()
                o.convert(oeb, oIO, opts, main.log)
                try:
                    ultima_log = DeliverLog.all().order("-time").get()
                except:
                    ultima_log = sorted(
                        DeliverLog.all(), key=attrgetter("time"), reverse=True
                    )
                    ultima_log = ultima_log[0] if ultima_log else None

                if ultima_log:
                    diff = datetime.datetime.utcnow() - ultima_log.datetime
                    if diff.days * 86400 + diff.seconds < 10:
                        time.sleep(8)

                self.SendToKindle(
                    username,
                    user.kindle_email,
                    title,
                    user.book_type,
                    str(oIO.getvalue()),
                    user.timezone,
                )
                book.UpdateLastDelivered(bookname, chapter_title, next_chapter_index)
                rs = "%s(%s).%s Sent!" % (
                    title,
                    local_time(tz=user.timezone),
                    user.book_type,
                )
                main.log.info(rs)
            except:
                main.log.exception(
                    u"Failed to push {} {}".format(bookname, chapter_title)
                )

    def ProcessComicRSS(self, username, user, feed):
        opts = getOpts(user.device, "comic")
        for ComicBaseClass in ComicBaseClasses:
            if feed.url.startswith(ComicBaseClass.accept_domains):
                book = ComicBaseClass(opts=opts, user=user)
                break
        else:
            msg = u"No base class for {}".format(feed.title)
            main.log.error(msg)
            return

        book.title = feed.title
        book.description = feed.title
        book.language = "zh-cn"
        book.keep_image = True
        book.oldest_article = 7
        book.fulltext_by_readability = True
        book.feeds = [(feed.title, feed.url)]
        book.url_filters = [flt.url for flt in user.urlfilter]

        return self.push_comic_book(username, user, book, opts)
