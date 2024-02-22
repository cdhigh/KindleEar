#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#一些高级设置功能页面

import datetime, hashlib, io
from urllib.parse import quote_plus, unquote_plus, urljoin
from flask import Blueprint, url_for, render_template, redirect, session, send_file, abort, current_app as app
from flask_babel import gettext as _
from PIL import Image
from ..base_handler import *
from ..back_end.db_models import *
from ..utils import local_time, ke_encrypt, ke_decrypt, str_to_bool
from ..lib.pocket import Pocket
from ..lib.urlopener import UrlOpener

bpAdv = Blueprint('bpAdv', __name__)

#现在推送
@bpAdv.route("/adv", endpoint='AdvDeliverNowEntry')
@bpAdv.route("/adv/delivernow", endpoint='AdvDeliverNow')
@login_required()
def AdvDeliverNow():
    user = get_login_user()
    recipes = user.get_booked_recipe()
    return render_template('adv_delivernow.html', tab='advset', user=user, 
        advCurr='deliverNow', recipes=recipes, in_email_service=app.config['INBOUND_EMAIL_SERVICE'])

#设置邮件白名单
@bpAdv.route("/adv/whitelist", endpoint='AdvWhiteList')
@login_required()
def AdvWhiteList():
    user = get_login_user()
    return render_template('adv_whitelist.html', tab='advset',user=user, 
        advCurr='whitelist', adminName=app.config['ADMIN_NAME'], in_email_service=app.config['INBOUND_EMAIL_SERVICE'])

@bpAdv.post("/adv/whitelist", endpoint='AdvWhiteListPost')
@login_required()
def AdvWhiteListPost():
    user = get_login_user()
    wlist = request.form.get('wlist')
    if wlist:
        wlist = wlist.replace('"', "").replace("'", "").strip()
        if wlist.startswith('*@'): #输入*@xx.xx则修改为@xx.xx
            wlist = wlist[1:]
        if wlist:
            WhiteList.get_or_create(mail=wlist, user=user.name)
    return redirect(url_for('bpAdv.AdvWhiteList'))

#删除白名单项目
@bpAdv.route("/advdel", endpoint='AdvDel')
@login_required()
def AdvDel():
    user = get_login_user()
    wlist_id = request.args.get('wlist_id')
    if wlist_id:
        dbItem = WhiteList.get_by_id_or_none(wlist_id)
        if dbItem:
            dbItem.delete_instance()
        return redirect(url_for("bpAdv.AdvWhiteList"))
    return redirect(url_for("bpAdmin.Admin"))

#设置归档和分享配置项
@bpAdv.route("/adv/archive", endpoint='AdvArchive')
@login_required()
def AdvArchive():
    user = get_login_user()

    #jinja自动转义非常麻烦，在代码中先把翻译写好再传过去吧
    appendStrs = {}
    appendStrs["Evernote"] = _("Append hyperlink '{}' to article").format(_('Save to {}').format(_('evernote')))
    appendStrs["Wiz"] = _("Append hyperlink '{}' to article").format(_('Save to {}').format(_('wiz')))
    appendStrs["Pocket"] = _("Append hyperlink '{}' to article").format(_('Save to {}').format(_('pocket')))
    appendStrs["Instapaper"] = _("Append hyperlink '{}' to article").format(_('Save to {}').format(_('instapaper')))
    appendStrs["Weibo"] = _("Append hyperlink '{}' to article").format(_('Share on {}').format(_('weibo')))
    appendStrs["TencentWeibo"] = _("Append hyperlink '{}' to article").format(_('Share on {}').format(_('tencent weibo')))
    appendStrs["Facebook"] = _("Append hyperlink '{}' to article").format(_('Share on {}').format(_('facebook')))
    appendStrs["X"] = _("Append hyperlink '{}' to article").format(_('Share on {}').format('X'))
    appendStrs["Tumblr"] = _("Append hyperlink '{}' to article").format(_('Share on {}').format(_('tumblr')))
    appendStrs["Browser"] = _("Append hyperlink '{}' to article").format(_('Open in browser'))
    shareLinks = user.share_links
    shareLinks.pop('key', None)
    
    return render_template('adv_archive.html', tab='advset', user=user, advCurr='archive', appendStrs=appendStrs,
        shareLinks=shareLinks, in_email_service=app.config['INBOUND_EMAIL_SERVICE'])

@bpAdv.post("/adv/archive", endpoint='AdvArchivePost')
@login_required()
def AdvArchivePost():
    user = get_login_user()
    form = request.form
    evernoteMail = form.get('evernote_mail', '').strip()
    evernote = str_to_bool(form.get('evernote')) and evernoteMail
    wizMail = form.get('wiz_mail', '').strip()
    wiz = str_to_bool(form.get('wiz')) and wizMail
    pocket = str_to_bool(form.get('pocket'))
    instapaper = str_to_bool(form.get('instapaper'))
    instaName = form.get('instapaper_username', '').strip()
    instaPwd = form.get('instapaper_password', '')
    #将instapaper的密码加密
    if instaName and instaPwd:
        instaPwd = ke_encrypt(instaPwd, user.secret_key)
    else:
        instaName = ''
        instaPwd = ''
    
    shareLinks = user.share_links
    oldPocket = shareLinks.get('pocket', {})
    accessToken = oldPocket.get('access_token', '') if oldPocket else ''
    shareLinks['Evernote'] = {'enable': '1' if evernote else '', 'email': evernoteMail}
    shareLinks['Wiz'] = {'enable': '1' if wiz else '', 'email': wizMail}
    shareLinks['Pocket'] = {'enable': '1' if pocket else '', 'access_token': accessToken}
    shareLinks['Instapaper'] = {'enable': '1' if instapaper else '', 'username': instaName, 'password': instaPwd}
    shareLinks['Weibo'] = str_to_bool(form.get('weibo'))
    shareLinks['TencentWeibo'] = str_to_bool(form.get('tencentweibo'))
    shareLinks['Facebook'] = str_to_bool(form.get('facebook'))
    shareLinks['X'] = str_to_bool(form.get('x'))
    shareLinks['Tumblr'] = str_to_bool(form.get('tumblr'))
    shareLinks['Browser'] = str_to_bool(form.get('browser'))
    user.share_links = shareLinks
    user.save()
    return redirect(url_for("bpAdv.AdvArchive"))

#导入自定义rss订阅列表，当前支持Opml格式
@bpAdv.route("/adv/import", endpoint='AdvImport')
@login_required()
def AdvImport(tips=None):
    user = get_login_user()
    return render_template('adv_import.html', tab='advset', user=user, advCurr='import', tips=tips,
        in_email_service=app.config['INBOUND_EMAIL_SERVICE'])

@bpAdv.post("/adv/import", endpoint='AdvImportPost')
@login_required()
def AdvImportPost():
    import opml
    user = get_login_user()
    upload = request.files.get('import_file')
    defaultIsFullText = bool(request.form.get('default_is_fulltext')) #默认是否按全文RSS导入
    if upload:
        try:
            rssList = opml.from_string(upload.read())
        except Exception as e:
            return render_template('adv_import.html', tab='advset', user=user, advCurr='import', tips=str(e),
                in_email_service=app.config['INBOUND_EMAIL_SERVICE'])
        
        for o in walkOpmlOutline(rssList):
            title, url, isfulltext = o.text, unquote_plus(o.xmlUrl), o.isFulltext #isFulltext为非标准属性
            if isfulltext:
                isfulltext = str_to_bool(isfulltext)
            else:
                isfulltext = defaultIsFullText
            
            if not url.startswith('http'):
                url = ('https:/' if url.startswith('/') else 'https://') + url

            if title and url: #查询是否有重复的
                dbItem = Recipe.get_or_none((Recipe.user == user.name) & (Recipe.title == title))
                if dbItem:
                    dbItem.url = url
                    dbItem.isfulltext = isfulltext
                    dbItem.save()
                else:
                    Recipe.create(title=title, url=url, user=user.name, isfulltext=isfulltext, type_='custom',
                        time=datetime.datetime.utcnow())
                        
        return redirect(url_for("bpSubscribe.MySubscription"))
    else:
        return redirect(url_for("bpAdv.AdvImport"))
    
#遍历opml的outline元素，支持不限层数的嵌套
def walkOpmlOutline(outline):
    if not outline:
        return
    
    cnt = len(outline)
    for idx in range(cnt):
        obj = outline[idx]
        if len(obj) > 0:
            yield from walkOpmlOutline(obj)
        yield obj

#生成自定义rss订阅列表的Opml格式文件，让用户下载保存
@bpAdv.route("/adv/export", endpoint='AdvExport')
@login_required()
def AdvExport():
    user = get_login_user()
    
    #为了简单起见，就不用其他库生成xml，而直接使用字符串格式化生成
    opmlTpl = """<?xml version="1.0" encoding="utf-8" ?>
    <opml version="2.0">
    <head>
      <title>KindleEar.opml</title>
      <dateCreated>{date}</dateCreated>
      <dateModified>{date}</dateModified>
      <ownerName>KindleEar</ownerName>
    </head>
    <body>
    {outLines}
    </body>
    </opml>"""

    date = local_time('%a, %d %b %Y %H:%M:%S GMT', user.timezone)
    #添加时区信息
    if user.timezone != 0:
        date += '+{:02d}00'.format(user.timezone) if (user.timezone > 0) else '-{:02d}00'.format(abs(user.timezone))
    outLines = []
    for feed in user.all_custom_rss():
        outLines.append('<outline type="rss" text="{}" xmlUrl="{}" isFulltext="{}" />'.format(
            feed.title, quote_plus(feed.url), feed.isfulltext))
    outLines = '\n'.join(outLines)
    
    opmlFile = opmlTpl.format(date=date, outLines=outLines)
    outLines = []
    for line in opmlFile.split('\n'):
        outLines.append(line[4:] if line.startswith('  ') else line)
    opmlFile = '\n'.join(outLines).encode('utf-8')
    return send_file(io.BytesIO(opmlFile), mimetype="text/xml", as_attachment=True, download_name="KindleEar_subscription.xml")
    
#在本地选择一个图片上传做为自定义RSS书籍的封面
@bpAdv.route("/adv/cover")
@login_required()
def AdvUploadCoverImage(tips=None):
    user = get_login_user()
    covers = {}
    covers['order'] = user.covers.get('order', 'random')
    for idx in range(7):
        coverName = f'cover{idx}'
        covers[coverName] = user.covers.get(coverName, f'/images/{coverName}.jpg')
    jsonCovers = json.dumps(covers)
    return render_template('adv_uploadcover.html', tab='advset', user=user, advCurr='uploadCover', 
        uploadUrl=url_for("bpAdv.AdvUploadCoverAjaxPost"), covers=covers, jsonCovers=jsonCovers,
        tips=tips, in_email_service=app.config['INBOUND_EMAIL_SERVICE'])

#AJAX接口的上传封面图片处理函数
@bpAdv.post("/adv/cover", endpoint='AdvUploadCoverAjaxPost')
@login_required(forAjax=True)
def AdvUploadCoverAjaxPost():
    MAX_WIDTH = 832
    MAX_HEIGHT = 1280
    ret = {'status': 'ok'}
    user = get_login_user()
    covers = user.covers
    covers['order'] = request.form.get('order', 'random')
    for idx in range(7):
        coverName = f'cover{idx}'
        upload = request.files.get(coverName) or request.form.get(coverName)
        if not upload:
            continue

        if isinstance(upload, str):
            if upload.startswith('/images/'): #delete the old image data
                UserBlob.delete().where((UserBlob.user == user.name) & (UserBlob.name == coverName)).execute()
            covers[coverName] = upload
            continue
        
        try:
            #将图像转换为JPEG格式，同时限制分辨率不超过 832x1280，宽高比为0.625~0.664，建议0.65
            imgInst = Image.open(upload)
            width, height = imgInst.size
            fmt = imgInst.format
            if (width > MAX_WIDTH) or (height > MAX_HEIGHT):
                ratio = min(MAX_WIDTH / width, MAX_HEIGHT / width)
                imgInst = imgInst.resize((int(width * ratio), int(height * ratio)))
            if imgInst.mode != 'RGB':
                imgInst = imgInst.convert('RGB')
            data = io.BytesIO()
            imgInst.save(data, 'JPEG')
            dbCover = UserBlob.get_or_none((UserBlob.user == user.name) & (UserBlob.name == coverName))
            if dbCover:
                dbCover.data = data.getvalue()
            else:
                dbCover = UserBlob(name=coverName, user=user.name, data=data.getvalue())
            dbCover.save()
            covers[coverName] = '/dbimage/{}'.format(str(dbCover.id))
            upload.close()
        except Exception as e:
            ret['status'] = str(e)
            return ret
    
    user.covers = covers
    user.save()
    ret.update(covers)
    return ret

#在本地选择一个样式文件上传做为所有书籍的样式
@bpAdv.route("/adv/css", endpoint='AdvUploadCss')
@login_required()
def AdvUploadCss(tips=None):
    user = get_login_user()
    extra_css = user.get_extra_css()
    return render_template('adv_uploadcss.html', tab='advset', extra_css=extra_css,
        user=user, advCurr='uploadCss', uploadUrl=url_for("bpAdv.AdvUploadCssAjaxPost"), 
        deleteUrl=url_for("bpAdv.AdvDeleteCssAjaxPost"), tips=tips, 
        in_email_service=app.config['INBOUND_EMAIL_SERVICE'])

#AJAX接口的上传CSS处理函数
@bpAdv.post("/adv/css", endpoint='AdvUploadCssAjaxPost')
@login_required(forAjax=True)
def AdvUploadCssAjaxPost():
    ret = {'status': 'ok'}
    user = get_login_user()
    try:
        upload = request.files.get('css_file')
        data = upload.read().decode('utf-8').encode('utf-8') #测试是否是utf-8编码
        dbItem = UserBlob.get_or_none((UserBlob.user == user.name) & (UserBlob.name == 'css'))
        if dbItem:
            dbItem.data = data
        else:
            dbItem = UserBlob(name='css', user=user.name, data=data)
        dbItem.save()
        upload.close()
    except Exception as e:
        ret['status'] = str(e)

    return ret

#删除上传的CSS
@bpAdv.post("/adv/css/delete", endpoint='AdvDeleteCssAjaxPost')
@login_required(forAjax=True)
def AdvDeleteCssAjaxPost():
    ret = {'status': 'ok'}
    user = get_login_user()
    if request.form.get('action') == 'delete':
        UserBlob.delete().where((UserBlob.user == user.name) & (UserBlob.name=='css')).execute()
    
    return ret

#读取数据库中的图像二进制数据，如果为dbimage/cover则返回当前用户的封面图片
@bpAdv.route("/dbimage/<id_>", endpoint='DbImage')
@login_required()
def DbImage(id_):
    user = get_login_user()
    dbItem = UserBlob.get_by_id_or_none(id_)
    if dbItem:
        return send_file(io.BytesIO(dbItem.data), mimetype='image/jpeg')
    else:
        abort(404)

#集成各种网络服务OAuth2认证的相关处理
@bpAdv.route("/oauth2/<authType>", endpoint='AdvOAuth2')
@login_required()
def AdvOAuth2(authType):
    if authType.lower() != 'pocket':
        return 'Auth Type ({}) Unsupported!'.format(authType)
        
    user = get_login_user()
    cbUrl = urljoin(app.config['APP_DOMAIN'], '/oauth2cb/pocket?redirect=/adv/archive')
    pocket = Pocket(app.config['POCKET_CONSUMER_KEY'], cbUrl)
    try:
        request_token = pocket.get_request_token()
        url = pocket.get_authorize_url(request_token)
    except Exception as e:
        return render_template('tipsback.html', title='Authorization Error', urltoback=url_for('bpAdv.AdvArchive'),
            tips=_('Authorization Error!<br/>{}').format(e))

    session['pocket_request_token'] = request_token
    return redirect(url)
        
#OAuth2认证过程的回调
@bpAdv.route("/oauth2cb/<authType>", endpoint='AdvOAuth2Callback')
@login_required()
def AdvOAuth2Callback(authType):
    if authType.lower() != 'pocket':
        return 'Auth Type ({}) Unsupported!'.format(authType)
        
    user = get_login_user()
    
    pocketInst = Pocket(app.config['POCKET_CONSUMER_KEY'])
    request_token = session.get('pocket_request_token', '')
    shareLinks = user.share_links
    try:
        resp = pocketInst.get_access_token(request_token)
        pocket = shareLinks.get('pocket', {})
        pocket['access_token'] = resp.get('access_token', '')
        user.share_links = shareLinks
        user.save()
        return render_template('tipsback.html', title='Success authorized', urltoback=url_for('bpAdv.AdvArchive'), tips=_('Success authorized by Pocket!'))
    except Exception as e:
        shareLinks[pocket] = {'enable': '', 'access_token': ''}
        user.share_links = shareLinks
        user.save()
        return render_template('tipsback.html', title='Failed to authorize', urltoback=url_for('bpAdv.AdvArchive'), 
            tips=_('Failed to request authorization of Pocket!<hr/>See details below:<br/><br/>{}').format(e))

#通过AJAX验证密码等信息的函数
@bpAdv.post("/verifyajax/verifType", endpoint='VerifyAjaxPost')
@login_required()
def VerifyAjaxPost(verifType):
    INSTAPAPER_API_AUTH_URL = "https://www.instapaper.com/api/authenticate"
    
    respDict = {'status': 'ok', 'correct': 0}
    if verifType.lower() != 'instapaper':
        respDict['status'] = _('Request type [{}] unsupported').format(verifType)
        return respDict
    
    user = get_login_user()
    
    userName = request.form.get('username', '')
    password = request.form.get('password', '')
    opener = UrlOpener()
    apiParameters = {'username': userName, 'password':password}
    ret = opener.open(INSTAPAPER_API_AUTH_URL, data=apiParameters)
    if ret.status_code in (200, 201):
        respDict['correct'] = 1
    elif ret.status_code == 403:
        respDict['correct'] = 0
    else:
        respDict['status'] = _("The Instapaper service encountered an error. Please try again later.")
    
    return respDict
    