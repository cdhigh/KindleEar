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
from calibre.web.feeds.recipes import compile_recipe
from lib.recipe_helper import *
from lib.build_ebook import ConvertRecipeToEbook

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
            elif recipe.isfulltext: #全文自定义RSS
                ftRssList.append((bked, recipe))
            else: #摘要自定义RSS
                rssList.append((bked, recipe))

    #全文和概要rss各建一个源码
    title = user.book_title
    if ftRssList:
        feeds = [(item.title, item.url) for bked, item in ftRssList]
        srcDict[title + '_f'] = [*ftRssList[0], GenerateRecipeSource(title, feeds, user, isfulltext=True)]

    if rssList:
        feeds = [(item.title, item.url) for bked, item in rssList]
        srcDict[title] = [*rssList[0], GenerateRecipeSource(title, feeds, user, isfulltext=False)]
    return srcDict

# 实际下载文章和生成电子书并且发送邮件
@bpWorker.route("/worker")
def Worker():
    global default_log
    log = default_log
    args = request.args
    userName = args.get('userName', '')
    recipeId = args.get('recipeId', '')  #如果有多个Recipe，使用','分隔
    
    return WorkerImpl(userName, recipeId.split(','), log)

#执行实际抓取网页生成电子书任务
#userName: 需要执行任务的账号名
#idList: 需要投递的Recipe ID列表
#返回执行结果字符串
def WorkerImpl(userName: str, idList: list, log):
    if not userName or not idList:
        return "Parameters invalid."

    user = KeUser.get_one(KeUser.name == userName)
    if not user:
        return "The user does not exist."
    
    to = user.kindle_email.replace(';', ',').split(',')
    tz = user.timezone
    
    #编译recipe
    srcDict = GetAllRecipeSrc(user, bkInstList)
    recipes = defaultdict(list) #编译好的recipe代码对象
    for title, (bked, recipeDb, src) in srcDict.items():
        try:
            ro = compile_recipe(src)
            assert(ro.title)
        except Exception as e:
            log.warning('Failed to compile recipe {}: {}'.format(title, e))

        if not ro.language or ro.language == 'und':
            ro.language = user.book_language

        #合并自定义css
        if user.css_content:
            ro.extra_css = ro.extra_css + '\n\n' + user.css_content if ro.extra_css else user.css_content

        #如果需要登录网站
        if ro.needs_subscription:
            ro.username = bked.account
            ro.password = bked.password

        if bked.separated:
            recipes[ro.title].append(ro)
        else:
            recipes[user.book_title].append(ro)
    
    #逐个生成电子书推送
    lastSendTime = 0
    bookType = user.book_type
    ret = []
    for title, ro in recipes.items():
        output = io.BytesIO()
        ConvertRecipeToEbook(ro, output, user)
        book = output.getvalue()
        if book:
            #避免触发垃圾邮件机制，最短10s发送一次
            now = time.time() #单位为s
            if lastSendTime and (now - lastSendTime < 10):
                time.sleep(10)

            send_to_kindle(userName, to, title, bookType, book, tz)
            lastSendTime = time.time()
            ret.append(f"Sent {title}.{bookType}")
        else:
            save_delivery_log(userName, to, title, 0, status='nonews', tz=tz)

    return '\n'.join(ret) if ret else "There are no new feeds available."

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
