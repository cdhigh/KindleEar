#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#关系数据库行结构定义，使用peewee ORM
#根据以前的经验，经常出现有网友部署时没有成功建立数据库索引，所以现在排序在应用内处理，数据量不大
#Author: cdhigh <https://github.com/cdhigh>
import os, json, datetime
from peewee import *
from playhouse.db_url import connect
from playhouse.shortcuts import model_to_dict
from config import (DATABASE_ENGINE, DATABASE_HOST, DATABASE_PORT, DATABASE_USERNAME, 
                DATABASE_PASSWORD, DATABASE_NAME)

#用于在数据库结构升级后的兼容设计，数据库结构和前一版本不兼容则需要升级此版本号
DB_VERSION = 1

if '://' in DATABASE_NAME:
    dbInstance = connect(DATABASE_NAME)
elif DATABASE_ENGINE == "sqlite":
    thisDir = os.path.dirname(os.path.abspath(__file__))
    dbName = os.path.normpath(os.path.join(thisDir, "..", "..", DATABASE_NAME))
    dbInstance = SqliteDatabase(dbName, check_same_thread=False)
elif DATABASE_ENGINE == "mysql":
    dbInstance = MySQLDatabase(DATABASE_NAME, user=DATABASE_USERNAME, password=DATABASE_PASSWORD,
                         host=DATABASE_HOST, port=DATABASE_PORT)
elif DATABASE_ENGINE == "postgresql":
    dbInstance = PostgresqlDatabase(DATABASE_NAME, user=DATABASE_USERNAME, password=DATABASE_PASSWORD,
                         host=DATABASE_HOST, port=DATABASE_PORT)
elif DATABASE_ENGINE == "cockroachdb":
    dbInstance = CockroachDatabase(DATABASE_NAME, user=DATABASE_USERNAME, password=DATABASE_PASSWORD,
                         host=DATABASE_HOST, port=DATABASE_PORT)
else:
    raise Exception("database engine '{}' not supported yet".format(DATABASE_ENGINE))

#调用此函数正式连接到数据库（打开数据库）
def ConnectToDatabase():
    global dbInstance
    dbInstance.connect(reuse_if_open=True)

#关闭数据库连接
def CloseDatabase():
    global dbInstance
    if not dbInstance.is_closed():
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

    @classmethod
    def get_one(cls, *query):
        return cls.get_or_none(*query)

    #如果取不到，返回None
    @classmethod
    def get_by_id_or_none(cls, id_):
        try:
            return cls.get_by_id(int(id_))
        except:
            return None

    #返回Key/Id的字符串表达
    @property
    def key_or_id_string(self):
        return str(self.id)

    #将当前行数据转换为一个字典结构，由子类使用，将外键转换为ID，日期转换为字符串
    #可以传入 only=[Book.title, ...]，或 exclude=[]
    def to_dict(self, **kwargs):
        ret = model_to_dict(self, **kwargs)
        for key in ret:
            data = ret[key]
            if isinstance(data, datetime.datetime):
                ret[key] = data.strftime('%Y-%m-%d %H:%M:%S')
        return ret
