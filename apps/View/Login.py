#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>

import hashlib, gettext, datetime
try:
    import json
except ImportError:
    import simplejson as json

import web
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from books import BookClasses, BookClass
from apps.utils import new_secret_key

from config import *

class Login(BaseHandler):
    __url__ = "/login"
    def CheckAdminAccount(self):
        #判断管理员账号是否存在
        #如果管理员账号不存在，创建一个，并返回False，否则返回True
        u = KeUser.all().filter("name = ", 'admin').get()
        if not u:            
            myfeeds = Book(title=MY_FEEDS_TITLE, description=MY_FEEDS_DESC,
                    builtin=False, keep_image=True, oldest_article=7,
                    needs_subscription=False, separate=False)
            myfeeds.put()
            secret_key = new_secret_key()
            au = KeUser(name='admin', passwd=hashlib.md5('admin' + secret_key).hexdigest(),
                kindle_email='', enable_send=False, send_time=8, timezone=TIMEZONE,
                book_type="mobi", device='kindle', expires=None, ownfeeds=myfeeds, 
                merge_books=False, secret_key=secret_key, expiration_days=0)
            au.put()
            return False
        else:
            return True
            
    def GET(self):
        # 第一次登陆时如果没有管理员帐号，
        # 则增加一个管理员帐号admin，密码admin，后续可以修改密码
        tips = ''
        if not self.CheckAdminAccount():
            tips = _("Please use admin/admin to login at first time.")
        else:
            tips = _("Please input username and password.")
        
        if main.session.get('login') == 1:
            web.seeother(r'/')
        else:
            return self.render('login.html', "Login", tips=tips)
        
    def POST(self):
        name, passwd = web.input().get('u'), web.input().get('p')
        if name.strip() == '':
            tips = _("Username is empty!")
            return self.render('login.html', "Login", nickname='', tips=tips)
        elif len(name) > 25:
            tips = _("The len of username reached the limit of 25 chars!")
            return self.render('login.html', "Login", nickname='', tips=tips, username=name)
        elif '<' in name or '>' in name or '&' in name or '\\' in name or '/' in name:
            tips = _("The username includes unsafe chars!")
            return self.render('login.html', "Login", nickname='', tips=tips)
        
        self.CheckAdminAccount() #确认管理员账号是否存在
        
        u = KeUser.all().filter("name = ", name).get()
        if u:
            secret_key = u.secret_key or ''
            pwdhash = hashlib.md5(passwd + secret_key).hexdigest()
            if u.passwd != pwdhash:
                u = None
                
        if u:
            main.session.login = 1
            main.session.username = name
            if u.expires and u.expiration_days != 0: #用户登陆后自动续期
                days = 180 if u.expiration_days is None else u.expiration_days #兼容老版本和老账号
                u.expires = datetime.datetime.utcnow() + datetime.timedelta(days=days)
                u.put()
            
            #为了兼容性，对于新账号才一次性设置secret_key
            #老账号删除重建则可以享受加强的加密
            #if not u.secret_key:
            #    u.secret_key = new_secret_key()
            #    u.put()
                
            #修正从1.6.15之前的版本升级过来后自定义RSS丢失的问题
            for fd in Feed.all():
                if not fd.time:
                    fd.time = datetime.datetime.utcnow()
                    fd.put()
                
            #1.7新增各用户独立的白名单和URL过滤器，这些处理是为了兼容以前的版本
            if name == 'admin':
                for wl in WhiteList.all():
                    try:
                        if not wl.user:
                            wl.user = u
                            wl.put()
                    except:
                        pass
                for uf in UrlFilter.all():
                    try:
                        if not uf.user:
                            uf.user = u
                            uf.put()
                    except:
                        pass
            
            #1.25.3新增user.remove_hyperlinks
            if u.remove_hyperlinks is None:
                u.remove_hyperlinks = 'image'
                u.put()
                
            #同步书籍数据库
            bksToDelete = []
            for bk in Book.all().filter('builtin = ', True):
                found = False
                for book in BookClasses():
                    if book.title == bk.title:
                        if bk.description != book.description:
                            bk.description = book.description
                            bk.put()
                        if bk.needs_subscription != book.needs_subscription:
                            bk.needs_subscription = book.needs_subscription
                            bk.put()
                        found = True
                        break
                
                #如果删除了内置书籍py文件，则在数据库中也清除相关信息
                if not found:
                    subs = u.subscription_info(bk.title)
                    if subs:
                        subs.delete()
                    for fd in list(bk.feeds):
                        fd.delete()
                    bksToDelete.append(bk)

            #从数据库中删除书籍
            for bk in bksToDelete:
                bk.delete()
            
            if u.kindle_email:
                raise web.seeother(r'/my')
            else:
                raise web.seeother(r'/setting')
        else:
            import time
            time.sleep(5)
            tips = _("The username not exist or password is wrong!")
            lang = main.session.get('lang')
            if lang and lang.startswith('zh'):
                tips += '&nbsp;&nbsp;&nbsp;&nbsp;<a href="/static/faq.html#forgotpwd" target="_blank">' + _('Forgot password?') + '</a>'
            else:
                tips += '&nbsp;&nbsp;&nbsp;&nbsp;<a href="/static/faq_en.html#forgotpwd" target="_blank">' + _('Forgot password?') + '</a>'
            main.session.login = 0
            main.session.username = ''
            main.session.kill()
            return self.render('login.html', "Login", nickname='', tips=tips, username=name)

class Logout(BaseHandler):
    __url__ = "/logout"
    def GET(self):
        main.session.login = 0
        main.session.username = ''
        main.session.lang = ''
        main.session.kill()
        raise web.seeother(r'/')

#for ajax parser, if login required, retuan a dict 
class NeedLoginAjax(BaseHandler):
    __url__ = "/needloginforajax"
    def GET(self):
        web.header('Content-Type', 'application/json')
        return json.dumps({'status': _('login required')})
