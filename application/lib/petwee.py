#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Petwee is an ORM/ODM module for Google Datastore, maintaining compatibility with the Peewee interface.
#Author: cdhigh <http://github.com/cdhigh>
#if datastore emulator doesnot effect, you can change:
#python/Lib/site-packages/google/cloud/datastore/client.py/class Client.__init__()
# replace host = os.environ[GCD_HOST] to 
#         host = 'localhost:8081'

#==================================================
import copy, datetime
#from google.cloud import datastore
#from google.cloud.datastore import Key
from fake_datastore import *

class DoesNotExist(Exception):
    pass

class Database(object):
    def bind(self, models):
        for model in models:
            model.bind(self)

class DatastoreDatabase(Database):
    def __init__(self, project=None, namespace=None, credentials=None, _http=None):
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT", None)
        self.credentials = credentials
        self.namespace = namespace
        self._http = _http

    @property
    def client(self):
        return datastore.Client(project=self.project, namespace=self.namespace, credentials=self.credentials, _http=self._http)

    #事务支持
    def atomic(self, **kwargs):
        return self.client.transaction(**kwargs)

    def transaction(self, **kwargs):
        return self.client.transaction(**kwargs)

    def generate_key(self, kind, identifier="", parent_key=None):
        if identifier:
            return self.client.key(kind, identifier, parent=parent_key)
        else:
            return self.client.key(kind, parent=parent_key)

class FieldDescriptor(object):
    def __init__(self, field):
        self.field_inst = field
        self.field_name = field.name

    def __get__(self, instance, instance_type=None):
        if instance:
            return instance._data.get(self.field_name)
        return self.field_inst

    def __set__(self, instance, value):
        instance._data[self.field_name] = value

class BaseModel(type):
    inheritable_options = ['database', 'order_by', 'useIDInsteadOfKey']

    def __new__(cls, name, bases, attrs):
        if not bases:
            return super(BaseModel, cls).__new__(cls, name, bases, attrs)

        meta_options = {}
        meta = attrs.pop('Meta', None)
        if meta:
            meta_options.update((k, v) for k, v in meta.__dict__.items() if not k.startswith('_'))

        for b in bases:
            base_meta = getattr(b, '_meta', None)
            if not base_meta:
                continue
            
            for (k, v) in base_meta.__dict__.items():
                if k in cls.inheritable_options and k not in meta_options:
                    meta_options[k] = v

            for (k, v) in b.__dict__.items():
                if isinstance(v, FieldDescriptor) and k not in attrs:
                    attrs[k] = copy.deepcopy(v.field_inst)

        meta_options.setdefault('database', None)
        meta_options.setdefault('useIDInsteadOfKey', False)
        
        if meta_options['useIDInsteadOfKey']:
            attrs['id'] = PrimaryKeyField()

        # initialize the new class and set the magic attributes
        cls = super(BaseModel, cls).__new__(cls, name, bases, attrs)
        cls._meta = ModelOptions(cls, **meta_options)
        cls._data = None

        # replace the fields with field descriptors, calling the add_to_class hook
        for name, attr in cls.__dict__.items():
            if isinstance(attr, Field):
                attr.add_to_class(cls, name)
        
        cls._meta.prepared()
        return cls

class ModelOptions(object):
    def __init__(self, cls, database=None, order_by=None, useIDInsteadOfKey=False, **kwargs):
        self.model_class = cls
        self.name = cls.__name__
        self.fields = {}
        self.defaults = {}
        self.database = database
        self.order_by = order_by
        self.useIDInsteadOfKey = useIDInsteadOfKey
        
    def prepared(self):
        for field in self.fields.values():
            if field.default is not None:
                self.defaults[field] = field.default

    def get_default_dict(self):
        return self.defaults


class Field(object):
    def __init__(self, default=None, enforce_type=False, **kwargs):
        self.default = default if callable(default) else lambda: default
        self.enforce_type = enforce_type
    
    def __eq__(self, other):
        return other.__class__ == self.__class__ and self.id and other.id == self.id

    def __hash__(self):
        return hash((self.model.__name__, self.name))
    def check_type(self, value):
        return True

    def add_to_class(self, klass, name):
        self.name = name
        self.model = klass
        klass._meta.fields[name] = self
        setattr(klass, name, FieldDescriptor(self))

    def db_value(self, value):
        if value is None:
            return None
        return value

    @classmethod
    def python_value(self, value):
        return value

    def __eq__(self, other):
        return self._generate_filter("=", other)
    def __ne__(self, other):
        return self._generate_filter("!=", other)
    def __lt__(self, other):
        return self._generate_filter("<", other)
    def __gt__(self, other):
        return self._generate_filter(">", other)
    def __le__(self, other):
        return self._generate_filter("<=", other)
    def __ge__(self, other):
        return self._generate_filter(">=", other)
    def in_(self, other):
        assert(isinstance(other, list))
        return self._generate_filter("IN", other)
    def not_in(self, other):
        assert(isinstance(other, list))
        return self._generate_filter("NOT_IN", other)

    def between(self, other1, other2):
        if other1 <= other2:
            return [self._generate_filter(">", other1), self._generate_filter("<", other2)]
        else:
            return [self._generate_filter("<", other1), self._generate_filter(">", other2)]

    def _generate_filter(self, op, other):
        if self.enforce_type and not self.check_type(other):
            raise ValueError("Comparing field {} with '{}' of type {}".format(self.__class__.__name__, other, type(other)))
        return Filter(self.name, op, other)

    #用来排序的，如果是升序，asc()可以省略
    def asc(self):
        return self.name
        
    def desc(self):
        return '-{}'.format(self.name)

class PrimaryKeyField(Field):
    def _generate_filter(self, op, other):
        if not isinstance(other, Key):
            raise ValueError("Comparing field {} with '{}' of type {}".format(self.__class__.__name__, other, type(other)))
        return Filter("__key__", op, other)

class AnyField(Field):
    pass

BlobField = AnyField

class BooleanField(Field):
    pass

class IntegerField(Field):
    pass

class FloatField(Field):
    pass

class DoubleField(Field):
    pass

class DecimalField(Field):
    pass

class BigIntegerField(Field):
    pass

class CharField(Field):
    pass

TextField = CharField

class DateTimeField(Field):
    def check_type(self, value):
        return isinstance(value, datetime.datetime)

class DateField(Field):
    pass

class TimeField(Field):
    pass

class JSONField(Field):
    def check_type(self, value):
        json_types = [bool, int, float, str, list, dict]
        return any(isinstance(value, json_type) for json_type in json_types)

    @classmethod
    def list_default(cls):
        return []
        
    @classmethod
    def dict_default(cls):
        return {}


class Model(object, metaclass=BaseModel):
    def __init__(self, key=None, *args, **kwargs):
        self.key = key if isinstance(key, Key) else self.generate_key(key)
        self._data = dict((f.name, v()) for f, v in self._meta.defaults.items())
        for key, value in kwargs.items():
            setattr(self, key, value)
        
    @classmethod
    def bind(cls, database):
        cls._meta.database = database
        
    @property
    def client(self):
        return self._meta.database.client

    def atomic(self, **kwargs):
        return self.client.transaction(**kwargs)

    @classmethod
    def select(cls, *args):
        return QueryBuilder(cls, *args)

    @classmethod
    def delete(cls):
        return DeleteQueryBuilder(cls)

    @classmethod
    def create(cls, **kwargs):
        inst = cls(**kwargs)
        inst.save()
        return inst

    @classmethod
    def insert_many(cls, entities, batch_size=500):
        batch_size = min(max(batch_size, 1), 500)
        put_multi = cls._meta.database.client.put_multi
        for batch in self.split_batches(entities, batch_size):
            put_multi([cls(**data).get_datastore_entity() for data in batch])

    #将一个列表分成batch_size的若干个小列表
    def split_batches(self, entities, batch_size):
        return [entities[i:i + batch_size] for i in range(0, len(entities), batch_size)]

    @classmethod
    def get(cls, query=None):
        sq = cls.select()
        if query:
            sq = sq.where(query)
        return sq.get()

    @classmethod
    def get_or_none(cls, query=None):
        try:
            return cls.get(query)
        except DoesNotExist:
            pass

    @classmethod
    def get_by_key(cls, key):
        return cls.select().filter_by_key(key).first()

    #compatiable to sql, but this id is not an integer, it's a string
    @classmethod
    def get_by_id(cls, sid):
        return cls.select().filter_by_key(sid).first()

    def save(self, **kwargs):
        self.client.put(self.get_datastore_entity())

    def delete_instance(self, **kwargs):
        self.client.delete(self.key)

    #生成Datastore的Entity
    def get_datastore_entity(self):
        entity = datastore.Entity(key=self.key)
        data = self.to_python_dict()
        data.pop('key', None)
        data.pop('id', None)
        entity.update(data) #这里update只是内存数据，还没有提交
        return entity

    #获取datastore的Key
    #identifier: Key表示的实体名字，如果不提供则datastore会提供一个id
    @classmethod
    def generate_key(cls, identifier=None, parent_key=None):
        if identifier:
            return cls._meta.database.client.key(cls.__name__, identifier, parent=parent_key)  # type: ignore
        else:
            return cls._meta.database.client.key(cls.__name__, parent=parent_key)  # type: ignore

    #生成一个字典
    #可以传入 only=[Book.title, ...]，或 exclude=[]
    def to_python_dict(self, **kwargs):
        only = [x.name for x in kwargs.get('only', [])]
        exclude = [x.name for x in kwargs.get('exclude', [])]
        should_skip = lambda n: (n in exclude) or (only and (n not in only))

        data = {}
        for name, field in self._meta.fields.items():
            if not should_skip(name):
                data[name] = getattr(self, name, None)
        #print(f'{self.__class__.__name__}.to_python_dict: {data}')
        return data


class Filter:
    def __init__(self, item, op, value):
        self.item = item
        self.op = op
        self.value = value

    def __repr__(self):
        return "<Filter: {} {} {}>".format(self.item, self.op, self.value)
    
    def __and__(self, rhs):
        assert(isinstance(rhs, Filter))
        return [self, rhs]


class QueryBuilder:
    def __init__(self, model_class, *args):
        self._model_class = model_class
        self._kind = model_class._meta.name
        self._client = model_class._meta.database.client
        self.useIDInsteadOfKey = model_class._meta.useIDInsteadOfKey
        self._filters = []
        self._projection = [(field.name if isinstance(field, Field) else field) for field in args]
        self._order = []
        self._distinct = []
        self._limit = 0

    def where(self, *filters):
        for flt in filters:
            if isinstance(flt, list):
                self._filters.extend(flt)
            else:
                self._filters.append(flt)
        return self

    def filter_by_key(self, key):
        if key:
            key = key if isinstance(key, Key) else Key.from_legacy_urlsafe(key)
            self._filters.append(Filter("__key__", "=", key))
        return self

    def order_by(self, *fields):
        order_fields = [(field.name if isinstance(field, Field) else field) for field in fields]
        self._order.extend(order_fields)
        return self

    def limit(self, limit: int):
        self._limit = limit

    def distinct_on(self, field):
        distinct_field = field.name if isinstance(field, Field) else field
        self._distinct.append(distinct_field)

    def execute(self, page_size=500, parent_key=None):
        query = self._get_query(parent_key)
        query = self._build_query(query)

        cursor = None
        limit = self._limit
        batch_size = min(page_size, limit) if limit else page_size
        count = 0
        while True:
            last_entity = None
            result = query.fetch(start_cursor=cursor, limit=batch_size)

            for raw in result:
                last_entity = self._make_instance(raw.key, raw)
                yield last_entity
                count += 1
            cursor = result.next_page_token
            if not cursor or (last_entity is None) or (limit and (count >= limit)):
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

    #make Model instance from database data
    def _make_instance(self, key, attr_data):
        inst = self._model_class(key)
        fields = inst._meta.fields
        for field_name, value in attr_data.items():
            if field_name in fields:
                setattr(inst, field_name, fields[field_name].python_value(value))
            else:
                setattr(inst, field_name, value)
        if inst._meta.useIDInsteadOfKey:
            inst.id = key.to_legacy_urlsafe().decode()
        return inst

    def __repr__(self):
        return "<QueryBuilder filters: {}, ordered by: {}>".format(self._filters or "No filters",
                                                                    self._order or "No order")  # pragma: no cover

class DeleteQueryBuilder(QueryBuilder):
    #select()之后需要调用此函数才开始删除数据
    def execute(self):
        keys = [e.key for e in super().execute()]
        if keys:
            self._client.delete_multi(keys)

    def __repr__(self):
        return "< DeleteQueryBuilder filters: {} >".format(self._filters or "No filters")  # pragma: no cover

