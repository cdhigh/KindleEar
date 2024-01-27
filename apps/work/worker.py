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
#from lib.makeoeb import *
#from calibre.ebooks.conversion.plugins.mobi_output import MOBIOutput, AZW3Output
#from calibre.ebooks.conversion.plugins.epub_output import EPUBOutput
#from books.base_book import BaseFeedBook
from lib.recipe_helper import *

bpWorker = Blueprint('bpWorker', __name__)

#<https://cloud.google.com/tasks/docs/creating-appengine-handlers>
#如果是Task触发的，则环境变量会包含以下一些变量
#X-AppEngine-QueueName/X-AppEngine-TaskName/X-AppEngine-TaskRetryCount/X-AppEngine-TaskExecutionCount/X-AppEngine-TaskETA

#在已订阅的Recipe或自定义RSS列表创建Recipe源码列表，最重要的作用是合并自定义RSS
#返回一个字典，键名为title，元素为 [BookedRecipe, recipe, src]
def GetAllRecipeSrc(user, idList):
    srcDict = {}
    rssList = []
    ftRssList = []
    for bked in filter(bool, [BookedRecipe.get_one(BookedRecipe.recipe_id == id_) for id_ in idList]):
        recipeId = bked.recipe_id
        recipeType, dbId = Recipe.type_and_id(recipeId)
        if recipeType == 'builtin':
            bnInfo = GetBuiltinRecipeInfo(recipeId)
            src = GetBuiltinRecipeSource(recipeId)
            if bnInfo and src:
                srcDict[bnInfo.get('title', '')] = [bked, bnInfo, src]
            continue
        
        recipe = Recipe.get_by_id_or_none(dbId)
        if recipe:
            if recipeType == 'upload': #上传的Recipe
                srcDict[recipe.title] = [bked, recipe, recipe.src]
            elif recipe.isfulltext: #自定义RSS
                ftRssList.append((bked, recipe))
            else:
                rssList.append((bked, recipe))

    #全文和概要rss各建一个源码
    title = user.book_title
    if ftRssList:
        feeds = [(item.title, item.url) for bked, item in ftRssList]
        srcDict[title + '_f'] = [*ftRssList[0],  GenerateRecipeSource(title, feeds, user.oldest_article, isfulltext=True)]

    if rssList:
        feeds = [(item.title, item.url) for bked, item in rssList]
        srcDict[title] = [*rssList[0], GenerateRecipeSource(title, feeds, user.oldest_article, isfulltext=False)]
    return srcDict

# 实际下载文章和生成电子书并且发送邮件
@bpWorker.route("/worker")
def Worker():
    global default_log
    args = request.args
    userName = args.get('userName', '')
    recipeId = args.get('recipeId', '')  #如果有多个Recipe，使用','分隔
    
    return WorkerImpl(userName, recipeId.split(','))

#执行实际抓取网页生成电子书任务
#userName: 需要执行任务的账号名
#idList: 需要投递的Recipe ID列表
#返回执行结果字符串
def WorkerImpl(userName: str, idList: list):
    if not userName or not idList:
        return "Parameters invalid."

    user = KeUser.get_one(KeUser.name == userName)
    if not user:
        return "The user does not exist."
    
    to = user.kindle_email.replace(';', ',').split(',')
    
    srcDict = GetAllRecipeSrc(user, bkInstList)
    for title, (bked, recipe, src) in srcDict.items():
        ConvertToEbook()

                
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
    
    bookType = user.book_type #mobi,epub
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
        send_to_kindle(username, to, bookForMeta.title, bookType, oIO.getvalue(), tz)
        rs = "{}.{} Sent".format(bookTitle, bookType)
        return rs
    else:
        deliver_log(username, str(to), bookForMeta.title, 0, status='nonews', tz=tz)
        rs = "No new feeds available."
        return rs

#创建OEB并设置一些基础信息
#user: 用户账号实例
#title: 书籍标题
#language: 书籍语种，kindle用来查词时使用，调用不同的词典
#返回一个OEBBook实例
def CreateOeb(user: KeUser, title: str, language: str):
    bookMode = user.book_mode or 'periodical' #periodical,comic
    titleFmt = user.title_fmt
    tz = user.timezone
    authorFmt = user.author_format

    opts = GetOpts(user.device, bookMode)
    oeb = CreateEmptyOeb(opts)
    
    bookTitle = "{} {}".format(title, local_time(titleFmt, tz)) if titleFmt else title
    pubType = 'book:book:KindleEar' if bookMode == 'comic' else 'periodical:magazine:KindleEar'
    author = local_time(authorFmt, tz) if authorFmt else 'KindleEar' #修正Kindle固件5.9.x将作者显示为日期的BUG    
    setMetaData(oeb, bookTitle, language, local_time("%Y-%m-%d", tz), pubType=pubType, creator=author)
    return oeb

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
    oeb = CreateEmptyOeb(log, opts)
    pubType = 'book:book:KindleEar'
    language = 'zh-cn'

    setMetaData(oeb, book.title, language, local_time("%Y-%m-%d", user.timezone), pubType=pubType)
    
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
            rs = "{}({}).{} Sent!" % (title, local_time(tz=user.timezone), user.book_type)
            #log.info(rs)
        except:
            rs = "Failed to push {} {}".format(bookname, chapter_title)
            #log.exception("Failed to push {} {}".format(bookname, chapter_title))

    return rs



