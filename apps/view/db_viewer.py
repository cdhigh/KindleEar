#!/usr/bin/env python
# -*- coding:utf-8 -*-
#查看当前数据库内容

from bottle import route
from apps.base_handler import *
from apps.db_models import *

@route("/dbviewer")
def DbViewer():
    login_required(ADMIN_NAME)
    return render_page('dbviewer.html', "DbViewer",
        books=Book.all(), users=KeUser.all(), feeds=Feed.all().order('book'))
