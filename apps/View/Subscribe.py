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

import main

class MySubscription(BaseHandler):
    # 管理我的订阅和杂志列表
    def GET(self, tips=None):
        user = self.getcurrentuser()
        myfeeds = user.ownfeeds.feeds if user.ownfeeds else None
        return self.render('my.html', "My subscription",current='my',
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
    def GET(self, id):
        self.login_required()
        if not id:
            return "the id is empty!<br />"
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
    def GET(self, id):
        self.login_required()
        if not id:
            return "the id is empty!<br />"
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
        raise web.seeother('/my')

class DelFeed(BaseHandler):
    def GET(self, id):
        user = self.getcurrentuser()
        if not id:
            return "the id is empty!<br />"
        try:
            id = int(id)
        except:
            return "the id is invalid!<br />"
        
        feed = Feed.get_by_id(id)
        if feed:
            feed.delete()
        
        raise web.seeother('/my')