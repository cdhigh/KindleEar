#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#登录页面

import hashlib, datetime, time
from flask import Blueprint, url_for, render_template, redirect, session
from apps.base_handler import *
from apps.back_end.db_models import *
from books import BookClasses, BookClass
from apps.utils import new_secret_key
from config import *

bpLogin = Blueprint('bpLogin', __name__)

@bpLogin.route("/login")
def Login():
    # 第一次登陆时如果没有管理员帐号，
    # 则增加一个管理员帐号 ADMIN_NAME，密码 ADMIN_NAME，后续可以修改密码
    tips = ''
    if InitialAdminAccount():
        tips = _("Please input username and password.")
    else:
        tips = _("Please use {}/{} to login at first time.").format(ADMIN_NAME, ADMIN_NAME)
    
    if session.login == 1:
        return redirect('/')
    else:
        return render_template('login.html', tips=tips)

@bpLogin.post("/login")
def LoginPost():
    name = request.form.get('u', '').strip()
    passwd = request.form.get('p', '')
    specialChars = ['<', '>', '&', '\\', '/', '%', '*', '.', '{', '}', ',', ';', '|']
    tips = ''
    if not name:
        tips = _("Username is empty!")
    elif len(name) > 25:
        tips = _("The len of username reached the limit of 25 chars!")
    elif any([char in name for char in specialChars]):
        tips = _("The username includes unsafe chars!")

    if tips:
        return render_template('login.html', tips=tips)
    
    InitialAdminAccount() #确认管理员账号是否存在
    
    u = KeUser.all().filter("name = ", name).get()
    if u:
        secret_key = u.secret_key or ''
        pwdhash = hashlib.md5((passwd + secret_key).encode()).hexdigest()
        if u.passwd != pwdhash:
            u = None
            
    if u:
        session.login = 1
        session.userName = name
        session.role = 'admin' if name == ADMIN_NAME else 'user'
        if u.expires and u.expiration_days > 0: #用户登陆后自动续期
            days = u.expiration_days
            u.expires = datetime.datetime.utcnow() + datetime.timedelta(days=days)
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
        
        return redirect(url_for("MySubscription") if u.kindle_email else url_for("/setting"))
    else:  #账号或密码错
        time.sleep(5) #防止暴力破解
        tips = _("The username not exist or password is wrong!")
        lang = session.get('langCode', '')
        if lang.startswith('zh'):
            tips += '&nbsp;&nbsp;&nbsp;&nbsp;<a href="/static/faq.html#forgotpwd" target="_blank">' + _('Forgot password?') + '</a>'
        else:
            tips += '&nbsp;&nbsp;&nbsp;&nbsp;<a href="/static/faq_en.html#forgotpwd" target="_blank">' + _('Forgot password?') + '</a>'
        session.login = 0
        session.userName = ''
        session.role = ''
        return render_template('login.html', tips=tips, userName=name)

#判断管理员账号是否存在
#如果管理员账号不存在，创建一个，并返回False，否则返回True
def InitialAdminAccount():
    u = KeUser.all().filter("name = ", ADMIN_NAME).get()
    if u:
        return True

    myFeeds = Book(title="KindleEar", description="RSS from KindleEar", builtin=False, 
            keep_image=True, oldest_article=7, needs_subscription=False, separate=False)
    myFeeds.put()
    secretKey = new_secret_key()
    password = hashlib.md5((ADMIN_NAME + secretKey).encode()).hexdigest()
    au = KeUser(name=ADMIN_NAME, passwd=password, kindle_email='', enable_send=False, 
        send_time=8, timezone=TIMEZONE, book_type="epub", device='kindle', expires=None, 
        own_feeds=myFeeds, merge_books=False, secret_key=secretKey, expiration_days=0)
    au.put()
    return False

@bpLogin.route("/logout")
def Logout(self):
    session.login = 0
    session.userName = ''
    session.role = ''
    return redirect('/')

#for ajax parser, if login required, retuan a dict 
@bpLogin.route("/needloginforajax")
def NeedLoginAjax():
    return {'status': _('login required')}

