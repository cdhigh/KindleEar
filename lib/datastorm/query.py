#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from typing import Union, List

from google.cloud import datastore
from google.cloud.datastore import Key

from .fields import BaseField
from .filter import Filter

class QueryBuilder:
    def __init__(self, entity_class, filters=None, order=None):
        self._entity_class = entity_class
        self._kind = entity_class.__kind__
        self._client = entity_class._datastore_client
        filters = filters or []
        self._filters = filters + entity_class.__base_filters__
        self._order = order or []
        self._limit = 0

    #修改为和peewee接口一致，原来为 filter()，改成 where()
    def where(self, *filters: Filter):
        self._filters += filters
        return self

    #增加此接口使用Key查询
    def get_by_key(self, key: Union[Key, str]):
        if not key:
            return None
        key = key if isinstance(key, Key) else self._entity_class.generate_key(key)
        self._filters.append(Filter("__key__", "=", key))
        return self.first()

    #修改为用法和peewee一样，order_by(Model.Field.desc())/order_by(Model.Field)
    def order_by(self, field: Union[BaseField, str]):
        order_field = field.field_name if isinstance(field, BaseField) else field
        self._order.append(order_field)
        return self

    def limit(self, limit: int):
        self._limit = limit

    #这个修饰函数是类似SQL的select函数里面的参数，只获取部分字段，可以考虑将这部分功能移到select函数
    def only(self, *args: List[str]):
        return ProjectedQueryBuilder(self._entity_class, filters=self._filters, order=self._order, projection=args)

    #修改此函数和peewee一致，返回一个元素: get(self, key: Union[Key, str]) -> def get(self)
    #def get(self, key: Union[Key, str]):
    #    if not isinstance(key, Key):
    #        key = self._client.key(self._kind, key)
    #    raw_entity = self._client.get(key)
    #    return None if raw_entity is None else self._make_entity_instance(raw_entity.key, raw_entity)
    get = first

    #select()之后需要调用此函数才提供数据
    def execute(self, page_size: int = 500, parent_key: Key = None):
        query = self._get_query(parent_key)
        query = self._build_query(query)

        cursor = None
        limit = self._limit
        batch_size = min(page_size, limit) if limit else page_size
        count = 0
        while True:
            last_yielded_entity = None
            query_iter = query.fetch(start_cursor=cursor, limit=batch_size)
            for raw_entity in query_iter: #逐个返回Python化的实体对象
                last_yielded_entity = self._make_entity_instance(raw_entity.key, raw_entity)
                yield last_yielded_entity
                cnt += 1
            cursor = query_iter.next_page_token
            #last_yielded_entity要用is None，避免实体类重载了__bool__()
            if not cursor or (last_yielded_entity is None) or (limit and (cnt >= limit)):
                break

    def _modify_filters(self, query):
        [query.add_filter(ft.item, ft.op, ft.value) for ft in self._filters]
        return query

    def _modify_order(self, query):
        if self._order:
            query.order = self._order
        return query

    def _get_query(self, parent_key: Key):
        query = self._client.query(kind=self._kind, ancestor=parent_key)
        return query

    def _build_query(self, query):
        query = self._modify_filters(query)
        query = self._modify_order(query)
        return query

    def first(self):
        result = None
        try:
            result = next(self.execute(page_size=1))
        except TypeError:  # pragma: no cover
            pass
        except StopIteration:  # pragma: no cover
            pass

        return result

    def __iter__(self):
        return iter(self.execute())

    def _make_entity_instance(self, key: Key, attr_data: dict):
        entity = self._entity_class(key)
        for datastore_field_name, serialized_data in attr_data.items():
            datastorm_field_name = entity._datastorm_mapper.resolve_datastore_alias(datastore_field_name)
            entity.set(datastorm_field_name,
                       entity._datastorm_mapper.get_field(datastorm_field_name).loads(serialized_data))
        return entity

    def __repr__(self):
        return "< QueryBuilder filters: {}, ordered by: {}>".format(self._filters or "No filters",
                                                                    self._order or "No order")  # pragma: no cover


class ProjectedQueryBuilder(QueryBuilder):
    def __init__(self, entity_class, filters=None, order=None, projection=None):
        super(ProjectedQueryBuilder, self).__init__(entity_class, filters=filters, order=order)
        self._projection = projection or []

    def only(self, *args: List[str]):
        self._projection += args
        return self

    def _make_entity_instance(self, key: Key, attr_data: dict):
        entity = datastore.Entity(key=key)
        entity.update(attr_data)
        return entity

    def _modify_projection(self, query):
        if self._projection:
            query.projection = self._projection
        return query

    def _build_query(self, query):
        query = super()._build_query(query)
        query = self._modify_projection(query)
        return query
