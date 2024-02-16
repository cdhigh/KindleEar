#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#网友共享的订阅源数据
import datetime, json, hashlib
from operator import attrgetter
from flask import Blueprint, render_template, request, Response
from flask_babel import gettext as _
from ..base_handler import *
from ..utils import str_to_bool
from ..back_end.db_models import *

#几个"官方"服务的地址
KINDLEEAR_SITE = "https://kindleear.appspot.com"
LIBRARY_KINDLEEAR = "/kindleearappspotlibrary"
LIBRARY_GETRSS = "getrss"
LIBRARY_GETLASTTIME = "latesttime"
LIBRARY_MGR = "/kindleearappspotlibrary/mgr/"
LIBRARY_GETSRC = "getsrc"
LIBRARY_REPORT_INVALID = "reportinvalid"
SUBSCRIBED_FROM_LIBRARY = "subscribedfromshared"
LIBRARY_CATEGORY = "/kindleearappspotlibrarycategory"
KINDLEEAR_SITE_KEY = "kindleear.lucky!"

#===========================================================================================================
#             以下函数仅为 kindleear.appspot.com 使用
#===========================================================================================================
bpLibraryOffical = Blueprint('bpLibraryOffical', __name__)

#提供共享库订阅源数据(仅用于kindleear.appspot.com"官方"共享服务器)
@bpLibraryOffical.route(LIBRARY_KINDLEEAR)
def SharedLibraryAppspot():
    args = request.args
    key = args.get('key') #避免爬虫消耗资源
    if key != KINDLEEAR_SITE_KEY:
        return []

    dataType = args.get('data_type')
    if dataType == LIBRARY_GETLASTTIME: #获取分享库的最近更新
        dbItem = AppInfo.get_or_none(AppInfo.name == 'lastSharedRssTime')
        #转换为时间戳，秒数
        lastSharedRssTime = int(dbItem.time_value.timestamp()) if dbItem else 0
        return {'status': 'ok', 'data': lastSharedRssTime}
    else:
        #本来想在服务器端分页的，但是好像CPU/数据库存取资源比带宽资源更紧张，所以干脆一次性提供给客户端，由客户端分页和分类
        #如果后续发现这样不理想，也可以考虑修改为服务器端分页
        #'r':以后可以扩展为github上的连接，现在先提供本地数据库id
        #唯一一个需要数据库索引的地方，因为这个只有自己部署的服务需要，所以没问题
        sharedData = [{'t': d.title, 'u': d.url, 'f': d.isfulltext, 'l': d.language, 'c': d.category, 's': d.subscribed,
                'd': int(d.last_subscribed_time.timestamp()), 'r': f'db:{d.id}', 'e': d.description}
                for d in SharedRss.select().order_by(SharedRss.last_subscribed_time.desc()).limit(2000).execute()]

        #使用更紧凑的输出格式
        #return sharedData
        return Response(json.dumps(sharedData, separators=(',', ':')), mimetype='application/json')
        
#网友分享了一个订阅链接或recipe(仅用于kindleear.appspot.com"官方"共享服务器)
@bpLibraryOffical.post(LIBRARY_KINDLEEAR)
def SharedLibraryAppspotAjax():
    form = request.form
    key = form.get('key')
    if key != KINDLEEAR_SITE_KEY: #避免爬虫消耗资源
        return {}

    #如果是自定义RSS，则category/title/url/isfulltext/lang有效
    #对于上传的recipe，category/title/src/desciption有效
    category = form.get('category', '')
    title = form.get('title')
    url = form.get('url', '')
    lang = form.get('lang', '').lower()
    isfulltext = str_to_bool(form.get('isfulltext', ''))
    creator = form.get('creator', '')
    src = form.get('src', '')
    description = form.get('description', '')

    respDict = {'status': 'ok', 'category': category, 'title': title, 'url': url, 'lang': lang, 
        'isfulltext': isfulltext, 'creator': creator}

    if not title or not (url or src): #url 和 src 至少要有一个
        respDict['status'] = "The title or url or src is empty!"
        return respDict

    #将贡献者的网址加密
    #from apps.utils import hide_website
    #creator = hide_website(creator)
    creator = hashlib.md5(creator.encode('utf-8')).hexdigest()

    #判断是否存在，如果存在，则更新分类或必要的信息，同时返回成功
    now = datetime.datetime.utcnow()
    if url: #自定义RSS，以url为准
        dbItem = SharedRss.get_or_none(SharedRss.url == url)
    else: #上传的recipe，以title为准
        dbItem = SharedRss.get_or_none(SharedRss.title == title)
    
    #其实这里应该判断是否为同一个作者，但是想想其他人发现错误也可以修改
    prevCategory = ''
    if dbItem:
        dbItem.title = title
        dbItem.url = url
        dbItem.src = src
        dbItem.description = description
        dbItem.isfulltext = isfulltext
        dbItem.language = lang
        dbItem.invalid_report_days = 0
        dbItem.creator = creator
        if category:
            prevCategory = dbItem.category
            dbItem.category = category
    else:
        dbItem = SharedRss(title=title, url=url, src=src, description=description, category=category, 
            language=lang, isfulltext=isfulltext, creator=creator, subscribed=1, created_time=now, 
            invalid_report_days=0, last_invalid_report_time=now, last_subscribed_time=now)
    dbItem.save()
    UpdateLastSharedRssTime()

    #更新分类信息，用于缓存
    if category:
        cItem = SharedRssCategory.get_or_none(SharedRssCategory.name == category)
        if cItem:
            cItem.last_updated = now
        else:
            cItem = SharedRssCategory(name=category, last_updated=now)
        cItem.save()

    #没有其他订阅源使用此分类了
    if prevCategory and not SharedRss.get_or_none(SharedRss.category == prevCategory):
        SharedRssCategory.delete().where(SharedRssCategory.name == prevCategory).execute()
        
    return respDict

#更新共享库的最新时间信息(仅用于kindleear.appspot.com"官方"共享服务器)
def UpdateLastSharedRssTime():
    dbItem = AppInfo.get_or_none(AppInfo.name == 'lastSharedRssTime')
    if dbItem:
        dbItem.time_value = datetime.datetime.utcnow()
        dbItem.save()
    else:
        AppInfo.create(name='lastSharedRssTime', time_value=datetime.datetime.utcnow())

#共享库的订阅源信息管理(仅用于kindleear.appspot.com"官方"共享服务器)
@bpLibraryOffical.post(LIBRARY_MGR + "<mgrType>")
def SharedLibraryMgrAppspotPost(mgrType):
    now = datetime.datetime.utcnow()
    form = request.form
    #print(mgrType, LIBRARY_GETSRC)
    if mgrType == LIBRARY_GETSRC: #获取一个共享recipe的源代码
        dbId = form.get('recipeId', '')
        if dbId.startswith('db:'):
            dbId = dbId[3:]
            recipe = Recipe.get_by_id_or_none(dbId)
            if recipe and recipe.src:
                return {'status': 'ok', 'src': recipe.src}
        return {'status': 'The recipe does not exist.'}
    elif mgrType == LIBRARY_REPORT_INVALID: #报告一个源失效了
        title = form.get('title', '')
        url = form.get('url', '')
        recipeId = form.get('recipeId', '') #当前仅用于数据库ID
        respDict = {'status': 'ok', 'title': title, 'url': url, 'recipeId': recipeId}

        if not url:
            respDict['status'] = "Url is empty!"
            return respDict

        if not url.lower().startswith('http'):
            url = 'https://' + url
            respDict['url'] = url

        #判断是否存在
        if url:
            dbItem = SharedRss.get_or_none(SharedRss.url == url)
        elif recipeId.startswith('db:'):
            dbItem = SharedRss.get_by_id_or_none(recipeId[3:])

        if not dbItem:
            respDict['status'] = "The rss is not found in the database"
            return respDict

        #希望能做到“免维护”，在一定数量的失效报告之后，自动删除对应的源，假定前提是人性本善
        delta = abs(now - dbItem.last_invalid_report_time)
        deltaDays = delta.days

        if deltaDays > 180: #半年内没有人报告失效则重新计数
            dbItem.invalid_report_days = 1
        elif delta.days >= 1: #一天内报告多次只算一次
            dbItem.invalid_report_days += 1

        if dbItem.invalid_report_days > 5: #相当于半年内有5次源失效报告则自动删除
            category = dbItem.category
            dbItem.delete_instance()
            UpdateLastSharedRssTime()

            #如果删除的源是它所在的分类下面最后一个，则其分类信息也一并删除
            if SharedRss.get_or_none(SharedRss.category == category) is None:
                cItem = SharedRssCategory.get_or_none(SharedRssCategory.name == category)
                if cItem:
                    cItem.delete_instance()
        else:
            dbItem.last_invalid_report_time = now
            dbItem.save()

        return respDict
    elif mgrType == SUBSCRIBED_FROM_LIBRARY: #有用户订阅了一个共享库里面的链接
        title = request.form.get('title')
        url = request.form.get('url')
        respDict = {'status': 'ok', 'title': title, 'url': url}

        if not url:
            respDict['status'] = "Url is empty!"
            return respDict

        if not url.lower().startswith('http'):
            url = 'https://' + url
            respDict['url'] = url

        #更新数据库实体
        dbItem = SharedRss.get_or_none(SharedRss.url == url)
        if dbItem:
            dbItem.subscribed += 1
            dbItem.last_subscribed_time = now
            dbItem.save()
            UpdateLastSharedRssTime()
        else:
            respDict['status'] = "URL not found in database!"

        return respDict
    else:
        return {'status': '[KE] Unknown command: {}'.format(mgrType)}

#共享库的订阅源数据分类信息(仅用于kindleear.appspot.com"官方"共享服务器)
@bpLibraryOffical.route(LIBRARY_CATEGORY)
def SharedLibraryCategoryAppspot():
    key = request.args.get('key') #避免爬虫消耗IO资源
    if key != KINDLEEAR_SITE_KEY:
        return {}

    cats = sorted(SharedRssCategory.get_all(), key=attrgetter('last_updated'), reverse=True)
    return [item.name for item in cats]
