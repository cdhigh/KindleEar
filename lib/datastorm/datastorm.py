#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#基于<https://github.com/JavierLuna/datastorm>修改为和peewee接口尽量一致
import os, math
from typing import List, TypeVar

from google.cloud import datastore
from google.cloud.datastore import Key

from .entity import BaseEntity, AbstractDSEntity
from .exceptions import BatchSizeLimitExceeded

T = TypeVar('T')

MAX_DATASTORE_BATCH_SIZE = 500

class DataStorm:
    def __init__(self, project=None, namespace=None, credentials=None, _http=None):
        self.project = project or os.getenv("DATASTORE_PROJECT_ID", None)
        self.credentials = credentials
        self.namespace = namespace
        self._http = _http

    #获取datastore的Client实例
    @property
    def client(self):
        return datastore.Client(project=self.project, namespace=self.namespace, credentials=self.credentials,
                                _http=self._http)

    #表示一个实体类，客户端每个实体继承这个类
    @property
    def DSEntity(self):
        return AbstractDSEntity("DSEntity", (BaseEntity,), {'__kind__': None, '_datastore_client': self.client})

    #保存多个实体到datastore
    def save_multi(self, entities: List[BaseEntity], batch_size: int = MAX_DATASTORE_BATCH_SIZE):
        if batch_size < 1:
            raise ValueError("Batch size must be greater than 0")
        if batch_size > self.MAX_DATASTORE_BATCH_SIZE:
            raise BatchSizeLimitExceeded(batch_size)

        for entity_batch in self.split_batches(entities, batch_size):
            self.client.put_multi([entity.get_datastore_entity() for entity in entity_batch])

    #根据参数获取或者产生datastore的Key实例
    #kind: 类似SQL里面的数据表名
    #identifier: 实体名字，如果不提供，datastore会生成一个id
    def generate_key(self, kind: str, identifier: str = "", parent_key: Key = None):
        if identifier:
            return self.client.key(kind, identifier, parent=parent_key)
        else:
            return self.client.key(kind, parent=parent_key)

    #将一个列表分成batch_size的若干个小列表
    def split_batches(self, entities: List[T], batch_size: int) -> List[List[T]]:
        return [entities[i:i + batch_size] for i in range(0, len(entities), batch_size)]
