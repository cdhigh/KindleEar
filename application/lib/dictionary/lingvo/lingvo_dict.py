#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#lingvo dsl 离线词典支持
#Author: cdhigh <https://github.com/cdhigh>
import os, re
from application.ke_utils import loc_exc_pos
from .dsl_reader import DslReader

#获取本地的dsl文件列表，只有列表，没有校验是否有效
def getDslDictList():
    dictDir = os.environ.get('DICTIONARY_DIR')
    if not dictDir or not os.path.isdir(dictDir):
        return {}

    ret = {}
    for dirPath, _, fileNames in os.walk(dictDir):
        for fileName in fileNames:
            if fileName.lower().endswith('.dsl'):
                dictName = os.path.splitext(fileName)[0]
                #为了界面显示和其他dict的一致，键为词典全路径名，值为词典名字
                ret[os.path.join(dirPath, fileName)] = dictName
    return ret

class LingvoDict:
    name = "lingvo"
    mode = "offline"
    #词典列表，键为词典缩写，值为词典描述
    databases = getDslDictList()

    #更新词典列表
    @classmethod
    def refresh(cls):
        cls.databases = getDslDictList()

    def __init__(self, database='', host=None):
        self.database = database
        self.dictionary = None
        self.initError = None
        if database in self.databases:
            try:
                self.dictionary = DslReader(database)
            except:
                self.initError = loc_exc_pos(f'Init LingvoDict failed: {self.databases[database]}')
                default_log.warning(self.initError)
        else:
            self.initError = f'Dict not found: {database}'
            default_log.warning(self.initError)

    #返回当前使用的词典名字
    def __repr__(self):
        return '{} [{}]'.format(self.name, self.databases.get(self.database, ''))
        
    def definition(self, word, language=''):
        return self.initError if self.initError else self.dictionary.get(word)
