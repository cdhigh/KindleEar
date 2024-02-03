#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Petwee is an ORM/ODM module for Google Datastore/MongoDB, featuring a compatible interface with Peewee.
#Author: cdhigh <http://github.com/cdhigh>
#==================================================
import copy, datetime

try:
    from google.cloud import datastore
    from google.cloud.datastore import Key
except ImportError:
    datastore = None    

try:
    import pymongo
    from bson.objectid import ObjectId
except ImportError:
    pymongo = None

from fake_datastore import *

__version__ = '0.0.1'

class DoesNotExist(Exception):
    pass

class NosqlClient(object):
    def bind(self, models):
        for model in models:
            model.bind(self)
    @classmethod
    def op_map(cls, op):
        return op
    def ensure_key(self, key, kind=None):
        return key


class DatastoreClient(NosqlClient):
    def __init__(self, project=None, namespace=None, credentials=None, _http=None):
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT", None)
        self.credentials = credentials
        self.namespace = namespace
        self._http = _http
        self._client = datastore.Client(project=self.project, namespace=self.namespace, credentials=self.credentials, _http=self._http)
    
    @classmethod
    def primary_key_str(cls):
        return "__key__"

    @classmethod
    def make_safe_id(cls, key, attr_data):
        return key.to_legacy_urlsafe().decode()

    @classmethod
    def make_orig_id(cls, key, attr_data):
        return key.id
        
    def insert_one(self, model):
        self._client.put(self.create_entity(model))

    def insert_many(self, models):
        for batch in self.split_batches(models, 500):
            self._client.put_multi([self.create_entity(data) for data in batch])

    update_one = insert_one
    update_many = insert_many
    
    def delete_one(self, model):
        if model.key:
            self._client.delete(model.key)

    def delete_many(self, models):
        keys = [e.key for e in models if e.key]
        if keys:
            self._client.delete_multi(keys)

    def execute(self, queryObj, page_size=500, parent_key=None):
        model_class = queryObj._model_class
        kind = _model_class._meta.name
        query = self.get_query(kind, parent_key)
        self.apply_query_condition(queryObj, query)

        cursor = None
        limit = queryObj._limit
        batch_size = min(page_size, limit) if limit else page_size
        count = 0
        while True:
            last_entity = None
            result = query.fetch(start_cursor=cursor, limit=batch_size)

            for raw in result:
                last_entity = self.make_instance(model_class, raw)
                yield last_entity
                count += 1
            cursor = result.next_page_token
            if not cursor or (last_entity is None) or (limit and (count >= limit)):
                break

    #make Model instance from database data
    def make_instance(self, model_class, raw):
        key = raw.key
        inst = model_class(key)
        fields = inst._meta.fields
        for field_name, value in raw.items():
            if field_name in fields:
                setattr(inst, field_name, fields[field_name].python_value(value))
            else:
                setattr(inst, field_name, value)
        inst.key = key
        if inst._meta.useIDInsteadOfKey:
            inst.id = key.to_legacy_urlsafe().decode()
        else:
            inst.id = key.id
        return inst

    def get_query(self, kind, parent_key=None):
        return self._client.query(kind=kind, ancestor=parent_key)

    def apply_query_condition(self, queryObj, query):
        [query.add_filter(ft.item, ft.op, ft.value) for ft in queryObj._filters]
        if queryObj._projection:
            query.projection = queryObj._projection
        if queryObj._order:
            query.order = queryObj._order
        if queryObj._distinct:
            query.distinct_on = queryObj._distinct
        return query

    #split a large list into some small list
    def split_batches(self, entities, batch_size):
        return [entities[i:i + batch_size] for i in range(0, len(entities), batch_size)]

    #create datastore entity instance
    def create_entity(self, model):
        if not model.key:
            model.key = self.generate_key(model._meta.name)
        entity = datastore.Entity(key=model.key)
        data = model.to_python_dict(remove_id=True)
        entity.update(data)
        return entity

    def atomic(self, **kwargs):
        return self._client.transaction(**kwargs)

    def transaction(self, **kwargs):
        return self._client.transaction(**kwargs)

    def generate_key(self, kind, identifier=None, parent_key=None):
        if identifier:
            return self._client.key(kind, identifier, parent=parent_key)
        else:
            return self._client.key(kind, parent=parent_key)

    def ensure_key(self, key, kind=None):
        if isinstance(key, Key):
            return key
        elif kind and (isinstance(key, int) or key.isdigit()):
            return self.generate_key(kind, int(key))
        else:
            return Key.from_legacy_urlsafe(key)

class MongoDbClient(NosqlClient):
    def __init__(self, project, host=None, port=None, username=None, password=None):
        self.project = project
        self.host = host or 'localhost'
        self.port = port or 27017
        if self.host.startswith('mongodb://'):
            self._client = pymongo.MongoClient(self.host)
        else:
            self._client = pymongo.MongoClient(host=self.host, port=self.port, username=username, password=password)
        self._db = self._client[project]
    
    @classmethod
    def primary_key_str(cls):
        return "_id"

    @classmethod
    def op_map(cls, op):
        return {'=': '=', '!=': '$ne', '<': '$lt', '>': '$gt', '<=': '$lte',
            '>=': '$gte', 'IN': '$in', 'NOT_IN': '$nin'}.get(op, op)

    @classmethod
    def make_safe_id(cls, key, attr_data):
        return key.to_legacy_urlsafe().decode()

    @classmethod
    def make_orig_id(cls, key, attr_data):
        return key.id
        
    def insert_one(self, model):
        self._db[model._meta.name].insert_one(model.to_python_dict(remove_id=True))

    def insert_many(self, models):
        self._db[model._meta.name].insert_many([model.to_python_dict(remove_id=True) for model in models])
        
    def update_one(self, model):
        if getattr(model, '_id', None):
            self._db[model._meta.name].update({'_id': model._id}, {'$set', model.to_python_dict(remove_id=True)})
        else:
            self.insert_one(model)
     
    def update_many(self, models):
        for model in models:
            self.update_one(model)

    def delete_one(self, model):
        if model._id:
            self._db[model._meta.name].delete_one({'_id': model._id})

    def delete_many(self, models):
        for model in models:
            self.delete_one(model)
        
    def execute(self, queryObj, page_size=500, parent_key=None):
        model_class = queryObj._model_class
        collection = self._db[model_class._meta.name]
        query = self.create_query_dict(queryObj._filters)
        sort = [(item[1:], pymongo.DESCENDING) if item.startswith('-') else (item, pymongo.ASCENDING) for item in queryObj._order]
        
        query_iter = collection.find(query)
        if sort:
            query_iter = query_iter.sort(sort)
        if queryObj._limit:
            query_iter = query_iter.limit(queryObj._limit)
        for item in query_iter:
            yield self.make_instance(model_class, item)

    def create_query_dict(self, filters):
        query = {}
        for ft in filters:
            query[ft.item] = ft.value if (ft.op == '=') else {ft.op: ft.value}
        return query

    #make Model instance from database data
    def make_instance(self, model_class, raw):
        inst = model_class()
        fields = inst._meta.fields
        for field_name, value in raw.items():
            if field_name in fields:
                setattr(inst, field_name, fields[field_name].python_value(value))
            else:
                setattr(inst, field_name, value)
        if inst._meta.useIDInsteadOfKey:
            inst.id = inst._id
        
        return inst

    def atomic(self, **kwargs):
        return self._client.start_session(**kwargs)

    def transaction(self, **kwargs):
        return self._client.start_session(**kwargs)

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
    inheritable_options = ['client', 'order_by', 'useIDInsteadOfKey']

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

        meta_options.setdefault('client', None)
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
    def __init__(self, cls, client=None, order_by=None, useIDInsteadOfKey=False, **kwargs):
        self.model_class = cls
        self.name = cls.__name__
        self.fields = {}
        self.defaults = {}
        self.client = client
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
        self.op_map = lambda x: x
    
    def __eq__(self, other):
        return (other.__class__ == self.__class__ and getattr(self, 'id', None) and 
            getattr(other, 'id', None) == getattr(self, 'id', None))

    def __hash__(self):
        return hash((self.model.__name__, self.name))

    def check_type(self, value):
        return True

    def add_to_class(self, klass, name):
        self.name = name
        self.model = klass
        self.op_map = klass._meta.client.op_map if klass._meta.client else lambda x: x
        klass._meta.fields[name] = self
        setattr(klass, name, FieldDescriptor(self))

    def db_value(self, value):
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
            return [self._generate_filter(">=", other1), self._generate_filter("<", other2)]
        else:
            return [self._generate_filter("<", other1), self._generate_filter(">=", other2)]

    def _generate_filter(self, op, other):
        if self.enforce_type and not self.check_type(other):
            raise ValueError("Comparing field {} with '{}' of type {}".format(self.__class__.__name__, other, type(other)))
        return Filter(self.name, self.op_map(op), other)

    #用来排序的，如果是升序，asc()可以省略
    def asc(self):
        return self.name
        
    def desc(self):
        return '-{}'.format(self.name)

class PrimaryKeyField(Field):
    def _generate_filter(self, op, other):
        if not isinstance(other, Key):
            raise ValueError("Comparing field {} with '{}' of type {}".format(self.__class__.__name__, other, type(other)))
        return Filter(self.model._meta.client.primary_key_str(), self.op_map(op), other)

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
    def __init__(self, *args, **kwargs):
        self.key = kwargs.get('key', None)
        self._data = dict((f.name, v()) for f, v in self._meta.defaults.items())
        for key, value in kwargs.items():
            setattr(self, key, value)
        
    @classmethod
    def bind(cls, client):
        cls._meta.client = client
        for f in cls._meta.fields:
            f.op_map = client.op_map
        
    @property
    def client(self):
        return self._meta.client

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
        self.client.insert_many(entities, batch_size)
        
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
            return None

    @classmethod
    def get_by_key(cls, key):
        return cls.select().filter_by_key(key).first()

    @classmethod
    def get_by_id(cls, sid):
        return cls.select().filter_by_id(sid).first()
        
    def save(self, **kwargs):
        self.client.update_one(self)

    def delete_instance(self, **kwargs):
        self.client.delete_one(self)

    #Convert model into a dict
    #: params only=[Model.title, ...]
    #: params exclude=[Model.title, ...]
    #: remove_id remove key and id field from dict
    def to_python_dict(self, **kwargs):
        only = [x.name for x in kwargs.get('only', [])]
        exclude = [x.name for x in kwargs.get('exclude', [])]
        should_skip = lambda n: (n in exclude) or (only and (n not in only))

        data = {}
        for name, field in self._meta.fields.items():
            if not should_skip(name):
                data[name] = getattr(self, name, None)

        if kwargs.get('remove_id'):
            data.pop('key', None)
            data.pop('id', None)
            data.pop('_id', None)
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
        _meta = model_class._meta
        self._kind = _meta.name
        self._client = _meta.client
        self.useIDInsteadOfKey = _meta.useIDInsteadOfKey
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
            key = self._client.ensure_key(key, self._kind)
            self._filters.append(Filter(self._client.primary_key_str(), self._client.op_map("="), key))
        return self

    def filter_by_id(self, id_):
        if id_:
            key = self._client.ensure_key(id_, self._kind)
            self._filters.append(Filter(self._client.primary_key_str(), self._client.op_map("="), key))
        return self

    def order_by(self, *fields):
        self._order.extend([(field.name if isinstance(field, Field) else field) for field in fields])
        return self

    def limit(self, limit: int):
        self._limit = limit
        return self

    def distinct_on(self, field):
        distinct_field = field.name if isinstance(field, Field) else field
        self._distinct = [distinct_field]
        return self

    def execute(self, page_size=500, parent_key=None):
        return self._client.execute(self, page_size=page_size, parent_key=parent_key)
        
    def first(self):
        result = None
        try:
            result = next(self.execute(page_size=1))
        except TypeError:
            pass
        except StopIteration:
            pass
        return result

    get = first

    def __iter__(self):
        return iter(self.execute())

    def __repr__(self):
        return f"<QueryBuilder filters: {self._filters}, ordered by: {self._order}>"

class DeleteQueryBuilder(QueryBuilder):
    def execute(self):
        self._client.delete_many([e for e in super().execute()])

    def __repr__(self):
        return f"<DeleteQueryBuilder filters: {self._filters}>"

