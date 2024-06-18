#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#后台实际的推送任务，由任务队列触发
#Author: cdhigh<https://github.com/cdhigh>
import os, sys, time
from typing import Union
from collections import defaultdict
from flask import Blueprint, request, current_app as app
from ..base_handler import *
from ..utils import filesizeformat
from ..back_end.send_mail_adpt import send_to_kindle
from ..back_end.db_models import *
from calibre.web.feeds.recipes import compile_recipe
from recipe_helper import *
from build_ebook import convert_book

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
    args = request.args
    userName = args.get('userName', '')
    recipeId = args.get('recipeId', '')  #如果有多个Recipe，使用','分隔
    reason = args.get('reason', 'cron') #cron/manual
    key = args.get('key')
    if key == app.config['DELIVERY_KEY']:
        return WorkerImpl(userName, recipeId, reason, default_log)
    else:
        return 'Key invalid.'

#执行实际抓取网页生成电子书任务
#userName: 需要执行任务的账号名
#recipeId: 需要投递的Recipe ID，如果有多个，使用逗号分隔
#返回执行结果字符串
def WorkerImpl(userName: str, recipeId: Union[list,str,None]=None, reason='cron', log=None, key=None):
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
        if not ro:
            log.warning('Failed to compile recipe {}: {}'.format(title, 'Cannot find any subclass of BasicNewsRecipe.'))
            continue

        if not ro.language or ro.language == 'und':
            ro.language = user.book_cfg('language')
            
        ro.delivery_reason = reason
        #合并自定义css
        ro.extra_css = combine_css(ro.extra_css) #type:ignore
        ro.translator = bked.translator.copy() #设置网页翻译器信息
        ro.tts = bked.tts.copy() #文本转语音设置，需要中途修改tts内容
        
        #如果需要登录网站
        if ro.needs_subscription:
            ro.username = bked.account #type:ignore
            ro.password = bked.password #type:ignore
        
        if bked.separated:
            recipes[ro.title].append(ro)
        else:
            recipes[user.book_cfg('title')].append(ro)
    
    #逐个生成电子书推送
    lastSendTime = 0
    bookType = user.book_cfg('type')
    ret = []
    delivery_mode = user.cfg('delivery_mode') or ''
    for title, roList in recipes.items():
        if len(roList) == 1:
            title = roList[0].title
        book = convert_book(roList, 'recipe', user)
        
        #如果有TTS音频，先推送音频
        ext, audio = MergeAudioSegment(roList)
        if audio:
            if lastSendTime and (time.time() - lastSendTime < 10):
                time.sleep(10)

            audioName = f"{title}.{ext}"
            audioNameWithTime = f"{title}_{user.local_time('%Y-%m-%d_%H-%M')}.{ext}"
            to = roList[0].tts.get('send_to') or user.cfg('kindle_email')
            send_to_kindle(user, audioName, (audioNameWithTime, audio), to=to)
            lastSendTime = time.time()
            ret.append(f'Sent "{audioName}" ({filesizeformat(len(audio))})')

        if book:
            if 'email' in delivery_mode:
                #避免触发垃圾邮件机制，最短10s发送一次
                if lastSendTime and (time.time() - lastSendTime < 10): #单位为s
                    time.sleep(10)

                send_to_kindle(user, title, book)
                lastSendTime = time.time()
                ret.append(f'Sent "{title}.{bookType}" ({filesizeformat(len(book))})')
            elif 'local' in delivery_mode:
                ret.append(f'Saved "{title}"')
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
        titles = ', '.join(recipes.keys())
        ret = f"There are no new feeds available: {userName}: [{titles}]"
    log.warning(ret)
    return ret


#在已订阅的Recipe或自定义RSS列表创建Recipe源码列表
#返回一个字典，键名为title，元素为 [BookedRecipe, Recipe, src]
def GetAllRecipeSrc(user, idList):
    srcDict = {}
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
    try:
        import subprocess
        execFile = 'mp3cat.exe' if 'win' in sys.platform.lower() else 'mp3cat'
        subprocess.run([execFile, "--version"], check=True, shell=True)
        default_log.debug('Using system mp3cat')
    except: #subprocess.CalledProcessError:
        #default_log.warning(f"Cannot execute mp3cat. Please check file exists and permissions: {e}")
        execFile = ''
    return execFile

#合并TTS生成的音频片段
#返回 (ext, audio)
def MergeAudioSegment(roList):
    audioDirs = [ro.tts.get('audio_dir') for ro in roList if ro.tts.get('audio_dir')]
    ret = ('', None)
    if not audioDirs:
        return ret

    mp3Cat = mp3cat_path()
    if mp3Cat:
        import subprocess
    else:
        import pymp3cat
        default_log.info('Using python version mp3cat')

    from calibre.ptempfile import PersistentTemporaryDirectory
    tempDir = PersistentTemporaryDirectory(prefix='ttsmerg_', dir=os.environ.get('KE_TEMP_DIR'))

    chapters = []
    #先合并每个recipe生成的片段
    for idx, ro in enumerate(roList):
        mp3Files = [mp3 for mp3 in (ro.tts.get('audio_files') or [])]
        if not mp3Files:
            continue
        outputFile = os.path.join(tempDir, f'output_{idx:04d}.mp3')
        mergedFiles = 0
        if mp3Cat:
            mergedFiles = len(mp3Files)
            mp3Files = ' '.join(mp3Files)
            runRet = subprocess.run(f'{mp3Cat} {mp3Files} -f -q -o {outputFile}', shell=True) #type:ignore
            if runRet.returncode != 0:
                mergedFiles = 0
                info = f'mp3cat return code : {runRet.returncode}'
        else:
            try:
                mergedFiles = pymp3cat.merge(outputFile, mp3Files, quiet=True) #type:ignore
            except Exception as e:
                default_log.warning('Failed to merge mp3 by pymp3cat: {e}')

        if mergedFiles and os.path.exists(outputFile):
            chapters.append(outputFile)


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
        mergedFiles = 0
        if mp3Cat:
            mergedFiles = len(chapters)
            mp3Files = ' '.join(chapters)
            runRet = subprocess.run(f'{mp3Cat} {mp3Files} -f -q -o {outputFile}', shell=True) #type:ignore
            if runRet.returncode != 0:
                mergedFiles = 0
                info = f'mp3cat return code : {runRet.returncode}'
        else:
            try:
                mergedFiles = pymp3cat.merge(outputFile, chapters, quiet=True) #type:ignore
            except Exception as e:
                info = 'Failed merge mp3 by pymp3cat: {e}'

        if not info and mergedFiles and os.path.exists(outputFile):
            try:
                with open(outputFile, 'rb') as f:
                    data = f.read()
                ret = ('mp3', data)
            except Exception as e:
                default_log.warning(f'Failed to read "{outputFile}": {e}')
        else:
            default_log.warning(info if info else 'Failed merge mp3')

    #清理临时文件
    import shutil
    for dir_ in [*audioDirs, tempDir]:
        try:
            shutil.rmtree(dir_)
        except Exception as e:
            default_log.debug(f"An error occurred while deleting '{dir_}': {e}")

    return ret
