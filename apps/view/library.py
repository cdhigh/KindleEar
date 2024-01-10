#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#网友共享的订阅源数据

import datetime, json
from urllib.parse import urljoin, urlparse
from bottle import route, post, response, request
from apps.base_handler import *
from apps.db_models import *
from lib.urlopener import UrlOpener

#几个"官方"服务的地址
KINDLEEAR_SITE = "https://kindleear.appspot.com"
SHARED_LIBRARY_KINDLEEAR = "/kindleearappspotlibrary"
SHARED_LIBRARY_MGR_KINDLEEAR = "/kindleearappspotlibrary/mgr/"
SHARED_LIB_MGR_CMD_REPORTINVALID = "reportinvalid"
SHARED_LIB_MGR_CMD_SUBSFROMSHARED = "subscribedfromshared"
SHARED_LIBRARY_CAT_KINDLEEAR = "/kindleearappspotlibrarycategory"
KINDLEEAR_SITE_KEY = "kindleear.lucky!"

#网友共享的订阅源数据
@route("/library")
def SharedLibrary():
    user = get_current_user()

    #连接分享服务器获取数据
    sharedData = []
    tips = ''
    opener = UrlOpener()
    url = urljoin(KINDLEEAR_SITE, SHARED_LIBRARY_KINDLEEAR)
    result = opener.open('{}?key={}'.format(url, KINDLEEAR_SITE_KEY))
    if result.status_code == 200:
        sharedData = json.loads(result.text)
    else:
        tips = _('Cannot fetch data from kindleear.appspot.com, status: ') + UrlOpener.CodeMap(result.status_code)

    return render_page('sharedlibrary.html', "Shared",
        current='shared', user=user, shared_data=sharedData, tips=tips)

#分享了一个订阅源
@post("/library")
def SharedLibraryPost():
    user = get_current_user(forAjax=True)
    response.content_type = 'application/json'
    forms = request.forms
    category = forms.category
    title = forms.title
    feedUrl = forms.url
    isfulltext = bool(forms.get('isfulltext', '').lower() == 'true')
    creator = forms.creator

    if not title or not feedUrl:
        return json.dumps({'status': _("Title or Url is empty!")})

    opener = UrlOpener()
    url = urljoin(KINDLEEAR_SITE, SHARED_LIBRARY_KINDLEEAR)
    data = {'category': category, 'title': title, 'url': feedUrl, 'creator': creator,
        'isfulltext': 'true' if isfulltext else 'false', 'key': KINDLEEAR_SITE_KEY}
    result = opener.open(url, data)
    if result.status_code == 200:
        return result.text
    else:
        return json.dumps({'status': 'Cannot submit data to {}, status: {}'.format(
            KINDLEEAR_SITE, UrlOpener.CodeMap(result.status_code))})

@post("/library/mgr/<mgrType>")
def SharedLibraryMgrPost(self, mgrType):
    user = get_current_user(forAjax=True)
    if mgrType == SHARED_LIB_MGR_CMD_REPORTINVALID: #报告一个源失效了
        response.content_type = 'application/json'
        title = request.forms.title
        feedUrl = request.forms.url

        opener = UrlOpener()
        path = SHARED_LIBRARY_MGR_KINDLEEAR + mgrType
        url = urljoin(KINDLEEAR_SITE, path)
        data = {'title': title, 'url': feedUrl, 'key': KINDLEEAR_SITE_KEY}
        result = opener.open(url, data)
        if result.status_code == 200:
            return result.text
        else:
            return json.dumps({'status': _('Cannot fetch data from kindleear.appspot.com, status: ') + UrlOpener.CodeMap(result.status_code)})
    else:
        return json.dumps({'status': 'unknown command: {}'.format(mgrType)})

#共享的订阅源的分类信息
@route("/library/category")
def SharedLibraryCategory():
    user = get_current_user(forAjax=True)
    response.content_type = 'application/json'

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

    return json.dumps(respDict)

#===========================================================================================================
#             以下函数仅为 kindleear.appspot.com 使用
#===========================================================================================================

#共享库订阅源数据(仅用于kindleear.appspot.com"官方"共享服务器)
@route(SHARED_LIBRARY_KINDLEEAR)
def SharedLibrarykindleearAppspotCom():
    key = request.query.key #避免爬虫消耗资源
    if key != KINDLEEAR_SITE_KEY:
        return ''

    response.content_type = 'application/json'

    #本来想在服务器端分页的，但是好像CPU/数据库存取资源比带宽资源更紧张，所以干脆一次性提供给客户端，由客户端分页和分类
    #如果后续发现这样不理想，也可以考虑修改为服务器端分页
    #qry = SharedRss.all().order('-subscribed').order('-created_time').fetch(limit=10000)
    sharedData = []
    for d in SharedRss.all().fetch(limit=10000):
        sharedData.append({'t':d.title, 'u':d.url, 'f':d.isfulltext, 'c':d.category, 's':d.subscribed,
            'd':int((d.created_time - datetime.datetime(1970, 1, 1)).total_seconds())})
    return json.dumps(sharedData)

#网友分享了一个订阅链接
@post(SHARED_LIBRARY_KINDLEEAR)
def SharedLibrarykindleearAppspotComPost():
    forms = request.forms
    key = forms.key
    if key != KINDLEEAR_SITE_KEY: #避免爬虫消耗资源
        return ''

    category = forms.category
    title = forms.title
    url = forms.url
    isfulltext = bool(forms.get('isfulltext', '').lower() == 'true')
    creator = forms.creator

    response.content_type = 'application/json'
    respDict = {'status':'ok', 'category':category, 'title':title, 'url':url, 'isfulltext':isfulltext, 'creator':creator}

    if not title or not url:
        respDict['status'] = _("Title or Url is empty!")
        return json.dumps(respDict)

    #将贡献者的网址加密
    if creator:
        parts = urlparse(creator)
        path = parts.path if parts.path else parts.netloc
        if '.' in path:
            pathArray = path.split('.')
            if len(pathArray[0]) > 4:
                pathArray[0] = pathArray[0][:2] + '**' + pathArray[0][-1]
            else:
                pathArray[0] = pathArray[0][0] + '**'
                pathArray[1] = pathArray[1][0] + '**'
            creator = '.'.join(pathArray)
        elif len(path) > 4:
            creator = path[:2] + '**' + path[-1]
        else:
            creator = path[0] + '**'

    #判断是否存在，如果存在，则更新分类或必要的信息，同时返回成功
    now = datetime.datetime.utcnow()
    dbItem = SharedRss.all().filter('url = ', url).get()
    prevCategory = ''
    if dbItem:
        dbItem.title = title
        dbItem.isfulltext = isfulltext
        dbItem.invalid_report_days = 0
        if category:
            prevCategory = dbItem.category
            dbItem.category = category
        dbItem.put()
    else:
        SharedRss(title=title, url=url, category=category, isfulltext=isfulltext, creator=creator,
            subscribed=1, created_time=now, invalid_report_days=0, last_invalid_report_time=now).put()

    #更新分类信息，用于缓存
    if category:
        cItem = SharedRssCategory.all().filter('name = ', category).get()
        if cItem:
            cItem.last_updated = now
            cItem.put()
        else:
            SharedRssCategory(name=category, last_updated=now).put()

    if prevCategory:
        catItem = SharedRss.all().filter('category = ', prevCategory).get()
        if not catItem: #没有其他订阅源使用此分类了
            sItem = SharedRssCategory.all().filter('name = ', prevCategory).get()
            if sItem:
                sItem.delete()

    return json.dumps(respDict)

#共享库的订阅源信息管理
@post(SHARED_LIBRARY_MGR_KINDLEEAR + "<mgrType>")
def SharedLibraryMgrkindleearAppspotComPost(mgrType):
    if mgrType == SHARED_LIB_MGR_CMD_REPORTINVALID: #报告一个源失效了
        title = request.forms.title
        url = request.forms.url
        respDict = {'status': 'ok', 'title': title, 'url': url}

        if not url:
            respDict['status'] = _("Url is empty!")
            return json.dumps(respDict)

        if not url.lower().startswith('http'):
            url = 'https://' + url
            respDict['url'] = url

        #判断是否存在
        dbItem = SharedRss.all().filter('url = ', url).get()
        if not dbItem:
            respDict['status'] = _("URL not found in database!")
            return json.dumps(respDict)

        #希望能做到“免维护”，在一定数量的失效报告之后，自动删除对应的源，这其实是要求不要有人恶作剧
        now = datetime.datetime.utcnow()
        delta = abs(now - dbItem.last_invalid_report_time)
        deltaDays = delta.days

        if deltaDays > 180:
            dbItem.invalid_report_days = 1
        elif delta.days >= 1:
            dbItem.invalid_report_days += 1

        if dbItem.invalid_report_days > 5:
            category = dbItem.category
            dbItem.delete()

            #更新分类信息
            allCategories = SharedRss.categories()
            if category not in allCategories:
                cItem = SharedRssCategory.all().filter('name = ', category).get()
                if cItem:
                    cItem.delete()
        else:
            dbItem.last_invalid_report_time = now
            dbItem.put()

        return json.dumps(respDict)
    elif mgrType == SHARED_LIB_MGR_CMD_SUBSFROMSHARED: #有用户订阅了一个共享库里面的链接
        title = request.forms.title
        url = request.forms.url
        respDict = {'status': 'ok', 'title': title, 'url': url}

        if not url:
            respDict['status'] = _("Url is empty!")
            return json.dumps(respDict)

        if not url.lower().startswith('http'):
            url = 'https://' + url
            respDict['url'] = url

        #判断是否存在
        dbItem = SharedRss.all().filter('url = ', url).get()
        if dbItem:
            dbItem.subscribed += 1
            dbItem.put()
        else:
            respDict['status'] = _("URL not found in database!")

        return json.dumps(respDict)

    else:
        return json.dumps({'status': 'Unknown command: {}'.format(mgrType)})

#共享库的订阅源数据分类信息(仅用于kindleear.appspot.com"官方"共享服务器)
@route(SHARED_LIBRARY_CAT_KINDLEEAR)
def SharedLibraryCategorykindleearAppspotCom():
    key = request.query.key #避免爬虫消耗IO资源
    if key != KINDLEEAR_SITE_KEY:
        return ''

    response.content_type = 'application/json'
    return json.dumps([item.name for item in SharedRssCategory.all().order('-last_updated')])
