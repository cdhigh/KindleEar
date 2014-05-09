#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#中文讨论贴：http://www.hi-pda.com/forum/viewthread.php?tid=1213082
#Contributors:
# rexdf <https://github.com/rexdf>

import datetime

import web

from google.appengine.api import memcache

from apps.BaseHandler import BaseHandler
from apps.dbModels import *

class MySubscription(BaseHandler):
    __url__ = "/my"
    # 管理我的订阅和杂志列表
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
        
class Subscribe(BaseHandler):
    __url__ = "/subscribe/(.*)"
    def GET(self, id):
        self.login_required()
        try:
            id = int(id)
        except:
            return "the id is invalid!<br />"
        
        bk = Book.get_by_id(id)
        if not bk:
            return "the book(%d) not exist!<br />" % id
        
        if main.session.username not in bk.users:
            bk.users.append(main.session.username)
            bk.put()
        raise web.seeother('/my')
        
class Unsubscribe(BaseHandler):
    __url__ = "/unsubscribe/(.*)"
    def GET(self, id):
        user = self.getcurrentuser()
        try:
            id = int(id)
        except:
            return "the id is invalid!<br />"
            
        bk = Book.get_by_id(id)
        if not bk:
            return "the book(%d) not exist!<br />" % id
        
        if main.session.username in bk.users:
            bk.users.remove(main.session.username)
            bk.put()
            
        #为安全起见，退订后也删除网站登陆信息（如果有的话）
        subs_info = user.subscription_info(bk.title)
        if subs_info:
            subs_info.delete()
            
        raise web.seeother('/my')

class DelFeed(BaseHandler):
    __url__ = "/delfeed/(.*)"
    def GET(self, id):
        user = self.getcurrentuser()
        try:
            id = int(id)
        except:
            return "the id is invalid!<br />"
        
        feed = Feed.get_by_id(id)
        if feed:
            feed.delete()
        
        raise web.seeother('/my')
        
class BookLoginInfo(BaseHandler):
    __url__ = "/booklogininfo/(.*)"
    #修改书籍的网站登陆信息
    def GET(self, id, tips=None):
        user = self.getcurrentuser()
        try:
            bk = Book.get_by_id(int(id))
        except:
            bk = None
        if not bk:
            return "Not exist the book!<br />"
        
        subs_info = user.subscription_info(bk.title)
        return self.render('booklogininfo.html', "Book Login Infomation",bk=bk,subs_info=subs_info,tips=tips)
    
    def POST(self,id):
        user = self.getcurrentuser()
        account = web.input().get('account')
        password = web.input().get('password')
        
        try:
            bk = Book.get_by_id(int(id))
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
