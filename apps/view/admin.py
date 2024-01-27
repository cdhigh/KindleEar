#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#账号管理页面

import hashlib, datetime
from flask import Blueprint, request, url_for, render_template, redirect, session
from flask_babel import gettext as _
from apps.base_handler import *
from apps.back_end.db_models import *
from apps.utils import new_secret_key, str_to_int
from config import *

bpAdmin = Blueprint('bpAdmin', __name__)

# 账户管理页面
@bpAdmin.route("/admin", endpoint='Admin')
@login_required()
def Admin():
    user = get_login_user()

    #只有管理员才能管理其他用户
    users = KeUser.get_all() if user.name == ADMIN_NAME else None
    return render_template('admin.html', title='Admin', tab='admin', user=user, users=users, admin_name=ADMIN_NAME)

@bpAdmin.post("/admin/<actType>", endpoint='AdminPost')
@login_required()
def AdminPost(actType):
    form = request.form
    user = get_login_user()
    users = KeUser.get_all() if user.name == ADMIN_NAME else None
    
    if actType == 'change': #修改当前登陆账号的密码
        oldPassword = form.get('op')
        newP1 = form.get('p1')
        newP2 = form.get('p2')
        secret_key = user.secret_key or ''
        try:
            pwd = hashlib.md5((oldPassword + secret_key).encode()).hexdigest()
            newPwd = hashlib.md5((newP1 + secret_key).encode()).hexdigest()
        except:
            tips = _("The password includes non-ascii chars.")
        else:
            if not all((oldPassword, newP1, newP2)):
                tips = _("The username or password is empty.")
            elif user.passwd != pwd:
                tips = _("Old password is wrong.")
            elif newP1 != newP2:
                tips = _("The two new passwords are dismatch.")
            else:
                tips = 'ok'
                user.passwd = newPwd
                user.save()
        return {'status': tips}
    elif actType == 'add': #添加账户
        userName = form.get('u')
        password1 = form.get('up1')
        password2 = form.get('up2')
        expiration = str_to_int(form.get('expiration', '0'))

        specialChars = ['<', '>', '&', '\\', '/', '%', '*', '.', '{', '}', ',', ';', '|']
        if user.name != ADMIN_NAME: #只有管理员能添加账号
            return redirect('/')
        elif not all((userName, password1, password2)):
            tips = _("The username or password is empty.")
        elif any([char in user.name for char in specialChars]):
            tips = _("The username includes unsafe chars.")
        elif password1 != password2:
            tips = _("The two new passwords are dismatch.")
        elif KeUser.get_one(KeUser.name == userName):
            tips = _("Already exist the username.")
        else:
            secret_key = new_secret_key()
            try:
                pwd = hashlib.md5((password1 + secret_key).encode()).hexdigest()
            except:
                tips = _("The password includes non-ascii chars.")
            else:
                au = KeUser(name=userName, passwd=pwd, kindle_email='', enable_send=False,
                    send_time=7, timezone=TIMEZONE, book_type="epub", merge_books=False, 
                    secret_key=secret_key, expiration_days=expiration, share_key=new_secret_key(),
                    book_title='KindleEar', book_language='en')
                if expiration:
                    au.expires = datetime.datetime.utcnow() + datetime.timedelta(days=expiration)

                au.save()
                users = KeUser.get_all() if user.name == ADMIN_NAME else None
                tips = _("Add a account success.")
        return render_template('admin.html', tab='admin', user=user, users=users, actips=tips)
    elif actType == 'delete': #删除账号，使用ajax请求的，返回一个字典
        name = form.get('name')
        if name and (name != ADMIN_NAME) and (session.get('userName') in (ADMIN_NAME, name)):
            u = KeUser.get_one(KeUser.name == name)
            if not u:
                return {'status': _("The username '{}' does not exist.").format(name)}
            else:
                u.erase_traces() #删除自己订阅的书，白名单，过滤器等，就是完全的清理
                u.delete_instance()
                return {'status': 'ok'}
        else:
            return {'status': _("The username is empty or you dont have right to delete it.")}
    else: #静悄悄的失败:)
        return Admin()

#管理员修改其他账户的密码
@bpAdmin.route("/mgrpwd/<name>", endpoint='AdminManagePassword')
@login_required(ADMIN_NAME)
def AdminManagePassword(name):
    u = KeUser.get_one(KeUser.name == name)
    expiration = 0
    if not u:
        tips = _("The username '{}' does not exist.").format(name)
    else:
        tips = _("Please input new password to confirm.")
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
    tips = _("Username is empty.")

    if name and name != ADMIN_NAME:
        u = KeUser.get_one(KeUser.name == name)
        if not u:
            tips = _("The username '{}' does not exist.").format(name)
        elif p1 != p2:
            tips = _("The two new passwords are dismatch.")
        else:
            secret_key = u.secret_key or ''
            try:
                pwd = hashlib.md5((p1 + secret_key).encode()).hexdigest()
            except:
                tips = _("The password includes non-ascii chars.")
            else:
                u.passwd = pwd
                u.expiration_days = expiration
                if expiration:
                    u.expires = datetime.datetime.utcnow() + datetime.timedelta(days=expiration)
                else:
                    u.expires = None
                u.save()
                strBackPage = '&nbsp;&nbsp;&nbsp;&nbsp;<a href="/admin">Click here to go back</a>'
                tips = _("Change password success.") + strBackPage
    
    return render_template('adminmgrpwd.html', tips=tips, userName=name)

#实际删除一个账号
def DelAccountPost(name):
    name = request.form.get('u')
    if (name != ADMIN_NAME) and (session.get('userName') in (ADMIN_NAME, name)):
        u = KeUser.get_one(KeUser.name == name)
        if not u:
            tips = _("The username '{}' does not exist.").format(name)
        else:
            u.erase_traces() #删除自己订阅的书，白名单，过滤器等，就是完全的清理
            u.delete_instance()
            return redirect(url_for("bpLogin.Logout") if session.get('userName') == name else url_for("bpAdmin.Admin"))
    else:
        tips = _("The username is empty or you dont have right to delete it.")
    return render_template('delaccount.html', tips=tips, userName=name)
