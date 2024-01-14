#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#后台实际的推送任务，由任务队列触发

from collections import defaultdict
import datetime, time, imghdr, io
from flask import Blueprint, request
from apps.base_handler import *
from apps.back_end.send_mail_adpt import send_to_kindle
from apps.back_end.db_models import *
from apps.utils import local_time
from lib.makeoeb import *
from calibre.ebooks.conversion.plugins.mobi_output import MOBIOutput, AZW3Output
from calibre.ebooks.conversion.plugins.epub_output import EPUBOutput
from books import BookClasses, BookClass
from books.base_book import BaseFeedBook
from books.base_comic_book import BaseComicBook

try:
    from books.comic import ComicBaseClasses, comic_domains
except ImportError:
    default_log.warning('Failed to import comic base classes.')
    ComicBaseClasses = []
    comic_domains = tuple()

bpWorker = Blueprint('bpWorker', __name__)

#<https://cloud.google.com/tasks/docs/creating-appengine-handlers>
#如果是Task触发的，则环境变量会包含以下一些变量
#X-AppEngine-QueueName/X-AppEngine-TaskName/X-AppEngine-TaskRetryCount/X-AppEngine-TaskExecutionCount/X-AppEngine-TaskETA

# 实际下载文章和生成电子书并且发送邮件
@bpWorker.route("/worker")
def Worker():
    global default_log
    args = request.args
    userName = args.get('u')
    bookId = args.get('id_')  #如果有多本书，使用','分隔
    feedsId = args.get('feedsId')
    
    user = KeUser.get_one(KeUser.name == userName)
    if not user:
        return "User not exist!"
    
    to = user.kindle_email
    if (';' in to) or (',' in to):
        to = to.replace(',', ';').replace(' ', '').split(';')
    
    bookType = user.book_type #mobi,epub
    bookMode = user.book_mode or 'periodical' #periodical,comic
    titleFmt = user.title_fmt
    tz = user.timezone
    authorFmt = user.author_format
    
    bkList = []
    #推送一些特定的书籍
    if bookId:
        bookId = [int(item) for item in bookId.split(',') if item.isdigit()]
        bkList = list(filter(bool, map(Feed.get_by_id, bookId)))

    if not bkList:
        return "There are no books to push."
                
    #仅推送自定义RSS
    feedList = []
    if feedsId:
        feedsId = [int(item) for item in feedsId.split(',') if item.isdigit()]
        feedList = list(filter(bool, map(Feed.get_by_id, feedsId)))

    bookForMeta = None
    mhFile = DEFAULT_MASTHEAD
    cvFile = DEFAULT_COVER

    if len(bkList) == 1:
        singleBook = bkList[0]
        if singleBook.builtin:
            bookForMeta = BookClass(singleBook.title)
            mhFile = bookForMeta.masthead_file
            cvFile = bookForMeta.cover_file

            #如果单独推送一个继承自BaseComicBook的书籍，则自动设置为漫画模式
            if issubclass(bookForMeta, BaseComicBook):
                bookMode = 'comic'
        else: #单独的推送自定义RSS
            bookForMeta = singleBook
    else: #多本书合并推送时使用“自定义RSS”的元属性
        bookForMeta = user.own_feeds
        cvFile = DEFAULT_COVER_BV if user.merge_books else DEFAULT_COVER
    
    if not bookForMeta:
        return "There are no books to push."

    #创建 OEBBook，并设置一些基本属性
    log = default_log
    opts = GetOpts(user.device, bookMode)
    oeb = CreateOeb(log, opts)
    oeb.container = ServerContainer(log)
    bookTitle = "{} {}".format(bookForMeta.title, local_time(titleFmt, tz)) if titleFmt else bookForMeta.title
    pubType = 'book:book:KindleEar' if bookMode == 'comic' else 'periodical:magazine:KindleEar'
    author = local_time(authorFmt, tz) if authorFmt else 'KindleEar' #修正Kindle固件5.9.x将作者显示为日期的BUG    
    setMetaData(oeb, bookTitle, bookForMeta.language, local_time("%Y-%m-%d", tz), pubType=pubType, creator=author)
    
    AddMastheadCoverToOeb(user, oeb, mhFile, cvFile, bookForMeta) #将报头和封面添加到电子书
        
    itemCnt = 0
    imgIndex = 0
    sections = defaultdict(list)
    tocThumbnails = {} #map img-url -> manifest-href

    for bk in bkList:
        if bk.builtin:
            cBook = BookClass(bk.title)
            if not cBook:
                log.warning("Book '{}' does not exist".format(bk.title))
                continue
            book = cBook(imgIndex=imgIndex, opts=opts, user=user)
            book.url_filters = [flt.url for flt in user.url_filters]
            if bk.needs_subscription: #需要登录
                subsInfo = user.subscription_info(bk.title)
                if subsInfo:
                    book.account = subsInfo.account
                    book.password = subsInfo.password
            if issubclass(cBook, BaseComicBook):
                PushComicBook(username, user, book)
                continue
        else:  # 自定义RSS
            if bk.feedsCount == 0:
                continue
                
            book = BaseFeedBook(imgIndex=imgIndex, opts=opts, user=user)
            book.title = bk.title
            book.description = bk.description
            book.language = bk.language
            book.keep_image = bk.keep_image
            book.oldest_article = bk.oldest_article
            book.fulltext_by_readability = True
            feeds = feedList if feedList else bk.feeds
            book.feeds = []
            for feed in feeds:
                if feed.url.startswith(comic_domains):
                    ProcessComicRSS(username, user, feed)
                else:
                    book.feeds.append((feed.title, feed.url, feed.isfulltext))
            book.url_filters = [flt.url for flt in user.url_filters]
        
        #书的质量可能不一，一本书的异常不能影响其他书籍的推送
        try:
            #可能为 ItemHtmlTuple, ItemImageTuple, ItemCssTuple
            for item in book.Items():
                if isinstance(item, ItemImageTuple): #图像文件
                    id_, href = oeb.manifest.generate(id='img', href=item.fileName)
                    oeb.manifest.add(id_, href, item.mime, data=item.content)
                    if item.isThumbnail:
                        tocThumbnails[item.url] = href
                    imgIndex += 1  #保证多本书集中推送时图像文件的唯一性
                elif isinstance(item, ItemCssTuple): #CSS
                    if item.url not in oeb.manifest.hrefs: #Only one css needed
                        oeb.manifest.add('css', item.url, "text/css", data=item.content)
                else: #网页文件
                    sections[item.section].append(item)
                    itemCnt += 1
        except Exception as e:
            log.warning("Failed to push <{}>: {}".format(book.title, e))
            continue
    
    volumeTitle = ''
    if itemCnt > 0:
        #插入单独的目录页
        InsertToc(oeb, sections, tocThumbnails)
        oIO = io.BytesIO()
        o = EPUBOutput() if bookType == "epub" else MOBIOutput()
        o.convert(oeb, oIO, opts, log)
        ultimaLog = sorted(DeliverLog.get_all(), key=attrgetter('datetime'), reverse=True)
        ultimaLog = ultimaLog[0] if ultimaLog else None
        if ultimaLog:
            diff = datetime.datetime.utcnow() - ultimaLog.datetime
            if diff.days * 86400 + diff.seconds < 10:
                time.sleep(5)
        send_to_kindle(username, to, bookForMeta.title + volumeTitle, bookType, oIO.getvalue(), tz)
        rs = "{}.{} Sent".format(bookTitle, bookType)
        #log.info(rs)
        return rs
    else:
        deliver_log(username, str(to), bookForMeta.title + volumeTitle, 0, status='nonews', tz=tz)
        rs = "No new feeds available."
        #log.info(rs)
        return rs

#将报头和封面添加到电子书
#user: 账号数据库行实例
#oeb: OEBBook实例
#mhFile: masthead文件路径
#cvFile: cover文件路径
#bookForMeta: 提供一些基本信息的书本实例
def AddMastheadCoverToOeb(user, oeb, mhFile, cvFile, bookForMeta):
    if mhFile: #设置报头
        id_, href = oeb.manifest.generate('masthead', mhFile) # size:600*60
        oeb.manifest.add(id_, href, ImageMimeFromName(mhFile))
        oeb.guide.add('masthead', 'Masthead Image', href)
    
    #设置封面
    if cvFile:
        imgData = None
        imgMime = ''
        #使用保存在数据库的用户上传的封面
        if cvFile == DEFAULT_COVER and user.cover:
            imgData = user.cover
            imgMime = 'image/jpeg' #保存在数据库中的只可能是jpeg格式
        elif callable(cvFile): #如果封面需要回调的话
            try:
                imgData = bookForMeta().cvFile()
            except:
                default_log.warning("Failed to fetch cover for book [{}]".format(bookForMeta.title))
                cvFile = DEFAULT_COVER

            if imgData:
                imgType = imghdr.what(None, imgData)
                if imgType: #如果是合法图片
                    imgMime = "image/{}".format(imgType)
                else:
                    default_log.warning('Content of cover is invalid : {}'.format(bookForMeta.title))
                    imgData = None
        
        if imgData and imgMime:
            id_, href = oeb.manifest.generate('cover', 'cover.jpg')
            oeb.manifest.add(id_, href, imgMime, data=imgData)
        else:
            id_, href = oeb.manifest.generate('cover', cvFile)
            oeb.manifest.add(id_, href, ImageMimeFromName(cvFile))
        oeb.guide.add('cover', 'Cover', href)
        oeb.metadata.add('cover', id_)

#单独处理漫画RSS
def ProcessComicRSS(userName, user, feed):
    opts = GetOpts(user.device, "comic")
    for comicClass in ComicBaseClasses:
        if feed.url.startswith(comicClass.accept_domains):
            book = comicClass(opts=opts, user=user)
            break
    else:
        log.warning("There is No base class for {}".format(feed.title))
        return

    book.title = feed.title
    book.description = feed.title
    book.language = "zh-cn"
    book.keep_image = True
    book.oldest_article = 7
    book.fulltext_by_readability = True
    book.feeds = [(feed.title, feed.url)]
    book.url_filters = [flt.url for flt in user.url_filters]

    return PushComicBook(userName, user, book, opts)

#单独推送漫画
def PushComicBook(userName, user, book, opts=None):
    global default_log
    log = default_log
    if not opts:
        opts = GetOpts(user.device, "comic")
    oeb = CreateOeb(log, opts)
    pubType = 'book:book:KindleEar'
    language = 'zh-cn'

    setMetaData(oeb, book.title, language, local_time("%Y-%m-%d", user.timezone), pubType=pubType)
    oeb.container = ServerContainer(log)

    #guide
    id_, href = oeb.manifest.generate('masthead', DEFAULT_MASTHEAD) # size:600*60
    oeb.manifest.add(id_, href, ImageMimeFromName(DEFAULT_MASTHEAD))
    oeb.guide.add('masthead', 'Masthead Image', href)

    id_, href = oeb.manifest.generate('cover', DEFAULT_COVER)
    item = oeb.manifest.add(id_, href, ImageMimeFromName(DEFAULT_COVER))

    oeb.guide.add('cover', 'Cover', href)
    oeb.metadata.add('cover', id_)

    itemCnt = 0
    imgIndex = 0
    sections = {}
    tocThumbnails = {} #map img-url -> manifest-href

    chapters = book.ParseFeedUrls()
    if not chapters:
        deliver_log(userName, str(user.kindle_email), book.title, 0, status="nonews", tz=user.timezone)
        return

    rs = 'ok'
    for (bookname, chapter_title, img_list, chapter_url, next_chapter_index) in chapters:
        try:
            image_count = 0
            for (mime_or_section, url, filename, content, brief, thumbnail) in book.GenImageItems(img_list, chapter_url):
                if not mime_or_section or not filename or not content:
                    continue

                if mime_or_section.startswith("image/"):
                    id_, href = oeb.manifest.generate(id="img", href=filename)
                    item = oeb.manifest.add(id_, href, mime_or_section, data=content)
                    if thumbnail:
                        tocThumbnails[url] = href
                else:
                    sections.setdefault(mime_or_section, [])
                    sections[mime_or_section].append((filename, brief, thumbnail, content))
                    image_count += 1

            title = book.title + " " + chapter_title
            if not image_count:
                deliverlog(userName, str(user.kindle_email), title, 0, status="can't download image", tz=user.timezone)
                rs = "No new feeds."
                log.info(rs)
                continue
            insertHtmlToc = False
            insertThumbnail = False
            oeb.metadata.clear("title")
            oeb.metadata.add("title", title)

            InsertToc(oeb, sections, tocThumbnails, insertHtmlToc, insertThumbnail)
            oIO = io.BytesIO()
            o = EPUBOutput() if user.book_type == "epub" else MOBIOutput()
            o.convert(oeb, oIO, opts, log)
            ultima_log = sorted(DeliverLog.get_all(), key=attrgetter("datetime"), reverse=True)
            ultima_log = ultima_log[0] if ultima_log else None
            if ultima_log:
                diff = datetime.datetime.utcnow() - ultima_log.datetime
                if diff.days * 86400 + diff.seconds < 10:
                    time.sleep(5)

            send_to_kindle(userName, user.kindle_email, title, user.book_type, oIO.getvalue(), user.timezone)
            book.UpdateLastDelivered(bookname, chapter_title, next_chapter_index)
            rs = "{}({}).{} Sent!" % (title, local_time(tz=user.timezone), user.book_type)
            #log.info(rs)
        except:
            rs = "Failed to push {} {}".format(bookname, chapter_title)
            #log.exception("Failed to push {} {}".format(bookname, chapter_title))

    return rs



