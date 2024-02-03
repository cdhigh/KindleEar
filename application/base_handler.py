#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#主要针对网页显示之类的一些公共支持工具函数

import os, datetime, hashlib, time, base64
from functools import wraps
from urllib.parse import urlparse
from flask import request, redirect, render_template, session, url_for
from .back_end.db_models import *
from .utils import local_time
from config import TIMEZONE

#一些共同的工具函数，工具函数都是小写+下划线形式

#确认登录的装饰器
#如果提供userName，则要求登录的用户名=userName
#forAjax:是返回一个json字典
def login_required(userName=None, forAjax=False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if ((session.get('login') == 1) and (not userName or (userName == session.get('userName')))
                and get_login_user()):
                return func(*args, **kwargs)
            else:
                return redirect(url_for("bpLogin.NeedLoginAjax") if forAjax else url_for("bpLogin.Login"))
        return wrapper
    return decorator

#查询当前登录用户名，在使用此函数前最好保证已经登录
#返回一个数据库行实例，而不是一个字符串
def get_login_user():
    return KeUser.get_one(KeUser.name == session.get('userName', ''))
    
#记录投递记录到数据库
def save_delivery_log(name, to, book, size, status='ok', tz=TIMEZONE):
    global default_log
    to = '; '.join(to) if isinstance(to, (list, tuple)) else to
    
    try:
        dl = DeliverLog(username=name, to=to, size=size,
           time=local_time(tz=tz), datetime=datetime.datetime.utcnow(),
           book=book, status=status)
        dl.save()
    except Exception as e:
        default_log.warning('DeliverLog failed to save: {}'.format(e))
