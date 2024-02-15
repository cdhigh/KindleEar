#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#后台实际的推送任务，由任务队列触发

from collections import defaultdict
import datetime, time, io, logging
from flask import Blueprint, request
from ..base_handler import *
from ..back_end.send_mail_adpt import send_to_kindle
from ..back_end.db_models import *
from ..utils import local_time
from calibre.web.feeds.recipes import compile_recipe
from ..lib.recipe_helper import *
from ..lib.build_ebook import recipes_to_ebook

bpWorker = Blueprint('bpWorker', __name__)

#<https://cloud.google.com/tasks/docs/creating-appengine-handlers>
#如果是Task触发的，则环境变量会包含以下一些变量
#X-AppEngine-QueueName/X-AppEngine-TaskName/X-AppEngine-TaskRetryCount/X-AppEngine-TaskExecutionCount/X-AppEngine-TaskETA

#提供给外部不通过任务队列直接调用的便捷接口
#注意此函数可能需要很长时间才返回
def WorkerAllNow():
    return '\n'.join([WorkerImpl(user.name) for user in KeUser.get_all()])

#下载文章和生成电子书并且发送邮件
@bpWorker.route("/worker")
def Worker():
    userName = request.args.get('userName', '')
    recipeId = request.args.get('recipeId', '')  #如果有多个Recipe，使用','分隔
    return WorkerImpl(userName, recipeId, default_log)

#执行实际抓取网页生成电子书任务
#userName: 需要执行任务的账号名
#recipeId: 需要投递的Recipe ID，如果有多个，使用逗号分隔
#返回执行结果字符串
def WorkerImpl(userName: str, recipeId: list=None, log=None):
    if not userName:
        return "The userName is empty."

    user = KeUser.get_or_none(KeUser.name == userName)
    if not user:
        return f"The user '{userName}' does not exist."

    if not log:
        log = logging.getLogger('WorkerImpl')
        log.setLevel(logging.WARN)
    
    if not recipeId:
        recipeId = [item.recipe_id for item in user.get_booked_recipe()]
    elif not isinstance(recipeId, (list, tuple)):
        recipeId = recipeId.replace('__', ':').split(',')
    
    if not recipeId:
        info = f"There are no feeds to push for user '{userName}'."
        log.warning(info)
        return info

    #编译recipe
    srcDict = GetAllRecipeSrc(user, recipeId)
    recipes = defaultdict(list) #编译好的recipe代码对象
    userCss = user.get_extra_css()
    combine_css = lambda c1, c2=userCss: f'{c1}\n\n{c2}' if c1 else c2
    for title, (bked, recipeDb, src) in srcDict.items():
        try:
            ro = compile_recipe(src)
        except Exception as e:
            log.warning('Failed to compile recipe {}: {}'.format(title, str(e)))

        if not ro.language or ro.language == 'und':
            ro.language = user.book_language

        #合并自定义css
        ro.extra_css = combine_css(ro.extra_css)
        
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
        book = recipes_to_ebook(ro, user)
        if book:
            #避免触发垃圾邮件机制，最短10s发送一次
            now = time.time() #单位为s
            if lastSendTime and (now - lastSendTime < 10):
                time.sleep(10)

            send_to_kindle(user, title, book)
            lastSendTime = time.time()
            ret.append(f"Sent {title}.{bookType}")
        else:
            save_delivery_log(user, title, 0, status='nonews')

    return '\n'.join(ret) if ret else "There are no new feeds available."


#在已订阅的Recipe或自定义RSS列表创建Recipe源码列表，最重要的作用是合并自定义RSS
#返回一个字典，键名为title，元素为 [BookedRecipe, recipe, src]
def GetAllRecipeSrc(user, idList):
    srcDict = {}
    rssList = []
    ftRssList = []
    for bked in filter(bool, [BookedRecipe.get_or_none(BookedRecipe.recipe_id == id_) for id_ in idList]):
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
            title = recipe.title
            if recipeType == 'upload': #上传的Recipe
                srcDict[title] = [bked, recipe, recipe.src]
            else: #自定义RSS
                src = GenerateRecipeSource(title, [(title, recipe.url)], user, isfulltext=recipe.isfulltext)
                srcDict[title] = [bked, recipe, src]
    return srcDict
