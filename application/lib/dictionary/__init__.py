#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#词典模块的入口文件
from .dict_org import DictOrg
from .dict_cn import DictCn
from .dict_cc import DictCc
from .stardict import StarDict
from .merriam_webster import MerriamWebster

all_dict_engines = {DictOrg.name: DictOrg, DictCn.name: DictCn, DictCc.name: DictCc,
    MerriamWebster.name: MerriamWebster, StarDict.name: StarDict}

#创建一个词典实例
def CreateDictInst(engine, database, host=None):
    klass = all_dict_engines.get(engine, DictOrg)
    return klass(database, host)

#获取某个引擎某个数据库的显示名字
def GetDictDisplayName(engine, database):
    klass = all_dict_engines.get(engine, DictOrg)
    return klass.databases.get(database, database)
