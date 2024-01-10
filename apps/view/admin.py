#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#账号管理页面

import hashlib, datetime

from bottle import route, post, redirect

from apps.base_handler import *
from apps.db_models import *
from apps.utils import new_secret_key, str_to_int

from config import *

# 账户管理页面
@route("/admin")
def Admin():
    user = get_current_user()

    #只有管理员才能管理其他用户
    users = KeUser.all() if user.name == ADMIN_NAME else None
    return render_page('admin.html', 'Admin', current=ADMIN_NAME, user=user, users=users)

@post("/admin")
def AdminPost(self):
    forms = request.forms
    u, up1, up2 = forms.u, forms.up1, forms.up2
    expiration = str_to_int(forms.get('expiration', '0'))
    op, p1, p2 = forms.op, forms.p1, forms.p2
    user = get_current_user()
    users = KeUser.all() if user.name == ADMIN_NAME else None
    
    if all((op, p1, p2)): #修改当前登陆账号的密码
        secret_key = user.secret_key or ''
        try:
            pwd = hashlib.md5((op + secret_key).encode()).hexdigest()
            newpwd = hashlib.md5((p1 + secret_key).encode()).hexdigest()
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
        return render_page('admin.html', "Admin", current=ADMIN_NAME, user=user, users=users, chpwdtips=tips)
    elif all((u, up1, up2)): #添加账户
        if user.name != ADMIN_NAME:
            redirect('/')
        elif not u:
            tips = _("Username is empty!")
        elif up1 != up2:
            tips = _("The two new passwords are dismatch!")
        elif KeUser.all().filter("name = ", u).get():
            tips = _("Already exist the username!")
        else:
            secret_key = new_secret_key()
            try:
                pwd = hashlib.md5((up1 + secret_key).encode()).hexdigest()
            except:
                tips = _("The password includes non-ascii chars!")
            else:
                myfeeds = Book(title="KindleEar", description="RSS from KindleEar",
                    builtin=False, keep_image=True, oldest_article=7, 
                    needs_subscription=False, separate=False)
                myfeeds.put()
                au = KeUser(name=u, passwd=pwd, kindle_email='', enable_send=False,
                    send_time=7, timezone=TIMEZONE, book_type="epub",
                    own_feeds=myfeeds, merge_books=False, secret_key=secret_key, expiration_days=expiration)
                if expiration:
                    au.expires = datetime.datetime.utcnow() + datetime.timedelta(days=expiration)

                au.put()
                users = KeUser.all() if user.name == ADMIN_NAME else None
                tips = _("Add a account success!")
        return render_page('admin.html', "Admin", current=ADMIN_NAME, user=user, users=users, actips=tips)
    else:
        return Admin()

#管理员修改其他账户的密码
@route("/mgrpwd/<name>")
def AdminManagePassword(name):
    login_required(ADMIN_NAME)
    u = KeUser.all().filter("name = ", name).get()
    expiration = 0
    if not u:
        tips = _("The username '{}' not exist!").format(name)
    else:
        tips = _("Please input new password to confirm!")
        expiration = u.expiration_days

    return render_page('adminmgrpwd.html', "Change password", tips=tips, username=name, expiration=expiration)

@post("/mgrpwd/<name>")
def AdminManagePasswordPost(name=None):
    login_required(ADMIN_NAME)
    forms = request.forms
    name, p1, p2 = forms.u, forms.p1, forms.p2
    expiration = str_to_int(forms.get('ep', '0'))

    if name:
        u = KeUser.all().filter("name = ", name).get()
        if not u:
            tips = _("The username '{}' not exist!").format(name)
        elif p1 != p2:
            tips = _("The two new passwords are dismatch!")
        else:
            secret_key = u.secret_key or ''
            try:
                pwd = hashlib.md5((p1 + secret_key).encode()).hexdigest()
            except:
                tips = _("The password includes non-ascii chars!")
            else:
                u.passwd = pwd
                u.expiration_days = expiration
                if expiration:
                    u.expires = datetime.datetime.utcnow() + datetime.timedelta(days=expiration)
                else:
                    u.expires = None
                u.put()
                strBackPage = '&nbsp;&nbsp;&nbsp;&nbsp;<a href="/admin">Click here to go back</a>'
                tips = _("Change password success!") + strBackPage
    else:
        tips = _("Username is empty!")
    
    return render_page('adminmgrpwd.html', "Change password", tips=tips, username=name)
        
#删除一个账号
@route("/delaccount/<name>")
def DelAccount(name):
    session = login_required()
    if (session.userName == ADMIN_NAME) or (name and name == session.userName):
        tips = _("Please confirm to delete the account!")
        return render_page('delaccount.html', "Delete account", tips=tips, username=name)
    else:
        redirect('/')

@post("/delaccount/<name>")
def DelAccountPost(name=None):
    session = login_required()
    name = request.forms.u
    if name and (name == ADMIN_NAME) and (session.userName in (ADMIN_NAME, name)):
        u = KeUser.all().filter("name = ", name).get()
        if not u:
            tips = _("The username '{}' not exist!").format(name)
        else:
            if u.own_feeds:
                for feed in list(u.own_feeds.feeds):
                    feed.delete()
                u.own_feeds.delete()
                
            #删掉白名单和过滤器
            whiteLists = list(u.white_list)
            urlFilters = list(u.url_filter)
            for d in whiteLists:
                d.delete()
            for d in urlFilters:
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
            
            if session.username == name:
                redirect('/logout')
            else:
                redirect('/admin')
    else:
        tips = _("The username is empty or you dont have right to delete it!")
    return render_page('delaccount.html', "Delete account", tips=tips, username=name)
