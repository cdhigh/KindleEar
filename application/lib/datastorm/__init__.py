#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#基于<https://github.com/JavierLuna/datastorm>修改为和peewee接口尽量一致
from .datastorm import DataStorm  # noqa: F401
__version__ = '0.0.0a9'

#目前支持的用法（支持的特性都和peewee保证一次）：
# from datastorm import DataStorm
# from datastorm.fields import *
# dbInstance = DataStorm(project=APP_ID)
# class User(dbInstance.DSEntity):
#     name = CharField()
#     passwd = CharField()
#     birthdate = DateTimeField()
#     score = IntegerField()

#--------- Create --------------
# User(name='python', passwd='3.0').save()
# User.create(name='python', passwd='3.0')
# User.insert_many([{'name':'python', 'passwd':'3.0'}, {'name':'cobra', 'passwd':'2.0'}])

#--------- Delete --------------
# user.delete_instance()
# User.delete().where(User.birthdate < datetime.datetime(2024,1,1)).execute()

#--------- Update --------------
# user.passwd = 'new password'
# user.save()

#-------- Retrieve -------------
#supported query operators: ==, !=, >, >=, <, <=, &, in_, not_in, order_by, limit
# user = User.select().where(User.name == 'python').get()
# user = User.select().where(User.name == 'python').first()
# user = User.select().where(User.name.in_(['python', 'cobra'])).first()
# user = User.select().where(User.name.not_in(['python', 'cobra'])).first()
# users = User.select(User.name, User.score).where(User.name == 'python').execute()
# users = User.select().where(User.birthdate.between(datetime.datetime(2024,1,1), datetime.datetime(2024,2,1)))).execute()
# user = User.select().where((User.name != 'python') & (User.name != 'cobra')).first()
# User.select().order_by(User.birthdate.desc(), User.score).limit(10).execute()

#------- transaction -----------
# with dbInstance.atomic():
#     User.insert_many([{'name':'python', 'passwd':'3.0'}, {'name':'cobra', 'passwd':'2.0'}])
