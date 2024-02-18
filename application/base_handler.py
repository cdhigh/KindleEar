#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#主要针对网页显示之类的一些公共支持工具函数

import os, datetime, hashlib, time, base64
from functools import wraps
from urllib.parse import urlparse
from flask import request, redirect, render_template, session, url_for
from .back_end.db_models import *
from .utils import local_time

#一些共同的工具函数，工具函数都是小写+下划线形式

#确认登录的装饰器
#forAjax:是否返回一个json字典
def login_required(forAjax=False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if ((session.get('login') == 1) and get_login_user()):
                return func(*args, **kwargs)
            else:
                return redirect(url_for("bpLogin.NeedLoginAjax") if forAjax else url_for("bpLogin.Login"))
        return wrapper
    return decorator

#查询当前登录用户名，在使用此函数前最好保证已经登录
#返回一个数据库行实例，而不是一个字符串
def get_login_user():
    return KeUser.get_or_none(KeUser.name == session.get('userName', ''))
    
#记录投递记录到数据库
def save_delivery_log(user, book, size, status='ok', to=None):
    global default_log
    name = user.name
    to = to or user.kindle_email
    tz = user.timezone
    if isinstance(to, list):
        to = ','.join(to)
    
    try:
        DeliverLog.create(user=name, to=to, size=size, time_str=local_time(tz=tz), 
           datetime=datetime.datetime.utcnow(), book=book, status=status)
    except Exception as e:
        default_log.warning('DeliverLog failed to save: {}'.format(e))
