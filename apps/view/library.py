#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#网友共享的订阅源数据
import datetime, json
from operator import attrgetter
from urllib.parse import urljoin, urlparse
from flask import Blueprint, render_template, request
from flask_babel import gettext as _
from apps.base_handler import *
from apps.back_end.db_models import *
from lib.urlopener import UrlOpener

#几个"官方"服务的地址
KINDLEEAR_SITE = "https://kindleear.appspot.com"
SHARED_LIBRARY_KINDLEEAR = "/kindleearappspotlibrary"
SHARED_LIBRARY_MGR_KINDLEEAR = "/kindleearappspotlibrary/mgr/"
SHARED_LIB_MGR_CMD_REPORTINVALID = "reportinvalid"
SHARED_LIB_MGR_CMD_SUBSFROMSHARED = "subscribedfromshared"
SHARED_LIBRARY_CAT_KINDLEEAR = "/kindleearappspotlibrarycategory"
KINDLEEAR_SITE_KEY = "kindleear.lucky!"

bpLibrary = Blueprint('bpLibrary', __name__)

#网友共享的订阅源数据
@bpLibrary.route("/library", endpoint='SharedLibrary')
@login_required()
def SharedLibrary():
    user = get_login_user()

    #连接分享服务器获取数据
    sharedData = []
    tips = ''
    opener = UrlOpener()
    url = urljoin(KINDLEEAR_SITE, SHARED_LIBRARY_KINDLEEAR)
    result = opener.open('{}?key={}'.format(url, KINDLEEAR_SITE_KEY))
    if result.status_code == 200:
        sharedData = json.loads(result.text)
    else:
        tips = _('Cannot fetch data from {}, status: {}').format(KINDLEEAR_SITE, UrlOpener.CodeMap(result.status_code))

    return render_template('sharedlibrary.html', tab='shared', user=user, shared_data=sharedData, tips=tips)

#分享了一个订阅源
@bpLibrary.post("/library", endpoint='SharedLibraryPost')
@login_required(forAjax=True)
def SharedLibraryPost():
    user = get_login_user()
    form = request.form
    category = form.get('category')
    title = form.get('title')
    feedUrl = form.get('url')
    isfulltext = bool(form.get('isfulltext', '').lower() == 'true')
    creator = form.get('creator')

    if not title or not feedUrl:
        return {'status': _("Title or Url is empty!")}

    opener = UrlOpener()
    url = urljoin(KINDLEEAR_SITE, SHARED_LIBRARY_KINDLEEAR)
    data = {'category': category, 'title': title, 'url': feedUrl, 'creator': creator,
        'isfulltext': 'true' if isfulltext else 'false', 'key': KINDLEEAR_SITE_KEY}
    result = opener.open(url, data)
    if result.status_code == 200:
        return result.text
    else:
        return {'status': 'Cannot submit data to {}, status: {}'.format(
            KINDLEEAR_SITE, UrlOpener.CodeMap(result.status_code))}

@bpLibrary.post("/library/mgr/<mgrType>", endpoint='SharedLibraryMgrPost')
@login_required(forAjax=True)
def SharedLibraryMgrPost(mgrType):
    user = get_login_user()
    if mgrType == SHARED_LIB_MGR_CMD_REPORTINVALID: #报告一个源失效了
        title = request.form.get('title')
        feedUrl = request.form.get('url')

        opener = UrlOpener()
        path = SHARED_LIBRARY_MGR_KINDLEEAR + mgrType
        url = urljoin(KINDLEEAR_SITE, path)
        data = {'title': title, 'url': feedUrl, 'key': KINDLEEAR_SITE_KEY}
        result = opener.open(url, data)
        if result.status_code == 200:
            return result.text
        else:
            return {'status': _('Cannot fetch data from {}, status: {}').format(KINDLEEAR_SITE, UrlOpener.CodeMap(result.status_code))}
    else:
        return {'status': 'Unknown command: {}'.format(mgrType)}

#共享的订阅源的分类信息
@bpLibrary.route("/library/category", endpoint='SharedLibraryCategory')
@login_required(forAjax=True)
def SharedLibraryCategory():
    user = get_login_user()
    
    #连接分享服务器获取数据
    respDict = {'status': 'ok', 'categories': []}

    opener = UrlOpener()
    url = urljoin(KINDLEEAR_SITE, SHARED_LIBRARY_CAT_KINDLEEAR)
    result = opener.open('{}?key={}'.format(url, KINDLEEAR_SITE_KEY))

    if result.status_code == 200:
        respDict['categories'] = json.loads(result.text)
    else:
        respDict['status'] = _('Cannot fetch data from {}, status: {}').format(
            KINDLEEAR_SITE, UrlOpener.CodeMap(result.status_code))

    return respDict

#===========================================================================================================
#             以下函数仅为 kindleear.appspot.com 使用
#===========================================================================================================

#共享库订阅源数据(仅用于kindleear.appspot.com"官方"共享服务器)
@bpLibrary.route(SHARED_LIBRARY_KINDLEEAR)
def SharedLibrarykindleearAppspotCom():
    key = request.args.get('key') #避免爬虫消耗资源
    if key != KINDLEEAR_SITE_KEY:
        return []

    #本来想在服务器端分页的，但是好像CPU/数据库存取资源比带宽资源更紧张，所以干脆一次性提供给客户端，由客户端分页和分类
    #如果后续发现这样不理想，也可以考虑修改为服务器端分页
    timeOrg = datetime.datetime(1970, 1, 1)
    sharedData = [{'t': d.title, 'u': d.url, 'f': d.isfulltext, 'c': d.category, 's': d.subscribed,
            'd': int((d.created_time - timeOrg).total_seconds()),} 
            for d in SharedRss.select().limit(1000).execute() ]
    
    return sharedData

#网友分享了一个订阅链接
@bpLibrary.post(SHARED_LIBRARY_KINDLEEAR)
def SharedLibrarykindleearAppspotComPost():
    from apps.utils import hide_website
    form = request.form
    key = form.get('key')
    if key != KINDLEEAR_SITE_KEY: #避免爬虫消耗资源
        return {}

    category = form.get('category')
    title = form.get('title')
    url = form.get('url')
    isfulltext = bool(form.get('isfulltext', '').lower() == 'true')
    creator = form.get('creator')

    respDict = {'status':'ok', 'category':category, 'title':title, 'url':url, 'isfulltext':isfulltext, 'creator':creator}

    if not title or not url:
        respDict['status'] = _("Title or Url is empty!")
        return respDict

    #将贡献者的网址加密
    creator = hide_website(creator)

    #判断是否存在，如果存在，则更新分类或必要的信息，同时返回成功
    now = datetime.datetime.utcnow()
    dbItem = SharedRss.get_one(SharedRss.url == url)
    prevCategory = ''
    if dbItem:
        dbItem.title = title
        dbItem.isfulltext = isfulltext
        dbItem.invalid_report_days = 0
        if category:
            prevCategory = dbItem.category
            dbItem.category = category
    else:
        dbItem = SharedRss(title=title, url=url, category=category, isfulltext=isfulltext, creator=creator,
            subscribed=1, created_time=now, invalid_report_days=0, last_invalid_report_time=now)
    dbItem.save()

    #更新分类信息，用于缓存
    if category:
        cItem = SharedRssCategory.get_one(SharedRssCategory.name == category)
        if cItem:
            cItem.last_updated = now
        else:
            cItem = SharedRssCategory(name=category, last_updated=now)
        cItem.save()

    if prevCategory:
        catItem = SharedRss.get_one(SharedRss.category == prevCategory)
        if not catItem: #没有其他订阅源使用此分类了
            sItem = SharedRssCategory.get_one(SharedRssCategory.name == prevCategory)
            if sItem:
                sItem.delete()

    return respDict

#共享库的订阅源信息管理
@bpLibrary.post(SHARED_LIBRARY_MGR_KINDLEEAR + "<mgrType>")
def SharedLibraryMgrkindleearAppspotComPost(mgrType):
    now = datetime.datetime.utcnow()
    if mgrType == SHARED_LIB_MGR_CMD_REPORTINVALID: #报告一个源失效了
        title = request.form.get('title')
        url = request.form.get('url')
        respDict = {'status': 'ok', 'title': title, 'url': url}

        if not url:
            respDict['status'] = _("Url is empty!")
            return respDict

        if not url.lower().startswith('http'):
            url = 'https://' + url
            respDict['url'] = url

        #判断是否存在
        dbItem = SharedRss.get_one(SharedRss.url == url)
        if not dbItem:
            respDict['status'] = _("URL not found in database!")
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
            dbItem.delete()

            #如果删除的源是它所在的分类下面最后一个，则其分类信息也一并删除
            if SharedRss.get_one(SharedRss.category == category) is None:
                cItem = SharedRssCategory.get_one(SharedRssCategory.name == category)
                if cItem:
                    cItem.delete()
        else:
            dbItem.last_invalid_report_time = now
            dbItem.save()

        return respDict
    elif mgrType == SHARED_LIB_MGR_CMD_SUBSFROMSHARED: #有用户订阅了一个共享库里面的链接
        title = request.form.get('title')
        url = request.form.get('url')
        respDict = {'status': 'ok', 'title': title, 'url': url}

        if not url:
            respDict['status'] = _("Url is empty!")
            return respDict

        if not url.lower().startswith('http'):
            url = 'https://' + url
            respDict['url'] = url

        #更新数据库实体
        dbItem = SharedRss.get_one(SharedRss.url == url)
        if dbItem:
            dbItem.subscribed += 1
            dbItem.last_subscribed_time = now
            dbItem.save()
        else:
            respDict['status'] = _("URL not found in database!")

        return respDict

    else:
        return {'status': 'Unknown command: {}'.format(mgrType)}

#共享库的订阅源数据分类信息(仅用于kindleear.appspot.com"官方"共享服务器)
@bpLibrary.route(SHARED_LIBRARY_CAT_KINDLEEAR)
def SharedLibraryCategorykindleearAppspotCom():
    key = request.args.get('key') #避免爬虫消耗IO资源
    if key != KINDLEEAR_SITE_KEY:
        return {}

    cats = list(SharedRssCategory.get_all())
    cats.sort(key=attrgetter('last_updated'), reverse=True)
    return cats
