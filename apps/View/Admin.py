#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>

import hashlib, gettext, datetime

import web

from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import new_secret_key, etagged, str_to_int

from config import *

class Admin(BaseHandler):
    __url__ = "/admin"
    # 账户管理页面
    @etagged()
    def GET(self):
        user = self.getcurrentuser()
        users = KeUser.all() if user.name == 'admin' else None
        return self.render('admin.html', "Admin", current='admin', user=user, users=users)
        
    def POST(self):
        u, up1, up2 = web.input().get('u'), web.input().get('up1'), web.input().get('up2')
        expiration = str_to_int(web.input().get('expiration', '0'))
        op, p1, p2 = web.input().get('op'), web.input().get('p1'), web.input().get('p2')
        user = self.getcurrentuser()
        users = KeUser.all() if user.name == 'admin' else None
        
        if all((op, p1, p2)): #修改当前登陆账号的密码
            secret_key = user.secret_key or ''
            try:
                pwd = hashlib.md5(op+secret_key).hexdigest()
                newpwd = hashlib.md5(p1+secret_key).hexdigest()
            except:
                tips = _("The password includes non-ascii chars!")
            else:
                if user.passwd != pwd:
                    tips = _("Old password is wrong!")
                elif p1 != p2:
                    tips = _("The two new passwords are dismatch!")
                else:
                    tips = _("Change password success!")
                    user.passwd = newpwd
                    user.put()
            return self.render('admin.html', "Admin", current='admin', user=user, users=users, chpwdtips=tips)
        elif all((u, up1, up2)): #添加账户
            if user.name != 'admin':
                raise web.seeother(r'/')
            elif not u:
                tips = _("Username is empty!")
            elif up1 != up2:
                tips = _("The two new passwords are dismatch!")
            elif KeUser.all().filter("name = ", u).get():
                tips = _("Already exist the username!")
            else:
                secret_key = new_secret_key()
                try:
                    pwd = hashlib.md5(up1 + secret_key).hexdigest()
                except:
                    tips = _("The password includes non-ascii chars!")
                else:
                    myfeeds = Book(title=MY_FEEDS_TITLE, description=MY_FEEDS_DESC,
                        builtin=False, keep_image=True, oldest_article=7, 
                        needs_subscription=False, separate=False)
                    myfeeds.put()
                    au = KeUser(name=u, passwd=pwd, kindle_email='', enable_send=False,
                        send_time=7, timezone=TIMEZONE, book_type="mobi",
                        ownfeeds=myfeeds, merge_books=False, secret_key=secret_key, expiration_days=expiration)
                    if expiration:
                        au.expires = datetime.datetime.utcnow() + datetime.timedelta(days=expiration)

                    au.put()
                    users = KeUser.all() if user.name == 'admin' else None
                    tips = _("Add a account success!")
            return self.render('admin.html', "Admin", current='admin', user=user, users=users, actips=tips)
        else:
            return self.GET()

class AdminMgrPwd(BaseHandler):
    __url__ = "/mgrpwd/(.*)"
    # 管理员修改其他账户的密码
    def GET(self, name):
        self.login_required('admin')
        tips = _("Please input new password to confirm!")
        return self.render('adminmgrpwd.html', "Change password", tips=tips, username=name)
        
    def POST(self, _n=None):
        self.login_required('admin')
        name, p1, p2 = web.input().get('u'), web.input().get('p1'), web.input().get('p2')
        if name:
            u = KeUser.all().filter("name = ", name).get()
            if not u:
                tips = _("The username '%s' not exist!") % name
            elif p1 != p2:
                tips = _("The two new passwords are dismatch!")
            else:
                secret_key = u.secret_key or ''
                try:
                    pwd = hashlib.md5(p1 + secret_key).hexdigest()
                except:
                    tips = _("The password includes non-ascii chars!")
                else:
                    u.passwd = pwd
                    u.put()
                    strBackPage = '&nbsp;&nbsp;&nbsp;&nbsp;<a href="%s">Click here to go back</a>' % Admin.__url__
                    tips = _("Change password success!") + strBackPage
        else:
            tips = _("Username is empty!")
        
        return self.render('adminmgrpwd.html', "Change password", tips=tips, username=name)
        
class DelAccount(BaseHandler):
    __url__ = "/delaccount/(.*)"
    def GET(self, name):
        self.login_required()
        if main.session.username == 'admin' or (name and name == main.session.username):
            tips = _("Please confirm to delete the account!")
            return self.render('delaccount.html', "Delete account", tips=tips,username=name)
        else:
            raise web.seeother(r'/')
    
    def POST(self, _n=None):
        self.login_required()
        name = web.input().get('u')
        if name and (main.session.username == 'admin' or main.session.username == name):
            u = KeUser.all().filter("name = ", name).get()
            if not u:
                tips = _("The username '%s' not exist!") % name
            else:
                if u.ownfeeds:
                    for feed in list(u.ownfeeds.feeds):
                        feed.delete()
                    u.ownfeeds.delete()
                    
                #删掉白名单和过滤器
                whitelists = list(u.whitelist)
                urlfilters = list(u.urlfilter)
                for d in whitelists:
                    d.delete()
                for d in urlfilters:
                    d.delete()
                
                # 删掉订阅记录
                for book in Book.all():
                    if book.users and name in book.users:
                        book.users.remove(name)
                        book.put()
                
                #删掉推送记录
                db.delete(DeliverLog.all().filter('username = ', name))
                
                #删掉书籍登陆信息
                for subs_info in SubscriptionInfo.all().filter('user = ', u.key()):
                    subs_info.delete()
                
                u.delete()
                
                if main.session.username == name:
                    raise web.seeother('/logout')
                else:
                    raise web.seeother('/admin')
        else:
            tips = _("The username is empty or you dont have right to delete it!")
        return self.render('delaccount.html', "Delete account", tips=tips, username=name)