#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#datastore 简易测试桩，也可以说是最简模拟器

import json, datetime, os, random, pickle
thisDir = os.path.dirname(os.path.abspath(__file__))
dbName = os.path.normpath(os.path.join(thisDir, '..', '..', 'fake_datastore.pkl'))

def SaveDbJson():
    with open(dbName, 'wb') as f:
        f.write(pickle.dumps(dbJson))

if os.path.exists(dbName):
    with open(dbName, 'rb') as f:
        dbJson = pickle.loads(f.read())
else:
    dbJson = {}

class DatastoreDatabase:
    def __init__(self, project):
        self.project = project

class datastore:
    entities = {}

    @property
    def client(self):
        return Client()

    @classmethod
    def Entity(cls, key):
        class _Entity:
            def __init__(self, key):
                self.key=str(key)
                self.data = None
                print(f'Created datastore entity: key={key}')
            def update(self, data):
                self.data = data
                print(f'Entity update: {data}')
        key = str(key)
        if key not in cls.entities:
            cls.entities[key] = _Entity(key)
        return cls.entities[key]

    class Client:
        cache_keys = set()
        def __init__(self, project, namespace, credentials, _http):
            self.project = project
            self.namespace = namespace
            self.credentials = credentials
            self._http = _http
        def key(self, name, identifier=None, parent=None):
            return Key(name, identifier, parent)
        def put(self, entity):
            dbJson[entity.key] = entity.data
            SaveDbJson()
            #print(f'client put: {entity.key}:{entity.data}')
        def put_multi(self, entities):
            for e in entities:
                dbJson[e.key] = e.data
            SaveDbJson()
        def delete(self, key):
            key = str(key)
            if key in dbJson:
                del dbJson[key]
            SaveDbJson()
        def delete_multi(self, keys):
            for key in keys:
                self.delete(key)
        def query(self, kind, ancestor=None):
            return DBQuery(kind)

        def transaction(self, **args):
            class Transaction:
                def __enter__(self):
                    print(f'Client transaction enter-->')
                def __exit__(self):
                    print(f'--< Client transaction exit')

class Key:
    def __init__(self, name, identifier=None, parent=None):
        self.name = name
        self.identifier = identifier or random.randint(1000, 9999)
        self.parent = parent
        #print(f'Generatde Key object: kind={name}, identifier={identifier}, parent={parent}')
    def to_legacy_urlsafe(self):
        return str(self).encode()
    def __str__(self):
        return f'{self.name}:{self.identifier}:KEY'
    @classmethod
    def from_legacy_urlsafe(cls, key):
        n, i, k = key.split(':')
        return Key(n, i)

class DBQuery:
    def __init__(self, kind, parent=None):
        self.kind = kind
        self.filters = []
        self.projection = []
        self.order = []
        self.distinct_on = None
    def add_filter(self, item, op, value):
        if op == '=':
            op = '=='
        elif op == 'IN':
            op = 'in'
        elif op == 'NOT_IN':
            op = 'not in'
        if isinstance(value, str):
            value = f'"{value}"'
        self.filters.append((item, op, value))
    def fetch(self, start_cursor=None, limit=None):
        results = []
        for key, data in dbJson.items():
            n, i, k = key.split(':')
            if n != self.kind: #key第一段是kind
                continue
            for item, op, value in self.filters:
                expr = f'data.get("{item}") {op} {value}'
                if item in data and not eval(expr):
                    break
            else:
                results.append((Key.from_legacy_urlsafe(key), data))
        if self.order:
            order = self.order[0]
            reverse = False
            if order.startswith('-'):
                order = order[1:]
                reverse = True
            results.sort(key=lambda x: x[1].get(order), reverse=reverse)
        return QueryResult(results)

class QueryResult:
    def __init__(self, results):
        self.results = results
        self.current_pos = 0
    def __iter__(self):
        for key, data in self.results:
            d = DotDict(data)
            d.key = key
            yield d
    @property
    def next_page_token(self):
        return None

#能使用点号访问的字典
class DotDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.key = None

    def __getattr__(self, key):
        try:
            return self[key]
        except:
            return None

    def __str__(self):
        return f'{self.key}: {self.items()}'