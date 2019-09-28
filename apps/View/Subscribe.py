#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>

import datetime
from operator import attrgetter
import web
import urlparse

try:
    import json
except ImportError:
    import simplejson as json

from google.appengine.api import memcache
from apps.utils import etagged
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from lib.urlopener import URLOpener
from books import BookClasses, BookClass
from books.base import BaseComicBook
from books.comic import ComicBaseClasses
from config import *
from apps.View.Library import SharedLibraryMgrkindleearAppspotCom

class MySubscription(BaseHandler):
    __url__ = "/my"
    # 管理我的订阅和杂志列表
    @etagged()
    def GET(self, tips=None):
        user = self.getcurrentuser()
        title_to_add = web.input().get('title_to_add')
        url_to_add = web.input().get('url_to_add')
        myfeeds = user.ownfeeds.feeds if user.ownfeeds else None
        books = list(Book.all().filter("builtin = ", True))
        # 简单排个序，为什么不用数据库直接排序是因为Datastore数据库需要建立索引才能排序
        books.sort(key=attrgetter("title"))

        return self.render(
            "my.html",
            "Feeds",
            current="my",
            user=user,
            books=books,
            myfeeds=myfeeds,
            comic_base_classes=ComicBaseClasses,
            tips=tips,
            subscribe_url=urlparse.urljoin(DOMAIN, self.__url__),
            title_to_add=title_to_add,
            url_to_add=url_to_add
        )

    def POST(self):  # 添加自定义RSS
        user = self.getcurrentuser()
        title = web.input().get('t')
        url = web.input().get('url')
        isfulltext = bool(web.input().get('fulltext'))
        if not title or not url:
            return self.GET(_("Title or url is empty!"))

        if not url.lower().startswith('http'): #http and https
            url = 'http://' + url

        assert user.ownfeeds

        #判断是否重复
        ownUrls = [item.url for item in user.ownfeeds.feeds]
        if url in ownUrls:
            return self.GET(_("Duplicated subscription!"))

        Feed(title=title, url=url, book=user.ownfeeds, isfulltext=isfulltext,
            time=datetime.datetime.utcnow()).put()
        memcache.delete('%d.feedscount' % user.ownfeeds.key().id())
        raise web.seeother('/my')

#添加/删除自定义RSS订阅的AJAX处理函数
class FeedsAjax(BaseHandler):
    __url__ = "/feeds/(.*)"

    def POST(self, mgrType):
        user = self.getcurrentuser(forAjax=True)
        web.header('Content-Type', 'application/json')

        if mgrType.lower() == 'delete':
            feedid = web.input().get('feedid')
            try:
                feedid = int(feedid)
            except:
                return json.dumps({'status': _('The id is invalid!')})

            feed = Feed.get_by_id(feedid)
            if feed:
                feed.delete()
                return json.dumps({'status': 'ok'})
            else:
                return json.dumps({'status': _('The feed(%d) not exist!') % feedid})
        elif mgrType.lower() == 'add':
            title = web.input().get('title')
            url = web.input().get('url')
            isfulltext = bool(web.input().get('fulltext', '').lower() == 'true')
            fromSharedLibrary = bool(web.input().get('fromsharedlibrary', '').lower() == 'true')

            respDict = {'status':'ok', 'title':title, 'url':url, 'isfulltext':isfulltext}

            if not title or not url:
                respDict['status'] = _("Title or Url is empty!")
                return json.dumps(respDict)

            if not url.lower().startswith('http'):
                url = 'http://' + url
                respDict['url'] = url

            #判断是否重复
            ownUrls = [item.url for item in user.ownfeeds.feeds]
            if url in ownUrls:
                respDict['status'] = _("Duplicated subscription!")
                return json.dumps(respDict)

            fd = Feed(title=title, url=url, book=user.ownfeeds, isfulltext=isfulltext,
                time=datetime.datetime.utcnow())
            fd.put()
            respDict['feedid'] = fd.key().id()
            memcache.delete('%d.feedscount' % user.ownfeeds.key().id())

            #如果是从共享库中订阅的，则通知共享服务器，提供订阅数量信息，以便排序
            if fromSharedLibrary:
                self.SendNewSubscription(title, url)

            return json.dumps(respDict)
        else:
            return json.dumps({'status': 'unknown command: %s' % mgrType})

    def SendNewSubscription(self, title, url):
        opener = URLOpener()
        path = SharedLibraryMgrkindleearAppspotCom.__url__.split('/')
        path[-1] = 'subscribedfromshared'
        srvUrl = urlparse.urljoin('http://kindleear.appspot.com/', '/'.join(path))
        data = {'title': title, 'url': url}
        result = opener.open(srvUrl, data) #只管杀不管埋，不用管能否成功了

#订阅/退订内置书籍的AJAX处理函数
class BooksAjax(BaseHandler):
    __url__ = "/books/(.*)"

    def POST(self, mgrType):
        web.header('Content-Type', 'application/json')
        user = self.getcurrentuser(forAjax=True)
        id_ = web.input().get('id_')
        try:
            id_ = int(id_)
        except:
            return json.dumps({'status': _('The id is invalid!')})

        bk = Book.get_by_id(id_)
        if not bk:
            return json.dumps({'status': _('The book(%d) not exist!') % id_})

        if mgrType.lower() == 'unsubscribe':
            if user.name in bk.users:
                bk.users.remove(user.name)
                bk.separate = False
                bk.put()

            #为安全起见，退订后也删除网站登陆信息（如果有的话）
            subs_info = user.subscription_info(bk.title)
            if subs_info:
                subs_info.delete()

            return json.dumps({'status':'ok', 'title': bk.title, 'desc': bk.description})
        elif mgrType.lower() == 'subscribe':
            separate = web.input().get('separate', '')

            respDict = {'status':'ok'}

            bkcls = BookClass(bk.title)
            if not bkcls:
                return json.dumps({'status': 'The book(%d) not exist!' % id_})

            #如果是漫画类，则不管是否选择了“单独推送”，都自动变成“单独推送”
            if issubclass(bkcls, BaseComicBook):
                separate = 'true'

            if user.name not in bk.users:
                bk.users.append(user.name)
                bk.separate = bool(separate.lower() in ('true', '1'))
                bk.put()

            respDict['title'] = bk.title
            respDict['desc'] = bk.description
            respDict['needs_subscription'] = bk.needs_subscription
            respDict['subscription_info'] = bool(user.subscription_info(bk.title))
            respDict['separate'] = bk.separate
            return json.dumps(respDict)
        else:
            return json.dumps({'status': 'unknown command: %s' % mgrType})

class Subscribe(BaseHandler):
    __url__ = "/subscribe/(.*)"
    def GET(self, id_):
        self.login_required()
        try:
            id_ = int(id_)
        except:
            return "the id is invalid!<br />"

        bk = Book.get_by_id(id_)
        if not bk:
            return "the book(%d) not exist!<br />" % id_

        bkcls = BookClass(bk.title)
        if not bkcls:
            return "the book(%d) not exist!<br />" % id_

        #如果是漫画类，则不管是否选择了“单独推送”，都自动变成“单独推送”
        if issubclass(bkcls, BaseComicBook):
            separate = 'true'
        else:
            separate = web.input().get('separate', 'true')

        if main.session.username not in bk.users:
            bk.users.append(main.session.username)
            bk.separate = bool(separate in ('true', '1'))
            bk.put()
        raise web.seeother('/my')

class Unsubscribe(BaseHandler):
    __url__ = "/unsubscribe/(.*)"
    def GET(self, id_):
        user = self.getcurrentuser()
        try:
            id_ = int(id_)
        except:
            return "the id is invalid!<br />"

        bk = Book.get_by_id(id_)
        if not bk:
            return "the book(%d) not exist!<br />" % id_

        if main.session.username in bk.users:
            bk.users.remove(main.session.username)
            bk.separate = False
            bk.put()

        #为安全起见，退订后也删除网站登陆信息（如果有的话）
        subs_info = user.subscription_info(bk.title)
        if subs_info:
            subs_info.delete()

        raise web.seeother('/my')

class DelFeed(BaseHandler):
    __url__ = "/delfeed/(.*)"
    def GET(self, id_):
        user = self.getcurrentuser()
        try:
            id_ = int(id_)
        except:
            return "the id is invalid!<br />"

        feed = Feed.get_by_id(id_)
        if feed:
            feed.delete()

        raise web.seeother('/my')

class BookLoginInfo(BaseHandler):
    __url__ = "/booklogininfo/(.*)"
    #修改书籍的网站登陆信息
    def GET(self, id_, tips=None):
        user = self.getcurrentuser()
        try:
            bk = Book.get_by_id(int(id_))
        except:
            bk = None
        if not bk:
            return "Not exist the book!<br />"

        subs_info = user.subscription_info(bk.title)
        return self.render('booklogininfo.html', "Book Login Infomation", bk=bk, subs_info=subs_info, tips=tips)

    def POST(self, id_):
        user = self.getcurrentuser()
        account = web.input().get('account')
        password = web.input().get('password')

        try:
            bk = Book.get_by_id(int(id_))
        except:
            bk = None
        if not bk:
            return "Not exist the book!<br />"

        subs_info = user.subscription_info(bk.title)
        if subs_info:
            #任何一个留空则删除登陆信息
            if not account or not password:
                subs_info.delete()
            else:
                subs_info.account = account
                subs_info.password = password
                subs_info.put()
        elif account and password:
            subs_info = SubscriptionInfo(account=account, user=user, title=bk.title)
            subs_info.put() #先保存一次才有user信息，然后才能加密
            subs_info.password = password
            subs_info.put()

        raise web.seeother('/my')
