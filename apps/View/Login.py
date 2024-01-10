#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#登录页面

import hashlib, datetime, time
import json
from bottle import route, post, redirect
from apps.base_handler import *
from apps.db_models import *
from books import BookClasses, BookClass
from apps.utils import new_secret_key
from config import *

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
    
@route("/login")
def Login():
    # 第一次登陆时如果没有管理员帐号，
    # 则增加一个管理员帐号 ADMIN_NAME，密码 ADMIN_NAME，后续可以修改密码
    tips = ''
    if InitialAdminAccount():
        tips = _("Please input username and password.")
    else:
        tips = _("Please use {}/{} to login at first time.".format(ADMIN_NAME, ADMIN_NAME))
    
    if current_session().login == 1:
        redirect('/')
    else:
        return render_page('login.html', "Login", tips=tips)

@post("/login")
def LoginPost():
    name = request.forms.u.strip()
    passwd = request.forms.p
    specialChars = ['<', '>', '&', '\\', '/', '%', '*', '.', '{', '}']
    if not name:
        tips = _("Username is empty!")
        return self.render('login.html', "Login", nickname='', tips=tips)
    elif len(name) > 25:
        tips = _("The len of username reached the limit of 25 chars!")
        return render_page('login.html', "Login", nickname='', tips=tips, username=name)
    elif any(char in name for char in specialChars):
        tips = _("The username includes unsafe chars!")
        return render_page('login.html', "Login", nickname='', tips=tips)
    
    session = current_session()
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
        session.save()
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
        
        if u.kindle_email:
            redirect('/my')
        else:
            redirect('/setting')
    else:  #账号或密码错
        time.sleep(5) #防止暴力破解
        tips = _("The username not exist or password is wrong!")
        lang = session..lang
        if lang and lang.startswith('zh'):
            tips += '&nbsp;&nbsp;&nbsp;&nbsp;<a href="/static/faq.html#forgotpwd" target="_blank">' + _('Forgot password?') + '</a>'
        else:
            tips += '&nbsp;&nbsp;&nbsp;&nbsp;<a href="/static/faq_en.html#forgotpwd" target="_blank">' + _('Forgot password?') + '</a>'
        session.login = 0
        session.userName = ''
        session.save()
        return render_page('login.html', "Login", nickname='', tips=tips, username=name)

@route("/logout")
def Logout(self):
    session = current_session()
    session.login = 0
    session.userName = ''
    session.lang = ''
    session.save()
    redirect('/')

#for ajax parser, if login required, retuan a dict 
@route("/needloginforajax")
def NeedLoginAjax():
    response.content_type = 'application/json'
    return json.dumps({'status': _('login required')})
