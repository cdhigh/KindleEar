#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#自动翻译和更新po文件
#Author: cdhigh <https://github.com/cdhigh>
import os, sys, datetime, shutil
sys.path.insert(0, 'D:/Programer/Project/autopo')
from autopo import createAiAgent, translateFile

thisDir = os.path.dirname(os.path.abspath(__file__))
appDir = os.path.normpath(os.path.join(thisDir, '..'))
bakDir = os.path.join(appDir, 'tests', 'pobackup')
#refPoFile = os.path.join(appDir, 'application', 'translations', 'zh', 'LC_MESSAGES', 'messages.po')
#refLang = 'zh_cn'

startTime = datetime.datetime.now()
agent = createAiAgent()
excluded = ['Email', 'Sep', 'Upl', 'Log', 'Emb', 'Tr', 'Tts', 'Ai', 'Api Key', 'Model', 'ApiKey',
    'evernote', 'SecretKey', 'pocket', 'instapaper', 'wallabag', 'facebook', 'tumblr', 'wiz', 
    'client_id', 'client_secret']
for lang in ['de', 'es', 'fr', 'it', 'ja', 'ko', 'pt', 'ru', 'tr']:
    fileName = os.path.join(appDir, 'application', 'translations', lang, 'LC_MESSAGES', 'messages.po')
    shutil.copy(fileName, os.path.join(bakDir, f'{lang}.po')) #先备份
    translateFile(fileName=fileName, agent=agent, dstLang=lang, srcLang='en',
        refPoFile=None, refLang=None, fuzzify=False, excluded=excluded)

consumed = datetime.datetime.now() - startTime
print(f'Time consumed: {str(consumed).split(".")[0]}')
os.system('pause')
