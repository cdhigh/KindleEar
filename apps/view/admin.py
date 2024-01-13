#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#账号管理页面

import hashlib, datetime
from flask import Blueprint, request, url_for, render_template, redirect, session
from apps.base_handler import *
from apps.back_end.db_models import *
from apps.utils import new_secret_key, str_to_int
from config import *

bpAdmin = Blueprint('bpAdmin', __name__)

# 账户管理页面
@bpAdmin.route("/admin", endpoint='Admin')
@login_required
def Admin():
    user = get_login_user()

    #只有管理员才能管理其他用户
    users = KeUser.all() if user.name == ADMIN_NAME else None
    return render_template('admin.html', title='Admin', tab='admin', user=user, users=users)

@bpAdmin.post("/admin", endpoint='AdminPost')
@login_required
def AdminPost():
    form = request.form
    userName = form.get('u') #用于添加账号
    password1 = form.get('up1')
    password2 = form.get('up2')
    oldPassword = form.get('op') #用于修改账号密码
    newP1 = form.get('p1')
    newP2 = form.get('p2')
    expiration = str_to_int(form.get('expiration', '0'))
    
    user = get_login_user()
    users = KeUser.all() if user.name == ADMIN_NAME else None
    
    if all((oldPassword, newP1, newP2)): #修改当前登陆账号的密码
        secret_key = user.secret_key or ''
        try:
            pwd = hashlib.md5((oldPassword + secret_key).encode()).hexdigest()
            newPwd = hashlib.md5((newP1 + secret_key).encode()).hexdigest()
        except:
            tips = _("The password includes non-ascii chars!")
        else:
            if user.passwd != pwd:
                tips = _("Old password is wrong!")
            elif newP1 != newP2:
                tips = _("The two new passwords are dismatch!")
            else:
                tips = _("Change password success!")
                user.passwd = newPwd
                user.put()
        return render_template('admin.html', tab='admin', user=user, users=users, chpwdtips=tips)
    elif all((userName, password1, password2)): #添加账户
        specialChars = ['<', '>', '&', '\\', '/', '%', '*', '.', '{', '}', ',', ';', '|']
        if user.name != ADMIN_NAME: #只有管理员能添加账号
            return redirect('/')
        elif any([char in name for char in specialChars]):
            tips = _("The username includes unsafe chars!")
        elif password1 != password2:
            tips = _("The two new passwords are dismatch!")
        elif KeUser.all().filter("name = ", userName).get():
            tips = _("Already exist the username!")
        else:
            secret_key = new_secret_key()
            try:
                pwd = hashlib.md5((password1 + secret_key).encode()).hexdigest()
            except:
                tips = _("The password includes non-ascii chars!")
            else:
                myfeeds = Book(title="KindleEar", description="RSS from KindleEar",
                    builtin=False, keep_image=True, oldest_article=7, 
                    needs_subscription=False, separate=False)
                myfeeds.put()
                au = KeUser(name=userName, passwd=pwd, kindle_email='', enable_send=False,
                    send_time=7, timezone=TIMEZONE, book_type="epub",
                    own_feeds=myfeeds, merge_books=False, secret_key=secret_key, expiration_days=expiration)
                if expiration:
                    au.expires = datetime.datetime.utcnow() + datetime.timedelta(days=expiration)

                au.put()
                users = KeUser.all() if user.name == ADMIN_NAME else None
                tips = _("Add a account success!")
        return render_template('admin.html', tab='admin', user=user, users=users, actips=tips)
    else:
        return Admin()

#管理员修改其他账户的密码
@bpAdmin.route("/mgrpwd/<name>", endpoint='AdminManagePassword')
@login_required(ADMIN_NAME)
def AdminManagePassword(name):
    u = KeUser.all().filter("name = ", name).get()
    expiration = 0
    if not u:
        tips = _("The username '{}' not exist!").format(name)
    else:
        tips = _("Please input new password to confirm!")
        expiration = u.expiration_days

    return render_template('adminmgrpwd.html', tips=tips, userName=name, expiration=expiration)

@bpAdmin.post("/mgrpwd/<name>", endpoint='AdminManagePasswordPost')
@login_required(ADMIN_NAME)
def AdminManagePasswordPost(name):
    form = request.form
    name = form.get('name')
    p1 = form.get('p1')
    p2 = form.get('p2')
    expiration = str_to_int(form.get('ep', '0'))
    tips = _("Username is empty!")

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
    
    return render_template('adminmgrpwd.html', tips=tips, userName=name)
    
#删除一个账号
@bpAdmin.route("/delaccount/<name>", endpoint='DelAccount')
@login_required
def DelAccount(name):
    if (name != ADMIN_NAME) and (session.userName in (ADMIN_NAME, name)):
        tips = _("Please confirm to delete the account!")
        return render_template('delaccount.html', tips=tips, userName=name)
    else:
        return redirect('/')

@bpAdmin.post("/delaccount/<name>", endpoint='DelAccountPost')
@login_required
def DelAccountPost(name):
    name = request.form.get('u')
    if (name != ADMIN_NAME) and (session.userName in (ADMIN_NAME, name)):
        u = KeUser.all().filter("name = ", name).get()
        if not u:
            tips = _("The username '{}' not exist!").format(name)
        else:
            if u.own_feeds:
                for feed in list(u.own_feeds.feeds):
                    feed.delete()
                u.own_feeds.delete()
                
            #删掉白名单和过滤器
            for d in list(u.white_list):
                d.delete()
            for d in list(u.url_filter):
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
            
            return redirect(url_for("Logout") if session.userName == name else url_for("Admin"))
    else:
        tips = _("The username is empty or you dont have right to delete it!")
    return render_template('delaccount.html', tips=tips, userName=name)
