#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#登录页面

import hashlib, datetime, time
from flask import Blueprint, url_for, render_template, redirect, session
from flask_babel import gettext as _
from apps.base_handler import *
from apps.back_end.db_models import *
from apps.utils import new_secret_key
from config import *

bpLogin = Blueprint('bpLogin', __name__)

@bpLogin.route("/login")
def Login():
    # 第一次登陆时如果没有管理员帐号，
    # 则增加一个管理员帐号 ADMIN_NAME，密码 ADMIN_NAME，后续可以修改密码
    tips = ''
    if InitialAdminAccount():
        tips = (_("Please input username and password."))
    else:
        tips = (_("Please use {}/{} to login at first time.").format(ADMIN_NAME, ADMIN_NAME))
    
    if session.get('login') == 1:
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
    
    u = KeUser.get_one(KeUser.name == name)
    if u:
        secret_key = u.secret_key or ''
        pwdhash = hashlib.md5((passwd + secret_key).encode()).hexdigest()
        if u.passwd != pwdhash:
            u = None
    
    if u:
        session['login'] = 1
        session['userName'] = name
        session['role'] = 'admin' if name == ADMIN_NAME else 'user'
        if u.expires and u.expiration_days > 0: #用户登陆后自动续期
            days = u.expiration_days
            u.expires = datetime.datetime.utcnow() + datetime.timedelta(days=days)
            u.save()
        
        #return redirect(url_for("bpSubscribe.MySubscription") if u.kindle_email else url_for("bpSetting.Setting"))
        return redirect(url_for("bpSetting.Setting"))
    else:  #账号或密码错
        time.sleep(5) #防止暴力破解
        tips = _("The username not exist or password is wrong!")
        lang = session.get('langCode', '')
        if lang.startswith('zh'):
            tips += '<br/><a href="/static/faq.html#forgotpwd" target="_blank">' + _('Forgot password?') + '</a>'
        else:
            tips += '<br/><a href="/static/faq_en.html#forgotpwd" target="_blank">' + _('Forgot password?') + '</a>'
        
        session['login'] = 0
        session['userName'] = ''
        session['role'] = ''
        return render_template('login.html', userName=name, tips=tips)

#判断管理员账号是否存在
#如果管理员账号不存在，创建一个，并返回False，否则返回True
def InitialAdminAccount():
    u = KeUser.get_all(KeUser.name == ADMIN_NAME)
    if u:
        return True

    myFeeds = Book(title="KindleEar", description="RSS from KindleEar", builtin=False, 
            keep_image=True, oldest_article=7, needs_subscription=False, separate=False)
    myFeeds.save()
    secretKey = new_secret_key()
    shareKey = new_secret_key()
    password = hashlib.md5((ADMIN_NAME + secretKey).encode()).hexdigest()
    au = KeUser(name=ADMIN_NAME, passwd=password, kindle_email='', enable_send=False, send_time=8, 
        timezone=TIMEZONE, book_type="epub", device='kindle', expires=None, merge_books=False, 
        own_feeds=myFeeds.reference_key_or_id, secret_key=secretKey, expiration_days=0, share_key=shareKey)
    au.save()
    return False

@bpLogin.route("/logout")
def Logout():
    session['login'] = 0
    session['userName'] = ''
    session['role'] = ''
    return redirect('/')

#for ajax parser, if login required, retuan a dict 
@bpLogin.route("/needloginforajax")
def NeedLoginAjax():
    return {'status': _('login required')}

