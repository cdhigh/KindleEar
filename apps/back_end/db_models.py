#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#数据库结构定义，使用这个文件隔离sql和nosql的差异，尽量向外提供一致的接口
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Author:
# cdhigh <https://github.com/cdhigh>
#Contributors:
# rexdf <https://github.com/rexdf>

from config import DATABASE_ENGINE

if DATABASE_ENGINE == "datastore":
    from apps.back_end.db_models_nosql import *
else:
    from apps.back_end.db_models_sql import *
