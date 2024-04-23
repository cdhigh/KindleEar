#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#后台实际的推送任务，由任务队列触发
import os, datetime, time, io, logging
from collections import defaultdict
from flask import Blueprint, request
from ..base_handler import *
from ..back_end.send_mail_adpt import send_to_kindle
from ..back_end.db_models import *
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
    if not log:
        log = default_log

    if not userName:
        ret = "The userName is empty."
        log.warning(ret)
        return ret

    user = KeUser.get_or_none(KeUser.name == userName)
    if not user:
        ret = f"The user '{userName}' does not exist."
        log.warning(ret)
        return ret

    if not recipeId:
        recipeId = [item.recipe_id for item in user.get_booked_recipe()]
    elif not isinstance(recipeId, (list, tuple)):
        recipeId = recipeId.replace('__', ':').split(',')
    
    if not recipeId:
        ret = f"There are no feeds to push for user '{userName}'."
        log.warning(ret)
        return ret

    startTime = time.time()

    #编译recipe
    srcDict = GetAllRecipeSrc(user, recipeId) #返回一个字典，键名为title，元素为 [BookedRecipe, Recipe, src]
    recipes = defaultdict(list) #用于保存编译好的recipe代码对象
    userCss = user.get_extra_css()
    combine_css = lambda c1, c2=userCss: f'{c1}\n\n{c2}' if c1 else c2
    for title, (bked, recipeDb, src) in srcDict.items():
        try:
            ro = compile_recipe(src)
        except Exception as e:
            log.warning('Failed to compile recipe {}: {}'.format(title, str(e)))
            continue

        if not ro.language or ro.language == 'und':
            ro.language = user.book_cfg('language')

        ro.extra_css = combine_css(ro.extra_css) #合并自定义css
        ro.translator = bked.translator #设置网页翻译器信息
        ro.tts = bked.tts.copy() #文本转语音设置，需要中途修改tts内容
        
        #如果需要登录网站
        if ro.needs_subscription:
            ro.username = bked.account
            ro.password = bked.password
        
        if bked.separated:
            recipes[ro.title].append(ro)
        else:
            recipes[user.book_cfg('title')].append(ro)
    
    #逐个生成电子书推送
    lastSendTime = 0
    bookType = user.book_cfg('type')
    ret = []
    for title, roList in recipes.items():
        book = recipes_to_ebook(roList, user)

        #如果有TTS音频，先推送音频
        ext, audio = MergeAudioSegment(roList)
        if audio:
            audioName = f'{title}.{ext}'
            to = roList[0].tts.get('send_to') or user.cfg('kindle_email')
            send_to_kindle(user, audioName, (audioName, audio), to=to)
            lastSendTime = time.time()

        if book:
            #避免触发垃圾邮件机制，最短10s发送一次
            now = time.time() #单位为s
            if lastSendTime and (now - lastSendTime < 10):
                time.sleep(10)

            send_to_kindle(user, title, book)
            lastSendTime = time.time()
            ret.append(f"Sent {title}.{bookType}")
        elif not audio:
            save_delivery_log(user, title, 0, status='nonews')

    elaspTime = (time.time() - startTime) / 60.0
    if ret:
        ret = '\n'.join(ret)
        if '\n' in ret:
            ret += f'\nConsumed time: {elaspTime:.1f} minutes.'
        else:
            ret += f' [Consumed time: {elaspTime:.1f} minutes].'
    else:
        ret = "There are no new feeds available."
    log.warning(ret)
    return ret


#在已订阅的Recipe或自定义RSS列表创建Recipe源码列表
#返回一个字典，键名为title，元素为 [BookedRecipe, Recipe, src]
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

#返回可用的mp3cat执行文件路径
def mp3cat_path():
    import subprocess, platform
    mp3Cat = 'mp3cat'
    isWindows = 'Windows' in platform.system()
    execFile = 'mp3cat.exe' if isWindows else 'mp3cat'
    try: #优先使用系统安装的mp3cat
        subprocess.run([execFile, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, shell=True)
        default_log.debug('Using system mp3cat')
    except: #subprocess.CalledProcessError:
        mp3Cat = os.path.join(appDir, 'tools', 'mp3cat', execFile)
        try:
            subprocess.run([mp3Cat, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, shell=True)
            default_log.debug('Using app mp3cat')
        except Exception as e:
            #default_log.warning(f"Cannot execute mp3cat. Please check file exists and permissions: {e}")
            mp3Cat = ''
    return mp3Cat

#合并TTS生成的音频片段
def MergeAudioSegment(roList):
    audioDirs = [ro.tts.get('audio_dir') for ro in roList if ro.tts.get('audio_dir')]
    ret = ('', None)
    if not audioDirs:
        return ret

    mp3Cat = mp3cat_path()
    pymp3cat = None
    if not mp3Cat:
        import pymp3cat
        default_log.info('Using python version mp3cat')

    import shutil, subprocess
    from calibre.ptempfile import PersistentTemporaryDirectory
    tempDir = PersistentTemporaryDirectory(prefix='ttsmerg_', dir=os.environ.get('KE_TEMP_DIR'))

    chapters = []
    #先合并每个recipe生成的片段
    for idx, ro in enumerate(roList):
        mp3Files = [mp3 for mp3 in (ro.tts.get('audio_files') or [])]
        if not mp3Files:
            continue
        outputFile = os.path.join(tempDir, f'output_{idx:04d}.mp3')
        if mp3Cat:
            mp3Files = ' '.join(mp3Files)
            runRet = subprocess.run(f'{mp3Cat} {mp3Files} -f -q -o {outputFile}', shell=True)
            if (runRet.returncode == 0) and os.path.exists(outputFile):
                chapters.append(outputFile)
        else:
            try:
                pymp3cat.merge(outputFile, mp3Files, quiet=True)
                if os.path.exists(outputFile):
                    chapters.append(outputFile)
            except Exception as e:
                default_log.warning('Failed to merge mp3 by pymp3cat: {e}')


    #再将所有recipe的音频合并为一个大的文件
    if len(chapters) == 1:
        try:
            with open(chapters[0], 'rb') as f:
                data = f.read()
            ret = ('mp3', data)
        except Exception as e:
            default_log.warning(f'Failed to read "{chapters[0]}"')
    elif chapters:
        outputFile = os.path.join(tempDir, 'final.mp3')
        info = ''
        if mp3Cat:
            mp3Files = ' '.join(chapters)
            runRet = subprocess.run(f'{mp3Cat} {mp3Files} -f -q -o {outputFile}', shell=True)
            if runRet.returncode != 0:
                info = f'mp3cat return code : {runRet.returncode}'
        else:
            try:
                pymp3cat.merge(outputFile, chapters, quiet=True)
            except Exception as e:
                info = 'Failed merge mp3 by pymp3cat: {e}'

        if not info and os.path.exists(outputFile):
            try:
                with open(outputFile, 'rb') as f:
                    data = f.read()
                ret = ('mp3', data)
            except Exception as e:
                default_log.warning(f'Failed to read "{outputFile}": {e}')
        else:
            default_log.warning(info if info else 'Failed merge mp3')

    #清理临时文件
    for dir_ in [*audioDirs, tempDir]:
        try:
            shutil.rmtree(dir_)
        except Exception as e:
            default.log.debug(f"An error occurred while deleting '{item}': {e}")

    return ret
