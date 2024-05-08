#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#关系数据库行结构定义，使用peewee ORM
#根据以前的经验，经常出现有网友部署时没有成功建立数据库索引，所以现在排序在应用内处理，数据量不大
#Author: cdhigh <https://github.com/cdhigh>
import os, json, datetime
from peewee import *
from playhouse.db_url import connect
from playhouse.shortcuts import model_to_dict

#用于在数据库结构升级后的兼容设计，数据库结构和前一版本不兼容则需要升级此版本号
DB_VERSION = 1
dbName = os.getenv('DATABASE_URL', '')
if dbName.startswith('sqlite:///'): #support sqlite relative path
    fileName = dbName[10:]
    if not fileName.startswith('/'):
        dbName = 'sqlite:///{}'.format(os.path.join(appDir, fileName))

if dbName == 'sqlite://:memory:':
    dbInstance = SqliteDatabase(':memory:')
else:
    dbInstance = connect(dbName)

#调用此函数正式连接到数据库（打开数据库）
def connect_database():
    global dbInstance
    dbInstance.connect(reuse_if_open=True)

#关闭数据库连接
def close_database():
    global dbInstance
    if not dbInstance.is_closed() and dbName != 'sqlite://:memory:':
        dbInstance.close()
        
#自定义字段，在本应用用来保存列表
class JSONField(TextField):
    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        if value is not None:
            return json.loads(value)

    @classmethod
    def list_default(cls):
        return []
    @classmethod
    def dict_default(cls):
        return {}

#数据表的共同基类
class MyBaseModel(Model):
    class Meta:
        database = dbInstance
    
    @classmethod
    def get_all(cls, *query):
        if query:
            return cls.select().where(*query).execute()
        else:
            return cls.select().execute()
            
    #如果取不到，返回None
    @classmethod
    def get_by_id_or_none(cls, id_):
        try:
            return cls.get_by_id(int(id_))
        except:
            return None

    #将当前行数据转换为一个字典结构，由子类使用，将外键转换为ID，日期转换为字符串
    #可以传入 only=[Book.title, ...]，或 exclude=[]
    def to_dict(self, **kwargs):
        ret = model_to_dict(self, **kwargs)
        ret.pop('key', None)
        ret.pop('_id', None)
        for key in ret:
            data = ret[key]
            if isinstance(data, datetime.datetime):
                ret[key] = data.strftime('%Y-%m-%d %H:%M:%S')
        return ret
