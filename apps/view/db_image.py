#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#读取数据库中的图像数据

from apps.BaseHandler import BaseHandler
from apps.utils import etagged
from bottle import route, error

#读取数据库中的图像数据，如果为dbimage/cover则返回当前用户的封面图片
@route("/dbimage/<id_>")
def DbImage(id_):
    if id_ != 'cover':
        return ''
    
    user = get_current_user() 
    if user.cover:
        response.content_type = "image/jpeg"
        return user.cover
    else:
        return "not cover"

