#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#一些高级设置功能页面

import datetime, hashlib, io
from urllib.parse import quote_plus, urljoin
from flask import Blueprint, url_for, render_template, redirect, session, send_file
from flask_babel import gettext as _
from PIL import Image
from apps.base_handler import *
from apps.back_end.db_models import *
from apps.utils import local_time, ke_encrypt, ke_decrypt
from lib.pocket import Pocket
from lib.urlopener import UrlOpener
from config import *

bpAdv = Blueprint('bpAdv', __name__)

#高级设置的主入口
@bpAdv.route("/adv")
def AdvSettings():
    return redirect(url_for("bpAdv.AdvDeliverNow"))

#现在推送
@bpAdv.route("/advdelivernow", endpoint='AdvDeliverNow')
@login_required()
def AdvDeliverNow():
    user = get_login_user()
    books = [item for item in Book.get_all() if user.name in item.users]
    return render_template('advdelivernow.html', tab='advset', user=user, 
        advCurr='delivernow', books=books, booksnum=len(books))

#设置邮件白名单
@bpAdv.route("/advwhitelist", endpoint='AdvWhiteList')
@login_required()
def AdvWhiteList():
    user = get_login_user()
    return render_template('advwhitelist.html', tab='advset',
        user=user, advCurr='whitelist', adminName=ADMIN_NAME)

@bpAdv.post("/advwhitelist", endpoint='AdvWhiteListPost')
@login_required()
def AdvWhiteListPost():
    user = get_login_user()
    wlist = request.form.get('wlist')
    if wlist:
        wlist = wlist.replace('"', "").replace("'", "").strip()
        if wlist.startswith('*@'): #输入*@xx.xx则修改为@xx.xx
            wlist = wlist[2:]
        if wlist:
            WhiteList(mail=wlist, user=user.reference_key_or_id).save()
    return redirect(url_for('bpAdv.AdvWhiteList'))

#设置归档和分享配置项
@bpAdv.route("/advarchive", endpoint='AdvArchive')
@login_required()
def AdvArchive():
    user = get_login_user()

    #jinja自动转义非常麻烦，在代码中先把翻译写好再传过去吧
    appendStrs = {}
    appendStrs["evernote"] = _("Append hyperlink '{}' to article").format(SAVE_TO_EVERNOTE)
    appendStrs["wiz"] = _("Append hyperlink '{}' to article").format(SAVE_TO_WIZ)
    appendStrs["pocket"] = _("Append hyperlink '{}' to article").format(SAVE_TO_POCKET)
    appendStrs["instapaper"] = _("Append hyperlink '{}' to article").format(SAVE_TO_INSTAPAPER)
    appendStrs["xweibo"] = _("Append hyperlink '{}' to article").format(SHARE_ON_XWEIBO)
    appendStrs["tweibo"] = _("Append hyperlink '{}' to article").format(SHARE_ON_TWEIBO)
    appendStrs["facebook"] = _("Append hyperlink '{}' to article").format(SHARE_ON_FACEBOOK)
    appendStrs["twitter"] = _("Append hyperlink '{}' to article").format(SHARE_ON_TWITTER)
    appendStrs["tumblr"] = _("Append hyperlink '{}' to article").format(SHARE_ON_TUMBLR)
    appendStrs["browser"] = _("Append hyperlink '{}' to article").format(OPEN_IN_BROWSER)
    
    return render_template('advarchive.html', tab='advset', user=user, advCurr='archive', appendStrs=appendStrs)

@bpAdv.post("/advarchive", endpoint='AdvArchivePost')
@login_required()
def AdvArchivePost():
    user = get_login_user()
    form = request.form
    evernoteMail = form.get('evernote_mail')
    evernote = bool(form.get('evernote')) and evernoteMail
    wizMail = form.get('wiz_mail')
    wiz = bool(form.get('wiz')) and wizMail
    pocket = bool(form.get('pocket'))
    instapaper = bool(form.get('instapaper'))
    instapaperUsername = form.get('instapaper_username')
    instapaperPassword = form.get('instapaper_password')
    
    xweibo = bool(form.get('xweibo'))
    tweibo = bool(form.get('tweibo'))
    facebook = bool(form.get('facebook'))
    twitter = bool(form.get('twitter'))
    tumblr = bool(form.get('tumblr'))
    browser = bool(form.get('browser'))
    qrcode = bool(form.get('qrcode'))
    
    #将instapaper的密码加密
    if instapaperUsername and instapaperPassword:
        instapaperPassword = ke_encrypt(instapaperPassword, user.secret_key or '')
    else:
        instapaperUsername = ''
        instapaperPassword = ''
    
    user.evernote = evernote
    user.evernote_mail = evernoteMail
    user.wiz = wiz
    user.wiz_mail = wizMail
    user.pocket = pocket
    user.instapaper = instapaper
    user.instapaper_username = instapaperUsername
    user.instapaper_password = instapaperPassword
    user.xweibo = xweibo
    user.tweibo = tweibo
    user.facebook = facebook
    user.twitter = twitter
    user.tumblr = tumblr
    user.browser = browser
    user.qrcode = qrcode
    user.save()
    return redirect(url_for("bpAdv.AdvArchive"))

#设置URL过滤器
@bpAdv.route("/advurlfilter", endpoint='AdvUrlFilter')
@login_required()
def AdvUrlFilter():
    user = get_login_user()
    return render_template('advurlfilter.html', tab='advset', user=user, advCurr='urlfilter')

@bpAdv.post("/advurlfilter", endpoint='AdvUrlFilterPost')
@login_required()
def AdvUrlFilterPost():
    user = get_login_user()
    url = request.form.get('url')
    if url:
        UrlFilter(url=url, user=user.reference_key_or_id).save()
    return redirect(url_for("bpAdv.AdvUrlFilter"))

#删除白名单或URL过滤器项目
@bpAdv.route("/advdel", endpoint='AdvDel')
@login_required()
def AdvDel():
    user = get_login_user()
    urlId = request.form.get('delurlid')
    wList = request.form.get('delwlist')
    if urlId:
        flt = UrlFilter.get_by_id_or_none(urlId)
        if flt:
            flt.delete()
        return redirect(url_for("bpAdv.AdvUrlFilter"))
    if wList:
        wlist = WhiteList.get_by_id_or_none(wList)
        if wlist:
            wlist.delete()
        return redirect(url_for("bpAdv.AdvWhiteList"))
    return redirect(url_for("bpAdmin.Admin"))

#导入自定义rss订阅列表，当前支持Opml格式
@bpAdv.route("/advimport", endpoint='AdvImport')
@login_required()
def AdvImport(tips=None):
    user = get_login_user()
    return render_template('advimport.html', tab='advset', user=user, advCurr='import', tips=tips)

@bpAdv.post("/advimport", endpoint='AdvImportPost')
@login_required()
def AdvImportPost():
    import opml
    upload = request.files.get('import_file')
    defaultIsFullText = bool(request.form.get('default_is_fulltext')) #默认是否按全文RSS导入
    if upload:
        user = get_login_user()
        try:
            rssList = opml.from_string(upload.file.read())
        except Exception as e:
            return render_template('advimport.html', tab='advset', user=user, advCurr='import', tips=str(e))
        
        for o in walkOpmlOutline(rssList):
            title, url, isfulltext = o.text, urllib.unquote_plus(o.xmlUrl), o.isFulltext #isFulltext为非标准属性
            if isfulltext.lower() in ('true', '1'):
                isfulltext = True
            elif isfulltext.lower() in ('false', '0'):
                isfulltext = False
            else:
                isfulltext = defaultIsFullText
                
            if title and url: #查询是否有重复的
                rss = [item for item in user.all_custom_rss if item.url == url]
                if rss:
                    rss.title = title
                    rss.isfulltext = isfulltext
                    rss.save()
                else:
                    Feed(title=title, url=url, book=user.my_rss_book.reference_key_or_id, isfulltext=isfulltext,
                        time=datetime.datetime.utcnow()).save()
                        
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
@bpAdv.route("/advexport", endpoint='AdvExport')
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
    for feed in user.all_custom_rss:
        outLines.append('        <outline type="rss" text="{}" xmlUrl="{}" isFulltext="{}" />'.format(
            (feed.title, quote_plus(feed.url), feed.isfulltext)))
    outLines = '\n'.join(outLines)
    
    opmlFile = opmlTpl.format(date=date, outlines=outLines)
    return send_file(io.StringIO(opmlFile), mimetype="text/xml", as_attachment=True, download_name="KindleEar_subscription.xml")
    
#在本地选择一个图片上传做为自定义RSS书籍的封面
@bpAdv.route("/advuploadcoverimage")
def AdvUploadCoverImage(tips=None):
    user = get_login_user()
    return render_template('advcoverimage.html', tab='advset',
        user=user, advCurr='uploadcoverimage', formaction=url_for("bpAdv.AdvUploadCoverImageAjaxPost"), 
        deletecoverhref=url_for("bpAdv.AdvDeleteCoverImageAjaxPost"), tips=tips)

#AJAX接口的上传封面图片处理函数
@bpAdv.post("/advuploadcoverimageajax", endpoint='AdvUploadCoverImageAjaxPost')
@login_required()
def AdvUploadCoverImageAjaxPost():
    MAX_IMAGE_PIXEL = 1024
    ret = 'ok'
    user = get_login_user()
    try:
        upload = request.files.get('cover_file')
        #将图像转换为JPEG格式，同时限制分辨率不超过1024
        imgInst = Image.open(upload.file)
        width, height = imgInst.size
        fmt = imgInst.format
        if (width > MAX_IMAGE_PIXEL) or (height > MAX_IMAGE_PIXEL):
            ratio = min(MAX_IMAGE_PIXEL / width, MAX_IMAGE_PIXEL / width)
            imgInst = imgInst.resize((int(width * ratio), int(height * ratio)))
        data = io.BytesIO()
        imgInst.save(data, 'JPEG')
        user.cover = data.getvalue()
        user.save()
    except Exception as e:
        ret = str(e)
        
    return ret

#删除上传的封面图片
@bpAdv.post("/advdeletecoverimageajax", endpoint='AdvDeleteCoverImageAjaxPost')
@login_required()
def AdvDeleteCoverImageAjaxPost():
    user = get_login_user()
    if request.form.get('action') == 'delete':
        user.cover = None
        user.save()
    
    return {'status': 'ok'}

#在本地选择一个样式文件上传做为所有书籍的样式
@bpAdv.route("/advuploadcss", endpoint='AdvUploadCss')
@login_required()
def AdvUploadCss(tips=None):
    user = get_login_user()
    return render_template('advuploadcss.html', tab='advset',
        user=user, advCurr='uploadcss', formaction=url_for("bpAdv.AdvUploadCssAjaxPost"), 
        deletecsshref=url_for("bpAdv.AdvDeleteCssAjaxPost"), tips=tips)

#AJAX接口的上传CSS处理函数
@bpAdv.post("/advuploadcssajax", endpoint='AdvUploadCssAjaxPost')
@login_required()
def AdvUploadCssAjaxPost():
    ret = 'ok'
    user = get_login_user()
    if 'css_file' in request.files:
        #werkzeug.datastructures.FileStorage对象
        upload = request.files['css_file'] #有filename属性，有read()/close()
        if upload:
            #这里应该要验证样式表的有效性，但是现在先忽略了
            user.css_content = upload.read().decode('utf-8')
            user.save()
            upload.close()
    
    return ret

#删除上传的CSS
@bpAdv.post("/advdeletecssajax", endpoint='AdvDeleteCssAjaxPost')
@login_required()
def AdvDeleteCssAjaxPost():
    ret = {'status': 'ok'}
    user = get_login_user()
    if request.form.get('action') == 'delete':
        user.css_content = ''
        user.save()
    
    return ret

#读取数据库中的图像二进制数据，如果为dbimage/cover则返回当前用户的封面图片
@bpAdv.route("/dbimage/<id_>", endpoint='DbImage')
@login_required()
def DbImage(id_):
    if id_ != 'cover':
        return ''
    
    user = get_login_user() 
    if user.cover:
        return send_file(io.BytesIO(user.cover), mimetype='image/jpeg')
    else:
        return "not cover"

#集成各种网络服务OAuth2认证的相关处理
@bpAdv.route("/oauth2/<authType>", endpoint='AdvOAuth2')
@login_required()
def AdvOAuth2(authType):
    if authType.lower() != 'pocket':
        return 'Auth Type ({}) Unsupported!'.format(authType)
        
    user = get_login_user()
    cbUrl = urljoin(KE_DOMAIN, '/oauth2cb/pocket?redirect=/advarchive')
    pocket = Pocket(POCKET_CONSUMER_KEY, cbUrl)
    try:
        request_token = pocket.get_request_token()
        url = pocket.get_authorize_url(request_token)
    except Exception as e:
        return render_template('tipsback.html', title='Authorization Error', urltoback='/advarchive', tips=_('Authorization Error!<br/>{}').format(e))

    session['pocket_request_token'] = request_token
    return redirect(url)
        
#OAuth2认证过程的回调
@bpAdv.route("/oauth2cb/<authType>", endpoint='AdvOAuth2Callback')
@login_required()
def AdvOAuth2Callback(authType):
    if authType.lower() != 'pocket':
        return 'Auth Type ({}) Unsupported!'.format(authType)
        
    user = get_login_user()
    
    pocket = Pocket(POCKET_CONSUMER_KEY)
    request_token = session.get('pocket_request_token', '')
    try:
        resp = pocket.get_access_token(request_token)
        user.pocket_access_token = resp.get('access_token', '')
        user.pocket_acc_token_hash = hashlib.md5(user.pocket_access_token.encode()).hexdigest()
        user.save()
        return render_template('tipsback.html', title='Success authorized', urltoback='/advarchive', tips=_('Success authorized by Pocket!'))
    except Exception as e:
        user.pocket_access_token = ''
        user.pocket_acc_token_hash = ''
        user.pocket = False
        user.save()
        return render_template('tipsback.html', title='Failed to authorize', urltoback='/advarchive', 
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
    
    userName = request.forms.username
    password = request.forms.password
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
    