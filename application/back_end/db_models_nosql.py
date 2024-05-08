#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#datastore/mongodb数据库结构定义，使用自己写的兼容peewee接口的ODM库weedata管理
#cloud datastore 文档 <https://cloud.google.com/datastore/docs/concepts/queries>
#Author: cdhigh <https://github.com/cdhigh>
import os, datetime
from weedata import *

dbUrl = os.getenv('DATABASE_URL', '')
appId = os.getenv('APP_ID', '')

if dbUrl.startswith('mongodb://'):
    dbInstance = MongoDbClient(appId, dbUrl)
elif dbUrl.startswith('redis://'):
    dbInstance = RedisDbClient(appId, dbUrl)
elif dbUrl.startswith("datastore"):
    dbInstance = DatastoreClient(project=appId)
elif dbUrl.startswith("pickle://"):
    fileName = dbUrl[10:]
    if not fileName.startswith('/'):
        dbUrl = 'pickle:///{}'.format(os.path.join(appDir, fileName))
    dbInstance = PickleDbClient(dbUrl)
else:
    raise ValueError("database engine '{}' not supported yet".format(dbUrl.split(":", 1)[0]))

#调用此函数正式连接到数据库（打开数据库）
def connect_database():
    pass

#关闭数据库连接
def close_database():
    pass

#数据表的共同基类
class MyBaseModel(Model):
    class Meta:
        client = dbInstance
    
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
            return cls.get_by_key(id_)
        except:
            return None

    #将当前行数据转换为一个字典结构，由子类使用，将外键转换为ID，日期转换为字符串
    #可以传入 only=[Book.title, ...]，或 exclude=[]
    def to_dict(self, **kwargs) -> dict:
        ret = self.dicts(**kwargs)
        ret.pop('key', None)
        ret.pop('_id', None)
        for key in ret:
            data = ret[key]
            if isinstance(data, datetime.datetime):
                ret[key] = data.strftime('%Y-%m-%d %H:%M:%S')
        return ret
        