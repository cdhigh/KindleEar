#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from typing import Union, List

from google.cloud import datastore
from google.cloud.datastore import Key

from .fields import BaseField
from .filter import Filter

class QueryBuilder:
    def __init__(self, entity_class, *args):
        self._entity_class = entity_class
        self._kind = entity_class.__name__
        self._client = entity_class._datastore_client
        self._filters = entity_class.__base_filters__
        self._projection = [(field.field_name if isinstance(field, BaseField) else field) for field in args]
        self._order = []
        self._distinct = []
        self._limit = 0

    #修改为和peewee接口一致
    def where(self, *filters: Filter):
        for flt in filters:
            if isinstance(flt, list):
                self._filters.extent(flt)
            else:
                self._filters.append(flt)
        return self

    #增加此接口使用Key查询
    def get_by_key(self, key: Union[Key, str]):
        if not key:
            return None
        key = key if isinstance(key, Key) else self._entity_class.generate_key(key)
        self._filters.append(Filter("__key__", "=", key))
        return self.first()

    #修改为用法和peewee一样，order_by(Model.Field.desc())/order_by(Model.field1, Model.field2)
    #如果where()使用了不等式查询，则order_by()的第一项必须是第一个不等式查询的field
    def order_by(self, *fields):
        order_fields = [(field.field_name if isinstance(field, BaseField) else field) for field in fields]
        self._order.extend(order_fields)
        return self

    def limit(self, limit: int):
        self._limit = limit

    def distinct_on(self, field: Union[BaseField, str]):
        distinct_field = field.field_name if isinstance(field, BaseField) else field
        self._distinct.append(distinct_field)

    #这个修饰函数是类似SQL的select函数里面的参数，只获取部分字段，可以考虑将这部分功能移到select函数
    def only(self, *args: List[str]):
        return ProjectedQueryBuilder(self._entity_class, filters=self._filters, order=self._order, projection=args)

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

    def _modify_projection(self, query):
        if self._projection:
            query.projection = self._projection
        return query

    def _modify_order(self, query):
        if self._order:
            query.order = self._order
        return query

    def _modify_distinct(self, query):
        if self._distinct:
            query.distinct_on = self._distinct
        return query

    def _get_query(self, parent_key: Key):
        query = self._client.query(kind=self._kind, ancestor=parent_key)
        return query

    def _build_query(self, query):
        query = self._modify_filters(query)
        query = self._modify_projection(query)
        query = self._modify_order(query)
        query = self._modify_distinct(query)
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

    get = first

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

class DeleteQueryBuilder(QueryBuilder):
    #select()之后需要调用此函数才开始删除数据
    def execute(self):
        keys = [e.key for e in super().execute()]
        if keys:
            self._client.delete_multi(keys)

    def __repr__(self):
        return "< DeleteQueryBuilder filters: {} >".format(self._filters or "No filters")  # pragma: no cover
