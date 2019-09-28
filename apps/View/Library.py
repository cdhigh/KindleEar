#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
import datetime, urlparse
try:
    import json
except ImportError:
    import simplejson as json

import web
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from lib.urlopener import URLOpener

#网友共享的订阅源数据
class SharedLibrary(BaseHandler):
    __url__ = "/library"

    def GET(self):
        user = self.getcurrentuser()

        #连接分享服务器获取数据
        shared_data = []
        tips = ''
        opener = URLOpener()
        url = urlparse.urljoin('http://kindleear.appspot.com/', SharedLibrarykindleearAppspotCom.__url__)
        result = opener.open(url + '?key=kindleear.lucky!')
        if result.status_code == 200 and result.content:
            shared_data = json.loads(result.content)
        else:
            tips = _('Cannot fetch data from kindleear.appspot.com, status: ') + URLOpener.CodeMap(result.status_code)

        return self.render('sharedlibrary.html', "Shared",
            current='shared', user=user, shared_data=shared_data, tips=tips)

    #分享了一个订阅源
    def POST(self):
        user = self.getcurrentuser(forAjax=True)
        web.header('Content-Type', 'application/json')
        webInput = web.input()
        category = webInput.get('category', '')
        title = webInput.get('title')
        feedUrl = webInput.get("url")
        isfulltext = bool(webInput.get('isfulltext', '').lower() == 'true')
        creator = webInput.get('creator', '')

        if not title or not feedUrl:
            return json.dumps({'status': _("Title or Url is empty!")})

        opener = URLOpener()
        srvUrl = urlparse.urljoin('http://kindleear.appspot.com/', SharedLibrarykindleearAppspotCom.__url__)
        data = {'category': category, 'title': title, 'url': feedUrl, 'creator': creator,
            'isfulltext': 'true' if isfulltext else 'false', 'key': 'kindleear.lucky!'}
        result = opener.open(srvUrl, data)
        if result.status_code == 200 and result.content:
            return result.content
        else:
            return json.dumps({'status': _('Cannot submit data to kindleear.appspot.com, status: %s' % URLOpener.CodeMap(result.status_code))})

class SharedLibraryMgr(BaseHandler):
    __url__ = "/library/mgr/(.*)"

    def POST(self, mgrType):
        user = self.getcurrentuser(forAjax=True)
        if mgrType == 'reportinvalid': #报告一个源失效了
            web.header('Content-Type', 'application/json')
            title = web.input().get('title', '')
            feedUrl = web.input().get('url', '')

            opener = URLOpener()
            path = SharedLibraryMgrkindleearAppspotCom.__url__.split('/')
            path[-1] = mgrType
            srvUrl = urlparse.urljoin('http://kindleear.appspot.com/', '/'.join(path))
            data = {'title': title, 'url': feedUrl, 'key': 'kindleear.lucky!'}
            result = opener.open(srvUrl, data)
            if result.status_code == 200 and result.content:
                return result.content
            else:
                return json.dumps({'status': _('Cannot fetch data from kindleear.appspot.com, status: ') + URLOpener.CodeMap(result.status_code)})
        else:
            return json.dumps({'status': 'unknown command: %s' % mgrType})

#共享的订阅源的分类信息
class SharedLibraryCategory(BaseHandler):
    __url__ = "/library/category"

    def GET(self):
        user = self.getcurrentuser(forAjax=True)
        web.header('Content-Type', 'application/json')

        #连接分享服务器获取数据
        respDict = {'status':'ok', 'categories':[]}

        opener = URLOpener()
        url = urlparse.urljoin('http://kindleear.appspot.com/', SharedLibraryCategorykindleearAppspotCom.__url__)
        result = opener.open(url + '?key=kindleear.lucky!')

        if result.status_code == 200 and result.content:
            respDict['categories'] = json.loads(result.content)
        else:
            respDict['status'] = _('Cannot fetch data from kindleear.appspot.com, status: ') + URLOpener.CodeMap(result.status_code)

        return json.dumps(respDict)

#===========================================================================================================
#             以下函数仅为 kindleear.appspot.com 使用
#===========================================================================================================

#共享库订阅源数据(仅用于kindleear.appspot.com"官方"共享服务器)
class SharedLibrarykindleearAppspotCom(BaseHandler):
    __url__ = "/kindleearappspotlibrary"

    def __init__(self):
        super(SharedLibrarykindleearAppspotCom, self).__init__(setLang=False)

    def GET(self):
        key = web.input().get('key', '') #避免爬虫消耗资源
        if key != 'kindleear.lucky!':
            return ''

        web.header('Content-Type', 'application/json')

        #本来想在服务器端分页的，但是好像CPU/数据库存取资源比带宽资源更紧张，所以干脆一次性提供给客户端，由客户端分页和分类
        #如果后续发现这样不理想，也可以考虑修改为服务器端分页
        #qry = SharedRss.all().order('-subscribed').order('-created_time').fetch(limit=10000)
        shared_data = []
        for d in SharedRss.all().fetch(limit=10000):
            shared_data.append({'t':d.title, 'u':d.url, 'f':d.isfulltext, 'c':d.category, 's':d.subscribed,
                'd':int((d.created_time - datetime.datetime(1970, 1, 1)).total_seconds())})
        return json.dumps(shared_data)

    #网友分享了一个订阅链接
    def POST(self):
        web.header('Content-Type', 'application/json')
        webInput = web.input()
        key = webInput.get('key')
        if key != 'kindleear.lucky!': #避免爬虫消耗资源
            return ''

        category = webInput.get('category', '')
        title = webInput.get('title')
        url = webInput.get("url")
        isfulltext = bool(webInput.get('isfulltext', '').lower() == 'true')
        creator = webInput.get('creator', '')

        respDict = {'status':'ok', 'category':category, 'title':title, 'url':url, 'isfulltext':isfulltext, 'creator':creator}

        if not title or not url:
            respDict['status'] = _("Title or Url is empty!")
            return json.dumps(respDict)

        #将贡献者的网址加密
        if creator:
            parts = urlparse.urlparse(creator)
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

        #判断是否存在，如果存在，则更新分类或必要的信息，同时还是返回成功
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
class SharedLibraryMgrkindleearAppspotCom(BaseHandler):
    __url__ = "/kindleearappspotlibrary/mgr/(.*)"

    def __init__(self):
        super(SharedLibraryMgrkindleearAppspotCom, self).__init__(setLang=False)

    def POST(self, mgrType):
        if mgrType == 'reportinvalid': #报告一个源失效了
            title = web.input().get('title')
            url = web.input().get('url')
            respDict = {'status':'ok', 'title':title, 'url':url}

            if not url:
                respDict['status'] = _("Url is empty!")
                return json.dumps(respDict)

            if not url.lower().startswith('http'):
                url = 'http://' + url
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
        elif mgrType == 'subscribedfromshared': #有用户订阅了一个共享库里面的链接
            title = web.input().get('title')
            url = web.input().get('url')
            respDict = {'status':'ok', 'title':title, 'url':url}

            if not url:
                respDict['status'] = _("Url is empty!")
                return json.dumps(respDict)

            if not url.lower().startswith('http'):
                url = 'http://' + url
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
            return json.dumps({'status': 'unknown command: %s' % mgrType})

#共享库的订阅源数据分类信息(仅用于kindleear.appspot.com"官方"共享服务器)
class SharedLibraryCategorykindleearAppspotCom(BaseHandler):
    __url__ = "/kindleearappspotlibrarycategory"

    def __init__(self):
        super(SharedLibraryCategorykindleearAppspotCom, self).__init__(setLang=False)

    def GET(self):
        key = web.input().get('key', '') #避免爬虫消耗IO资源
        if key != 'kindleear.lucky!':
            return ''

        web.header('Content-Type', 'application/json')
        return json.dumps([item.name for item in SharedRssCategory.all().order('-last_updated')])
