#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#账号管理页面

import hashlib, datetime
from operator import attrgetter
from flask import Blueprint, request, url_for, render_template, redirect, session, current_app as app
from flask_babel import gettext as _
from ..base_handler import *
from ..back_end.db_models import *
from ..utils import new_secret_key, str_to_int

bpAdmin = Blueprint('bpAdmin', __name__)

# 账户管理页面
@bpAdmin.route("/admin", endpoint='Admin')
@login_required()
def Admin():
    user = get_login_user()

    #只有管理员才能管理其他用户
    adminName = app.config['ADMIN_NAME']
    if user.name == adminName:
        users = sorted(KeUser.get_all(), key=attrgetter('created_time'))
        mailSrv = AppInfo.get_value(AppInfo.newUserMailService, 'admin')
        signupType = AppInfo.get_value(AppInfo.signupType, 'oneTimeCode')
        inviteCodes = AppInfo.get_value(AppInfo.inviteCodes, '')
        return render_template('admin.html', title='Admin', tab='admin', users=users, adminName=adminName,
            mailSrv=mailSrv, signupType=signupType, inviteCodes=inviteCodes, tips='')
    else:
        return render_template('change_password.html', tips='', tab='admin', user=user)

@bpAdmin.post("/admin", endpoint='AdminPost')
@login_required()
def AdminPost():
    user = get_login_user()
    #只有管理员才能管理其他用户
    adminName = app.config['ADMIN_NAME']
    if user.name != adminName:
        return redirect(url_for('bpAdmin.Admin'))

    mailSrv = request.form.get('sm_service')
    signupType = request.form.get('signup_type')
    inviteCodes = request.form.get('invite_codes', '')
    AppInfo.set_value(AppInfo.newUserMailService, mailSrv)
    AppInfo.set_value(AppInfo.signupType, signupType)
    AppInfo.set_value(AppInfo.inviteCodes, inviteCodes)
    users = sorted(KeUser.get_all(), key=attrgetter('created_time'))
    return render_template('admin.html', title='Admin', tab='admin', users=users, adminName=adminName,
            mailSrv=mailSrv, signupType=signupType, inviteCodes=inviteCodes, tips=_("Settings Saved!"))

#管理员添加一个账号
@bpAdmin.route("/account/add", endpoint='AdminAddAccount')
@login_required()
def AdminAddAccount():
    user = get_login_user()
    if user.name != app.config['ADMIN_NAME']:
        return redirect(url_for("bpLogin.Login"))
    else:
        return render_template('user_account.html', tips='', formTitle=_('Add account'), submitTitle=_('Add'), tab='admin')

@bpAdmin.post("/account/add", endpoint='AdminAddAccountPost')
@login_required()
def AdminAddAccountPost():
    user = get_login_user()
    if user.name != app.config['ADMIN_NAME']:
        tips = _("You do not have sufficient privileges.")
        return render_template('user_account.html', tips=tips, formTitle=_('Add account'), submitTitle=_('Add'), tab='admin')
    
    form = request.form
    username = form.get('username')
    password1 = form.get('password1')
    password2 = form.get('password2')
    email = form.get('email')
    sm_service = form.get('sm_service')
    expiration = str_to_int(form.get('expiration', '0'))

    specialChars = ['<', '>', '&', '\\', '/', '%', '*', '.', '{', '}', ',', ';', '|', ' ']
    tips = ''
    if not all([username, password1, password2, email, sm_service]):
        tips = _("Some parameters are missing or wrong.")
    elif any([char in username for char in specialChars]):
        tips = _("The username includes unsafe chars.")
    elif password1 != password2:
        tips = _("The two new passwords are dismatch.")
    elif KeUser.get_or_none(KeUser.name == username):
        tips = _("Already exist the username.")
    else:
        secret_key = new_secret_key()
        try:
            pwd = hashlib.md5((password1 + secret_key).encode()).hexdigest()
        except:
            tips = _("The password includes non-ascii chars.")
        else:
            send_mail_service = {'service': 'admin'} if sm_service == 'admin' else {}
            user = KeUser(name=username, passwd=pwd, timezone=app.config['TIMEZONE'], secret_key=secret_key, 
                expiration_days=expiration, share_links={'key': new_secret_key()},
                email=email, send_mail_service=send_mail_service)
            if expiration:
                user.expires = datetime.datetime.utcnow() + datetime.timedelta(days=expiration)
            user.save()
    if tips:
        return render_template('user_account.html', tips=tips, formTitle=_('Add account'), submitTitle=_('Add'), 
            user=None, tab='admin')
    else:
        return redirect(url_for('bpAdmin.Admin'))

#直接AJAX删除一个账号
@bpAdmin.post("/account/delete", endpoint='AdminDeleteAccountAjax')
@login_required(forAjax=True)
def AdminDeleteAccountAjax():
    user = get_login_user()
    adminName = app.config['ADMIN_NAME']
    name = request.form.get('name')
    if user.name != adminName or not name or name == adminName:
        return {'status': _("You do not have sufficient privileges.")}
    
    u = KeUser.get_or_none(KeUser.name == name)
    if not u:
        return {'status': _("The username '{}' does not exist.").format(name)}
    else:
        u.erase_traces() #删除账号订阅的书，白名单，过滤器等，就是完全的清理
        u.delete_instance()
        return {'status': 'ok'}
    
#修改密码，可能是修改自己的密码或管理员修改其他用户的密码
@bpAdmin.route("/account/change/<name>", endpoint='AdminAccountChange')
@login_required()
def AdminAccountChange(name):
    user = get_login_user()
    if user.name == name:
        return render_template('change_password.html', tips='', tab='admin', user=user)
    elif user.name == app.config['ADMIN_NAME']:
        u = KeUser.get_or_none(KeUser.name == name)
        if u:
            tips = _('The password will not be changed if the fields are empties.')
            return render_template('user_account.html', tips=tips, formTitle=_('Change account'), 
                submitTitle=_('Change'), user=u, tab='admin')
        else:
            return render_template('tipsback.html', title='error', urltoback=url_for('bpAdmin.Admin'), 
                tips=_("The username '{}' does not exist.").format(name))
    else:
        return render_template('tipsback.html', title='privileges', urltoback=url_for('bpAdmin.Admin'), 
            tips=_('You do not have sufficient privileges.'))

@bpAdmin.post("/account/change/<name>", endpoint='AdminAccountChangePost')
@login_required()
def AdminAccountChangePost(name):
    user = get_login_user()
    form = request.form
    username = form.get('username')
    orgpwd = form.get('orgpwd')
    p1 = form.get('password1')
    p2 = form.get('password2')
    email = form.get('email')
    u = None
    if name != username:
        return render_template('tipsback.html', title='error', urltoback=url_for('bpAdmin.Admin'), 
            tips=_('Some parameters are missing or wrong.'))
    elif user.name == name: #修改自己的密码
        tips = ChangePassword(user, orgpwd, p1, p2, email)
        return render_template('change_password.html', tips=tips, tab='admin', user=user)
    elif user.name == app.config['ADMIN_NAME']: #管理员修改其他账号
        email = form.get('email', '')
        sm_service = form.get('sm_service')
        expiration = str_to_int(form.get('expiration', '0'))

        u = KeUser.get_or_none(KeUser.name == username)
        if not u:
            tips = _("The username '{}' does not exist.").format(username)
        elif (p1 or p2) and (p1 != p2):
            tips = _("The two new passwords are dismatch.")
        else:
            try:
                if p1 or p2:
                    u.passwd = hashlib.md5((p1 + u.secret_key).encode()).hexdigest()
            except:
                tips = _("The password includes non-ascii chars.")
            else:
                u.expiration_days = expiration
                if expiration:
                    u.expires = datetime.datetime.utcnow() + datetime.timedelta(days=expiration)
                else:
                    u.expires = None
                if sm_service == 'admin':
                    u.send_mail_service = {'service': 'admin'}
                elif u.send_mail_service.get('service', 'admin') == 'admin':
                    send_mail_service = user.send_mail_service
                    send_mail_service['service'] = ''
                    u.send_mail_service = send_mail_service
                u.email = email
                u.save()
                tips = _("Change success.")
    
    return render_template('user_account.html', tips=tips, formTitle=_('Change account'), 
        submitTitle=_('Change'), user=u, tab='admin')

#修改一个账号的密码，返回执行结果字符串
def ChangePassword(user, orgPwd, p1, p2, email):
    secret_key = user.secret_key
    try:
        oldPwd = hashlib.md5((orgPwd + secret_key).encode()).hexdigest()
        newPwd = hashlib.md5((p1 + secret_key).encode()).hexdigest()
    except:
        tips = _("The password includes non-ascii chars.")
    else:
        if not all((orgPwd, p1, p2, email)):
            tips = _("The username or password is empty.")
        elif user.passwd != oldPwd:
            tips = _("The old password is wrong.")
        elif p1 != p2:
            tips = _("The two new passwords are dismatch.")
        else:
            user.passwd = newPwd
            user.email = email
            user.save()
            tips = _("Change password success.")
    return tips
