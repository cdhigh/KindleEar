#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#登录页面

import hashlib, datetime, time, json
from urllib.parse import urljoin, urlencode
from flask import Blueprint, url_for, render_template, redirect, session, current_app as app
from flask_babel import gettext as _
from ..base_handler import *
from ..back_end.db_models import *
from ..back_end.send_mail_adpt import send_html_mail
from ..utils import new_secret_key, hide_email

bpLogin = Blueprint('bpLogin', __name__)

#账号名不允许的特殊字符
specialChars = ['<', '>', '&', '\\', '/', '%', '*', '.', '{', '}', ',', ';', '|', ' ']

@bpLogin.route("/login")
def Login():
    # 第一次登陆时如果没有管理员帐号，
    # 则增加一个管理员帐号 ADMIN_NAME，密码 ADMIN_NAME，后续可以修改密码
    tips = ''
    adminName = app.config['ADMIN_NAME']
    if CreateAccountIfNotExist(adminName):
        tips = (_("Please use {}/{} to login at first time.").format(adminName, adminName))
    
    return render_template('login.html', tips=tips)

@bpLogin.post("/login")
def LoginPost():
    name = request.form.get('username', '').strip()
    passwd = request.form.get('password', '')
    tips = ''
    if not name:
        tips = _("Username is empty.")
    elif len(name) > 25:
        tips = _("The len of username reached the limit of 25 chars.")
    elif any([char in name for char in specialChars]):
        tips = _("The username includes unsafe chars.")

    if tips:
        return render_template('login.html', tips=tips)
    
    adminName = app.config['ADMIN_NAME']
    isFirstTime = CreateAccountIfNotExist(adminName) #确认管理员账号是否存在
    
    u = KeUser.get_or_none(KeUser.name == name)
    if u:
        secret_key = u.secret_key or ''
        pwdhash = hashlib.md5((passwd + secret_key).encode()).hexdigest()
        if u.passwd != pwdhash:
            u = None
    
    if u:
        session['login'] = 1
        session['userName'] = name
        session['role'] = 'admin' if name == adminName else 'user'
        if u.expires and u.expiration_days > 0: #用户登陆后自动续期
            u.expires = datetime.datetime.utcnow() + datetime.timedelta(days=u.expiration_days)
            u.save()
        if 'resetpwd' in u.custom:
            custom = u.custom
            custom.pop('resetpwd', None)
            u.custom = custom
            u.save()
        
        if not u.sender:
            url = url_for('bpAdmin.AdminAccountChange', name=name)
        elif not u.kindle_email:
            url = url_for("bpSetting.Setting")
        else:
            url = url_for("bpSubscribe.MySubscription")
        default_log.info(f"Login event: {name}")
        return redirect(url)
    else:  #账号或密码错
        if isFirstTime:
            tips = (_("Please use {}/{} to login at first time.").format(adminName, adminName))
        else:
            time.sleep(5) #防止暴力破解
            tips = (_("The username does not exist or password is wrong.") +
                f'<br/><a href="/resetpwd?name={name}">' + _('Forgot password?') + '</a>')
        
        session.pop('login', None)
        session.pop('userName', None)
        session.pop('role', None)
        return render_template('login.html', userName=name, tips=tips)

#判断账号是否存在
#如果账号不存在，创建一个，并返回True，否则返回False
def CreateAccountIfNotExist(name, password=None, email='', sender=None, sm_service=None, expiration=0):
    if KeUser.get_or_none(KeUser.name == name):
        return False

    password = password if password else name
    secretKey = new_secret_key()
    shareKey = new_secret_key(length=4)
    try:
        password = hashlib.md5((password + secretKey).encode()).hexdigest()
    except Exception as e:
        default_log.warning('CreateAccountIfNotExist failed to hash password: {}'.format(str(e)))
        return False

    adminName = app.config['ADMIN_NAME']
    if sm_service is None:
        sm_service = {}
        if name != adminName and AppInfo.get_value(AppInfo.newUserMailService, 'admin') == 'admin':
            sm_service = {'service': 'admin'}
            if sender is None:
                adUser = KeUser.get_or_none(KeUser.name == adminName)
                sender = adUser.email if adUser else email

    sender = sender or email

    user = KeUser(name=name, passwd=password, expires=None, secret_key=secretKey, expiration_days=expiration, 
        share_links={'key': shareKey}, email=email, sender=sender, send_mail_service=sm_service)
    if expiration:
        user.expires = datetime.datetime.utcnow() + datetime.timedelta(days=expiration)
    user.save()
    return True

@bpLogin.route("/logout", methods=['GET', 'POST'])
def Logout():
    session.pop('login', None)
    session.pop('userName', None)
    session.pop('role', None)
    return redirect('/')

#for ajax parser, if login required, retuan a dict 
@bpLogin.route("/needloginforajax")
def NeedLoginAjax():
    return {'status': _('login required')}

#忘记密码后用于重设密码
@bpLogin.route("/resetpwd")
def ResetPasswordRoute():
    name = request.args.get('name')
    token = request.args.get('token')
    user = KeUser.get_or_none(KeUser.name == name) if name else None
    if user and token: #重设密码的最后一步
        pre_set = user.custom.get('resetpwd', {})
        now = datetime.datetime.utcnow().timestamp()
        pre_time = pre_set.get('expires') or (now - datetime.timedelta(hours=1)).timestamp()
        if (token == pre_set.get('token')) and (now < pre_time):
            return render_template('reset_password.html', tips='', userName=name, firstStep=False,
                token=token)
        else:
            tips = _('The token is wrong or expired.')
            return render_template('tipsback.html', tips=tips, urltoback=url_for('bpLogin.ResetPasswordRoute'))

    tips = [_('Please input the correct username and email to reset password.')]
    if user and user.email:
        tips.append(_("The email of account '{name}' is {email}.").format(name=name, 
            email=hide_email(user.email)))

    return render_template('reset_password.html', tips='<br/>'.join(tips), 
        userName=name, firstStep=True)

@bpLogin.post("/resetpwd")
def ResetPasswordPost():
    form = request.form
    name = form.get('username')
    email = form.get('email')
    token = form.get('token')
    new_p1 = form.get('new_p1')
    new_p2 = form.get('new_p2')
    user = KeUser.get_or_none(KeUser.name == name) if name else None
    if not user or not user.email:
        tips = _('The username does not exist or the email is empty.')
        return render_template('reset_password.html', tips=tips, userName=name, firstStep=True)
    elif token: #重置密码的最后一步
        tips = reset_pwd_final_step(user, token, new_p1, new_p2)
        if tips == 'ok':
            tips = _('Reset password success, Please close this page and login again.')
            return render_template('reset_password.html', tips=tips, userName=name, firstStep=True)
    elif user.email != email:
        tips = _("The email you input is not associated with this account.")
        return render_template('reset_password.html', tips=tips, userName=name, firstStep=True)
    else:
        token = new_secret_key(length=24)
        custom = user.custom
        expires = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).timestamp()
        custom['resetpwd'] = {'token': token, 'expires': expires}
        user.custom = custom
        user.save()
        tips = send_resetpwd_email(user, token)
        if tips == 'ok':
            tips = (_('The link to reset your password has been sent to your email.') + '<br/>' +
                _('Please check your email inbox within 24 hours.'))
        return render_template('reset_password.html', tips=tips, userName=name, firstStep=True)

#注册表单
@bpLogin.route("/signup")
def Signup():
    if app.config['ALLOW_SIGNUP'] == 'yes':
        inviteNeed = AppInfo.get_value(AppInfo.signupType, 'oneTimeCode') != 'public'
        return render_template('signup.html', tips='', inviteNeed=inviteNeed)
    else:
        tips = _("The website does not allow registration. You can ask the owner for an account.")
        return render_template('tipsback.html', title='not allow', urltoback='/', tips=tips)

#注册验证
@bpLogin.post("/signup")
def SignupPost():
    if not app.config['ALLOW_SIGNUP'] == 'yes':
        tips = _("The website does not allow registration. You can ask the owner for an account.")
        return render_template('tipsback.html', title='not allow', urltoback='/', tips=tips)

    signupType = AppInfo.get_value(AppInfo.signupType, 'oneTimeCode')
    inviteCodes = AppInfo.get_value(AppInfo.inviteCodes, '').splitlines()
    form = request.form
    name = form.get('username', '')
    password1 = form.get('password1')
    password2 = form.get('password2')
    email = form.get('email', '')
    code = form.get('invite_code')
    if not all([name, password1, password2, email, len(name) < 25, '@' in email]):
        tips = _("Some parameters are missing or wrong.")
    elif (signupType != 'public') and (not code or (code not in inviteCodes)):
        tips = _("The invitation code is invalid.")
    elif password1 != password2:
        tips = _("The two new passwords are dismatch.")
    elif any([char in name for char in specialChars]):
        tips = _("The username includes unsafe chars.")
    elif KeUser.get_or_none(KeUser.name == name):
        tips = _("Already exist the username.")
    elif not CreateAccountIfNotExist(name, password1, email):
        tips = _("Failed to create an account. Please contact the administrator for assistance.")
    else:
        #如果邀请码是一次性的，注册成功后从列表中去除
        if inviteCodes and signupType == 'oneTimeCode':
            try:
                inviteCodes.remove(code)
            except:
                pass
            AppInfo.set_value(AppInfo.inviteCodes, '\n'.join(inviteCodes))

        tips = _('Successfully created account.')
        return render_template('tipsback.html', title='Success', urltoback=url_for('bpLogin.Login'), tips=tips)

    return render_template('signup.html', tips=tips, inviteNeed=(signupType != 'public'))

#发送重设密码邮件
#返回 'ok' 表示成功
def send_resetpwd_email(user, token):
    if not user or not user.email or not token:
        return _("Some parameters are missing or wrong.")

    subject = _('Reset KindleEar password')
    info = [_('This is an automated email. Please do not reply to it.'),
        _('You can click the following link to reset your KindleEar password.'),
        '<br/>']
    query = urlencode({'token': token, 'name': user.name})
    link = urljoin(app.config['APP_DOMAIN'], url_for('bpLogin.ResetPasswordRoute') + '?' + query)
    info.append(f'<a href="{link}">' + subject + '</a>')
    info = '<br/>'.join(info)
    html = f"""<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        <title>{subject}</title></head><body><p style="text-align:center;font-size:1.5em;">
        {info}</p><br/><br/><p style="text-align:right;color:silver;">Sent from KindleEar &nbsp;</p></body></html>"""

    return send_html_mail(user, user.email, subject, html)

#重置密码的最后一步，校验密码，写入数据库
def reset_pwd_final_step(user, token, new_p1, new_p2):
    pre_set = user.custom.get('resetpwd', {})
    now = datetime.datetime.utcnow().timestamp()
    pre_time = pre_set.get('expires') or (now - datetime.timedelta(hours=1)).timestamp()
    if (token == pre_set.get('token')) and (now < pre_time):
        if new_p1 == new_p2:
            try:
                pwd = hashlib.md5((new_p1 + user.secret_key).encode()).hexdigest()
            except:
                tips = _("The password includes non-ascii chars.")
            else:
                custom = user.custom
                custom.pop('resetpwd', None)
                user.custom = custom
                user.passwd = pwd
                user.save()
                return 'ok'
        else:
            return _("The two new passwords are dismatch.")
    else:
        return _('The token is wrong or expired.')
