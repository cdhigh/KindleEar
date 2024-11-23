#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#词典模块的入口文件
from .dict_org import DictOrg
from .dict_cn import DictCn
from .dict_cc import DictCc
from .merriam_webster import MerriamWebster
from .oxford_learners import OxfordLearners
from .stardict import StarDict
from .mdict import MDict
from .lingvo import LingvoDict
from .babylon import BabylonDict

all_dict_engines = {DictOrg.name: DictOrg, DictCn.name: DictCn, DictCc.name: DictCc,
    MerriamWebster.name: MerriamWebster, OxfordLearners.name: OxfordLearners,
    StarDict.name: StarDict, MDict.name: MDict, LingvoDict.name: LingvoDict,
    BabylonDict.name: BabylonDict}

#创建一个词典实例
def CreateDictInst(engine, database, host=None):
    klass = all_dict_engines.get(engine, DictOrg)
    return klass(database, host)

#获取某个引擎某个数据库的显示名字
def GetDictDisplayName(engine, database):
    klass = all_dict_engines.get(engine, DictOrg)
    return klass.databases.get(database, database)
