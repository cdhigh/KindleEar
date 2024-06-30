#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#账号管理页面
#Author: cdhigh <https://github.com/cdhigh>
import datetime
from operator import attrgetter
from flask import Blueprint, request, url_for, render_template, redirect, current_app as app
from flask_babel import gettext as _
from ..base_handler import *
from ..back_end.db_models import *
from ..utils import str_to_int
from .login import CreateAccountIfNotExist

bpAdmin = Blueprint('bpAdmin', __name__)

# 账户管理页面
@bpAdmin.route("/admin", endpoint='Admin')
@login_required()
def Admin(user: KeUser):
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
        return render_template('change_password.html', tips='', tab='admin', user=user, shareKey=user.share_links.get('key'))

@bpAdmin.post("/admin", endpoint='AdminPost')
@login_required()
def AdminPost(user: KeUser):
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
def AdminAddAccount(user: KeUser):
    if user.name != app.config['ADMIN_NAME']:
        return redirect(url_for("bpLogin.Login"))
    else:
        return render_template('user_account.html', tips='', formTitle=_('Add account'), submitTitle=_('Add'), tab='admin')

@bpAdmin.post("/account/add", endpoint='AdminAddAccountPost')
@login_required()
def AdminAddAccountPost(user: KeUser):
    if user.name != app.config['ADMIN_NAME']:
        tips = _("You do not have sufficient privileges.")
        return render_template('user_account.html', tips=tips, formTitle=_('Add account'), submitTitle=_('Add'), tab='admin')
    
    form = request.form
    username = form.get('username', '')
    password1 = form.get('password1', '')
    password2 = form.get('password2', '')
    email = form.get('email', '')
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
        sm_service = {'service': 'admin'} if sm_service == 'admin' else {}
        sender = user.cfg('email') if sm_service else email #和管理员一致则邮件发件地址也一致
        if not CreateAccountIfNotExist(username, password1, email, sender, sm_service, expiration):
            tips = _("The password includes non-ascii chars.")

    if tips:
        return render_template('user_account.html', tips=tips, formTitle=_('Add account'), submitTitle=_('Add'), 
            user=None, tab='admin')
    else:
        return redirect(url_for('bpAdmin.Admin'))

#直接AJAX删除一个账号
@bpAdmin.post("/account/delete", endpoint='AdminDeleteAccountAjax')
@login_required(forAjax=True)
def AdminDeleteAccountAjax(user: KeUser):
    adminName = app.config['ADMIN_NAME']
    name = request.form.get('name', '')
    if (user.name != adminName) or not name or (name == adminName):
        return {'status': _("You do not have sufficient privileges.")}
    
    dbItem = KeUser.get_or_none(KeUser.name == name)
    if not dbItem:
        return {'status': _("The username '{}' does not exist.").format(name)}
    else:
        dbItem.erase_traces() #删除账号订阅的书，白名单，过滤器等，完全的清理其痕迹
        dbItem.delete_instance()
        return {'status': 'ok'}

#修改自己的密码
@bpAdmin.route("/account/change", endpoint='AdminAccountChangeSelf')
@login_required()
def AdminAccountChangeSelf(user: KeUser):
    return redirect(url_for('bpAdmin.AdminAccountChange', name=user.name), code=307)

#修改密码，可能是修改自己的密码或管理员修改其他用户的密码
@bpAdmin.route("/account/change/<name>", endpoint='AdminAccountChange')
@login_required()
def AdminAccountChange(name: str, user: KeUser):
    tips = _('The password will not be changed if the fields are empties.')
    if user.name == name: #修改自己的密码和一些设置
        return render_template('change_password.html', tips=tips, tab='admin', user=user, shareKey=user.share_links.get('key'))
    elif user.name == app.config['ADMIN_NAME']: #管理员修改其他人的密码和其他设置
        dbItem = KeUser.get_or_none(KeUser.name == name)
        if dbItem:
            return render_template('user_account.html', tips=tips, formTitle=_('Edit account'), 
                submitTitle=_('Change'), user=dbItem, tab='admin')
        else:
            tips=_("The username '{}' does not exist.").format(name)
            return render_template('tipsback.html', title='error', urltoback=url_for('bpAdmin.Admin'), tips=tips)
    else:
        tips=_('You do not have sufficient privileges.')
        return render_template('tipsback.html', title='privileges', urltoback=url_for('bpAdmin.Admin'), tips=tips)

@bpAdmin.post("/account/change/<name>", endpoint='AdminAccountChangePost')
@login_required()
def AdminAccountChangePost(name: str, user: KeUser):
    form = request.form
    username = form.get('username')
    orgPwd = form.get('orgpwd', '')
    p1 = form.get('password1', '')
    p2 = form.get('password2', '')
    email = form.get('email')
    shareKey = form.get('shareKey')
    dbItem = None
    tips = ''
    if name != username:
        return render_template('tipsback.html', title='error', urltoback=url_for('bpAdmin.Admin'), 
            tips=_('Some parameters are missing or wrong.'))
    elif user.name == name: #修改自己的密码
        tips = ChangePassword(user, orgPwd, p1, p2, email, shareKey)
        return render_template('change_password.html', tips=tips, tab='admin', user=user, shareKey=user.share_links.get('key'))
    elif user.name == app.config['ADMIN_NAME']: #管理员修改其他账号
        email = form.get('email', '')
        smType = form.get('sm_service')
        expiration = str_to_int(form.get('expiration', '0'))

        dbItem = KeUser.get_or_none(KeUser.name == username)
        if not dbItem:
            tips = _("The username '{}' does not exist.").format(username)
        elif (p1 or p2) and (p1 != p2):
            tips = _("The two new passwords are dismatch.")
        else:
            if p1 and p2: #只有提供了两个密码才修改数据库中保存的密码
                dbItem.passwd_hash = dbItem.hash_text(p1)
            
            dbItem.expiration_days = expiration
            if expiration:
                dbItem.expires = datetime.datetime.utcnow() + datetime.timedelta(days=expiration)
            else:
                dbItem.expires = None
            if smType == 'admin':
                dbItem.send_mail_service = {'service': 'admin'}
            elif dbItem.send_mail_service.get('service') == 'admin': #从和管理员一致变更为独立设置
                dbItem.send_mail_service = {}
            dbItem.set_cfg('email', email)
            dbItem.save()
            tips = _("Change success.")
    
    return render_template('user_account.html', tips=tips, formTitle=_('Edit account'), 
        submitTitle=_('Change'), user=dbItem, tab='admin')

#修改一个账号的密码，返回执行结果字符串
def ChangePassword(user, orgPwd, p1, p2, email, shareKey):
    if not email or not shareKey:
        tips = _("Some parameters are missing or wrong.")
    elif p1 != p2:
        tips = _("The two new passwords are dismatch.")
    elif any((orgPwd, p1, p2)) and not user.verify_password(orgPwd):
        #如果不修改密码，则三个密码都必须为空，有任何一个不为空，都表示要修改密码
        tips = _("The old password is wrong.")
    else:
        tips = _("Changes saved successfully.")

        if any((orgPwd, p1, p2)):
            user.passwd_hash = user.hash_text(p1)
        user.set_cfg('email', email)
        shareLinks = user.share_links
        shareLinks['key'] = shareKey
        user.share_links = shareLinks
        if user.name == app.config['ADMIN_NAME']: #如果管理员修改email，也同步更新其他用户的发件地址
            user.set_cfg('sender', email)
            SyncSenderAddress(user)
        else: #其他人修改自己的email，根据设置确定是否要同步到发件地址
            sm_service = user.send_mail_service
            if not sm_service or sm_service.get('service', 'admin') != 'admin':
                user.set_cfg('sender', email)
                    
        user.save()
    return tips

#将管理员的email同步到所有用户
def SyncSenderAddress(adminUser):
    for user in list(KeUser.get_all(KeUser.name != app.config['ADMIN_NAME'])):
        sm_service = user.send_mail_service
        if sm_service and sm_service.get('service', 'admin') == 'admin':
            user.set_cfg('sender', adminUser.cfg('email'))
            user.save()
