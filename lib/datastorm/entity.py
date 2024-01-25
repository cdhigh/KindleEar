#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#基于<https://github.com/JavierLuna/datastorm>修改为和peewee接口尽量一致
import inspect, re
from typing import Optional, Union, Any, List, Type

from google.cloud import datastore
from google.cloud.datastore import Key

from .fields import BaseField
from .filter import Filter
from .mapper import FieldMapper
from .query import QueryBuilder


class AbstractDSEntity(type):
    #原模块为@property query()，为了和peewee接口一致，修改为select()
    @classmethod
    def select(cls, *args):
        return QueryBuilder(cls)

    def __getattribute__(self, key):
        #if key in ['create', 'get', 'get_or_none', 'get_by_id']
        attr = super(AbstractDSEntity, self).__getattribute__(key)
        if isinstance(attr, BaseField) and attr.field_name is None:
            attr.field_name = key
        return attr

class BaseEntity:
    __kind__: str = None  # type: ignore #kind类似SQL里面的表名
    __base_filters__: List[Filter] = []

    _datastore_client = None

    #这里为了简单，key可以为空
    def __init__(self, key: Union[Key, str] = "", **kwargs):
        self.key = key if isinstance(key, Key) else self.generate_key(key)
        self._datastorm_mapper = self.__resolve_mappings()
        self.__set_defaults()

        [self.set(name, value) for name, value in kwargs.items()]
        self.set('id', self.key.to_legacy_urlsafe().decode()) #兼容peewee的一个属性

    #增加和peewee相同的接口 create()
    @classmethod
    def create(cls, **kwargs):
        inst = cls(**kwargs)
        inst.save()
        return inst

    #增加和peewee相同的接口 get()，不同的是这里获取不到数据也不抛出异常
    @classmethod
    def get(cls, **kwargs):
        return QueryBuilder(cls).where(**kwargs).first()

    #和peewee一致
    @classmethod
    def get_or_none(cls, **kwargs):
        return cls.get(**kwargs)

    @classmethod
    def get_by_key(cls, key: Union[Key, str]):
        return QueryBuilder(cls).get_by_key(key)

    #保存本实例到datastore
    def save(self):
        self._datastore_client.put(self.get_datastore_entity())

    def set(self, field_name: str, value: Any, field: Optional[BaseField] = None):
        if field:
            self._map_field(field_name, field)
        if field_name not in self._datastorm_mapper.fields:
            self._datastorm_mapper.set_field(field_name, self._datastorm_mapper.get_field(field_name))

        setattr(self, field_name, value)

    def _map_field(self, field_name: str, field: Union[BaseField, Type[BaseField]]):
        field_instance = field() if inspect.isclass(field) else field  # type: ignore
        self._datastorm_mapper.set_field(field_name, field_instance)  # type: ignore

    #从datastore拉取数据更新本实例
    def sync(self):
        buffer = self.get_datastore_entity()
        updated_instance = self._datastore_client.get(self.key)
        for field_name, datastore_value in updated_instance.items():
            if field_name not in buffer or buffer[field_name] != updated_instance[field_name]:
                self.set(field_name, datastore_value)

    #从datastore删除本实例，和peewee接口一致，注意不是 delete()，delete()是peewee里面的DELETE query
    def delete_instance(self):
        """Delete the object from Datastore."""
        self._datastore_client.delete(self.key)

    #获取datastore的Key
    #identifier: Key表示的实体名字，如果不提供则datastore会提供一个id
    @classmethod
    def generate_key(cls, identifier: str = None, parent_key: Optional[Key] = None):
        if identifier:
            return cls._datastore_client.key(cls.__kind__, identifier, parent=parent_key)  # type: ignore
        else:
            return cls._datastore_client.key(cls.__kind__, parent=parent_key)  # type: ignore

    #生成Datastore的Entity
    def get_datastore_entity(self):
        entity = datastore.Entity(key=self.key)
        data = self.to_python_dict()
        data.pop('key', None)
        entity.update(entity_dict) #这里update只是内存数据，还没有提交
        return entity

    #生成一个字典
    #可以传入 only=[Book.title, ...]，或 exclude=[]
    def to_python_dict(self, **kwargs):
        only = [x.field_name for x in kwargs.get('only', [])]
        exclude = [x.field_name for x in kwargs.get('exclude', [])]
        should_skip = lambda n: (n in exclude) or (only and (n not in only))

        data = {}
        #if not should_skip('key'):
        #    data['key'] = self.key.to_legacy_urlsafe().decode();
        
        for field_name in self._datastorm_mapper.fields:
            field = self._datastorm_mapper.get_field(field_name)
            if should_skip(field_name):
                continue
            #如果定义Field时没有指定field_name，则field.field_name == field_name
            data[field.field_name or field_name] = field.dumps(getattr(self, field_name))

        return data

    def __resolve_mappings(self) -> FieldMapper:
        field_mapper = FieldMapper()
        for attribute_name in dir(self):
            attribute = getattr(self, attribute_name)
            if inspect.isclass(attribute) and issubclass(attribute, BaseField):
                attribute = attribute() #每个字段都创建一个实例，而不是使用一个类，这样就不会相互干扰
            if isinstance(attribute, BaseField):
                field_mapper.set_field(attribute_name, attribute)
        return field_mapper

    def __set_defaults(self):
        for field_name in self._datastorm_mapper.fields:
            self.set(field_name, self._datastorm_mapper.default(field_name))

    def __repr__(self):
        return "< {name} >".format(name=self.__kind__)  # pragma: no cover
