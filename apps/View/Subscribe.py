#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>

import datetime

import web
try:
    import json
except ImportError:
    import simplejson as json

from google.appengine.api import memcache
from apps.utils import etagged
from apps.BaseHandler import BaseHandler
from apps.dbModels import *

class MySubscription(BaseHandler):
    __url__ = "/my"
    # 管理我的订阅和杂志列表
    @etagged()
    def GET(self, tips=None):
        user = self.getcurrentuser()
        myfeeds = user.ownfeeds.feeds if user.ownfeeds else None
        return self.render('my.html', "My subscription",current='my',user=user,
            books=Book.all().filter("builtin = ",True),myfeeds=myfeeds,tips=tips)
    
    def POST(self): # 添加自定义RSS
        user = self.getcurrentuser()
        title = web.input().get('t')
        url = web.input().get('url')
        isfulltext = bool(web.input().get('fulltext'))
        if not title or not url:
            return self.GET(_("Title or url is empty!"))
        
        if not url.lower().startswith('http'): #http and https
            url = 'http://' + url
        assert user.ownfeeds
        Feed(title=title,url=url,book=user.ownfeeds,isfulltext=isfulltext,
            time=datetime.datetime.utcnow()).put()
        memcache.delete('%d.feedscount'%user.ownfeeds.key().id())
        raise web.seeother('/my')

class FeedsAjax(BaseHandler):
    __url__ = "/feeds/(.*)"
    
    def POST(self, mgrType):
        web.header('Content-Type', 'application/json')
        user = self.getcurrentuser()
        
        if mgrType.lower() == 'delete':
            feedid = web.input().get('feedid')
            try:
                feedid = int(feedid)
            except:
                return json.dumps({'status': _('The id is invalid!')})
            
            feed = Feed.get_by_id(feedid)
            if feed:
                feed.delete()
                return json.dumps({'status':'ok'})
            else:
                return json.dumps({'status': _('The feed(%d) not exist!') % feedid})
        elif mgrType.lower() == 'add':
            title = web.input().get('title')
            url = web.input().get('url')
            isfulltext = bool(web.input().get('fulltext','').lower() == 'true')
            respDict = {'status':'ok', 'title':title, 'url':url, 'isfulltext':isfulltext}
            
            if not title or not url:
                respDict['status'] = _("Title or Url is empty!")
                return json.dumps(respDict)
            
            if not url.lower().startswith('http'):
                url = 'http://' + url
                respDict['url'] = url
            
            fd = Feed(title=title, url=url, book=user.ownfeeds, isfulltext=isfulltext,
                time=datetime.datetime.utcnow())
            fd.put()
            respDict['feedid'] = fd.key().id()
            memcache.delete('%d.feedscount' % user.ownfeeds.key().id())
            return json.dumps(respDict)

class BooksAjax(BaseHandler):
    __url__ = "/books/(.*)"
    
    def POST(self, mgrType):
        web.header('Content-Type', 'application/json')
        user = self.getcurrentuser()
        
        if mgrType.lower() == 'unsubscribe':
            id_ = web.input().get('id_')
            try:
                id_ = int(id_)
            except:
                return json.dumps({'status': _('The id is invalid!')})
            
            bk = Book.get_by_id(id_)
            if not bk:
                return json.dumps({'status': _('The book(%d) not exist!') % id_})
            
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
            id_ = web.input().get('id_')
            separate = web.input().get('separate', '')
            
            respDict = {'status':'ok'}
            
            try:
                id_ = int(id_)
            except:
                return json.dumps({'status': _('The id is invalid')})
            
            bk = Book.get_by_id(id_)
            if not bk:
                return json.dumps({'status': 'The book(%d) not exist!' % id_})
            
            if user.name not in bk.users:
                bk.users.append(user.name)
                bk.separate = bool(separate.lower() in ('true','1'))
                bk.put()
                
            respDict['title'] = bk.title
            respDict['desc'] = bk.description
            respDict['needs_subscription'] = bk.needs_subscription
            respDict['subscription_info'] = bool(user.subscription_info(bk.title))
            respDict['separate'] = bk.separate
            return json.dumps(respDict)
            
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
        
        if main.session.username not in bk.users:
            bk.users.append(main.session.username)
            bk.separate = bool(web.input().get('separate') in ('true','1'))
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
        return self.render('booklogininfo.html', "Book Login Infomation",bk=bk,subs_info=subs_info,tips=tips)
    
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
            subs_info = SubscriptionInfo(account=account,user=user,title=bk.title)
            subs_info.put() #先保存一次才有user信息，然后才能加密
            subs_info.password = password
            subs_info.put()
            
        raise web.seeother('/my')
