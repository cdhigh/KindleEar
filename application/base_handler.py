#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#主要针对网页显示之类的一些公共支持工具函数
#Author: cdhigh <https://github.com/cdhigh>
from typing import Union
from functools import wraps
from flask import request, redirect, session, url_for
from .back_end.db_models import *

#一些共同的工具函数，工具函数都是小写+下划线形式

#确认登录的装饰器
#forAjax:是否返回一个json字典
def login_required(forAjax=False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_url = request.url
            if (session.get('login', '') == 1) and get_login_user():
                return func(*args, **kwargs)
            elif forAjax:
                return redirect(url_for("bpLogin.NeedLoginAjax"))
            else:
                return redirect(url_for("bpLogin.Login", next=current_url))
        return wrapper
    return decorator

#查询当前登录用户名，在使用此函数前最好保证已经登录
#返回一个数据库行实例，而不是一个字符串
def get_login_user() -> Union[KeUser,None]:
    name = session.get('userName', '')
    return KeUser.get_or_none(KeUser.name == name) if name else None
    
#记录投递记录到数据库
def save_delivery_log(user: KeUser, book: str, size: int, status='ok', to: Union[str,list,None]=None):
    name = user.name
    to = to or user.cfg('kindle_email') #type: ignore
    if isinstance(to, list):
        to = ','.join(to)
    
    try:
        DeliverLog.create(user=name, to=to, size=size, time_str=user.local_time("%Y-%m-%d %H:%M"), 
            book=book, status=status)
    except Exception as e:
        default_log.warning('DeliverLog failed to save: {}'.format(e))
