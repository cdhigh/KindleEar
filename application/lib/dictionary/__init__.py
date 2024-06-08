#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#词典模块的入口文件
from .dict_org import DictOrg
from .dict_cn import DictCn
from .dict_cc import DictCc

all_dict_engines = {DictOrg.name: DictOrg, DictCn.name: DictCn, DictCc.name: DictCc}

#创建一个词典实例
def CreateDictInst(name, database, host=None):
    klass = all_dict_engines.get(name, DictOrg)
    return klass(database, host)
