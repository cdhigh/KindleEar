#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#一些高级设置功能页面

import datetime, hashlib, io, json
from urllib.parse import quote_plus, urljoin
from bottle import route, post, redirect, response
from PIL import Image
from apps.base_handler import *
from apps.db_models import *
from apps.utils import local_time, ke_encrypt, ke_decrypt
from lib.pocket import Pocket
from lib.urlopener import UrlOpener
from config import *

#高级设置的主入口
@route("/adv")
def AdvSettings():
    redirect("/advdelivernow")

#现在推送
@route("/advdelivernow")
def AdvDeliverNow():
    user = get_current_user()
    books = [item for item in Book.all() if user.name in item.users]
    return render_page('advdelivernow.html', "Deliver now", current='advsetting',
        user=user, advcurr='delivernow', books=books, booksnum=len(books))

#设置邮件白名单
@route("/advwhitelist")
def AdvWhiteList():
    user = get_current_user()
    return render_page('advwhitelist.html', "White List", current='advsetting',
        user=user, advcurr='whitelist')

@post("/advwhitelist")
def AdvWhiteListPost():
    user = get_current_user()
    wlist = request.forms.wlist
    if wlist:
        wlist = wlist.replace('"', "").replace("'", "").strip()
        if wlist.startswith('*@'): #输入*@xx.xx则修改为@xx.xx
            wlist = wlist[2:]
        if wlist:
            WhiteList(mail=wlist, user=user).put()
    redirect("/advwhitelist")

#设置归档和分享配置项
@route("/advarchive")
def AdvArchive():
    user = get_current_user()
    
    return render_page('advarchive.html', "Archive", current='advsetting', user=user, advcurr='archive',
        savetoevernote=SAVE_TO_EVERNOTE, savetowiz=SAVE_TO_WIZ, savetopocket=SAVE_TO_POCKET, 
        savetoinstapaper=SAVE_TO_INSTAPAPER, ke_decrypt=ke_decrypt,
        shareonxweibo=SHARE_ON_XWEIBO, shareontweibo=SHARE_ON_TWEIBO, shareonfacebook=SHARE_ON_FACEBOOK,
        shareontwitter=SHARE_ON_TWITTER, shareontumblr=SHARE_ON_TUMBLR, openinbrowser=OPEN_IN_BROWSER)

@post("/advarchive")
def AdvArchivePost():
    user = get_current_user()
    forms = request.forms
    fuckgfw = bool(forms.fuckgfw)
    evernoteMail = forms.evernote_mail
    evernote = bool(forms.evernote) and evernoteMail
    wizMail = forms.wiz_mail
    wiz = bool(forms.wiz) and wizMail
    pocket = bool(forms.pocket)
    instapaper = bool(forms.instapaper)
    instapaperUsername = forms.instapaper_username
    instapaperPassword = forms.instapaper_password
    
    xweibo = bool(forms.xweibo)
    tweibo = bool(forms.tweibo)
    facebook = bool(forms.facebook)
    twitter = bool(forms.twitter)
    tumblr = bool(forms.tumblr)
    browser = bool(forms.browser)
    qrcode = bool(forms.qrcode)
    
    #将instapaper的密码加密
    if instapaperUsername and instapaperPassword:
        instapaperPassword = ke_encrypt(instapaperPassword, user.secret_key or '')
    else:
        instapaperUsername = ''
        instapaperPassword = ''
    
    user.share_fuckgfw = fuckgfw
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
    user.put()
    redirect("/advarchive")

#设置URL过滤器
@route("/advurlfilter")
def AdvUrlFilter():
    user = get_current_user()
    return render_page('advurlfilter.html', "Url Filter", current='advsetting',
        user=user, advcurr='urlfilter')

@post("/advurlfilter")
def AdvUrlFilterPost():
    user = get_current_user()
    url = request.forms.url
    if url:
        UrlFilter(url=url, user=user).put()
    redirect("/advurlfilter")

#删除白名单或URL过滤器项目
@route("/advdel")
def AdvDel():
    user = get_current_user()
    urlId = request.forms.delurlid
    wList = request.forms.delwlist
    if urlId and urlId.isdigit():
        flt = UrlFilter.get_by_id(int(urlId))
        if flt:
            flt.delete()
        redirect("/advurlfilter")
    if wList and wList.isdigit():
        wlist = WhiteList.get_by_id(int(wList))
        if wlist:
            wlist.delete()
        redirect("/advwhitelist")

#导入自定义rss订阅列表，当前支持Opml格式
@route("/advimport")
def AdvImport(tips=None):
    user = get_current_user()
    return render_page('advimport.html', "Import", current='advsetting',
        user=user, advcurr='import', tips=tips)

@post("/advimport")
def AdvImportPost():
    import opml
    upload = request.files.import_file
    defaultIsFullText = bool(request.forms.default_is_fulltext) #默认是否按全文RSS导入
    if upload:
        user = get_current_user()
        try:
            rssList = opml.from_string(upload.file.read())
        except Exception as e:
            return render_page('advimport.html', "Import", current='advsetting',
                user=user, advcurr='import', tips=str(e))
        
        for o in walkOpmlOutline(rssList):
            title, url, isfulltext = o.text, urllib.unquote_plus(o.xmlUrl), o.isFulltext #isFulltext为非标准属性
            if isfulltext.lower() in ('true', '1'):
                isfulltext = True
            elif isfulltext.lower() in ('false', '0'):
                isfulltext = False
            else:
                isfulltext = defaultIsFullText
                
            if title and url:
                rss = Feed.all().filter('book = ', user.own_feeds).filter("url = ", url).get() #查询是否有重复的
                if rss:
                    rss.title = title
                    rss.isfulltext = isfulltext
                    rss.put()
                else:
                    Feed(title=title, url=url, book=user.own_feeds, isfulltext=isfulltext,
                        time=datetime.datetime.utcnow()).put()
                        
        redirect("/my")
    else:
        redirect("/advimport")
    
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
@route("/advexport")
def AdvExport():
    user = get_current_user()
    
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
    for feed in Feed.all().filter('book = ', user.own_feeds):
        outLines.append('        <outline type="rss" text="{}" xmlUrl="{}" isFulltext="{}" />'.format(
            (feed.title, quote_plus(feed.url), feed.isfulltext)))
    outLines = '\n'.join(outLines)
    
    opmlFile = opmlTpl.forms(date=date, outlines=outLines)
    web.header("Content-Type", "text/xml;charset=utf-8")
    web.header("Content-Disposition", "attachment;filename=KindleEar_subscription.xml")
    return opmlFile

#在本地选择一个图片上传做为自定义RSS书籍的封面
@route("/advuploadcoverimage")
def AdvUploadCoverImage(tips=None):
    user = get_current_user()
    return render_page('advcoverimage.html', "Cover Image", current='advsetting',
        user=user, advcurr='uploadcoverimage', formaction="/advuploadcoverimageajax", 
        deletecoverhref="/advdeletecoverimageajax", tips=tips)

#AJAX接口的上传封面图片处理函数
@post("/advuploadcoverimageajax")
def AdvUploadCoverImageAjaxPost():
    MAX_IMAGE_PIXEL = 1024
    ret = 'ok'
    user = get_current_user(forAjax=True)
    try:
        upload = request.files.cover_file
        #将图像转换为JPEG格式，同时限制分辨率不超过1024
        imgInst = Image.open(upload.file)
        width, height = imgInst.size
        fmt = imgInst.format
        if (width > MAX_IMAGE_PIXEL) or (height > MAX_IMAGE_PIXEL):
            ratio = min(MAX_IMAGE_PIXEL / width, MAX_IMAGE_PIXEL / width)
            imgInst = imgInst.resize((int(width * ratio), int(height * ratio)))
        data = io.BytesIO()
        imgInst.save(data, 'JPEG')
        user.cover = db.Blob(data.getvalue())
        user.put()
    except Exception as e:
        ret = str(e)
        
    return ret

#删除上传的封面图片
@post("/advdeletecoverimageajax")
def AdvDeleteCoverImageAjaxPost():
    ret = {'status': 'ok'}
    user = get_current_user(forAjax=True)
    confirmKey = request.forms.action
    if confirmKey == 'delete':
        user.cover = None
        user.put()
    
    return json.dumps(ret)

#在本地选择一个样式文件上传做为所有书籍的样式
@route("/advuploadcss")
def AdvUploadCss(tips=None):
    user = get_current_user()
    return render_page('advuploadcss.html', "Stylesheet", current='advsetting',
        user=user, advcurr='uploadcss', formaction="/advuploadcssajax", 
        deletecsshref="/advdeletecssajax", tips=tips)

#AJAX接口的上传CSS处理函数
@post("/advuploadcssajax")
def AdvUploadCssAjaxPost():
    ret = 'ok'
    user = get_current_user(forAjax=True)
    upload = request.files.css_file
    if upload:
        #这里应该要验证样式表的有效性，但是现在先忽略了
        user.css_content = db.Text(upload.file.read(), encoding="utf-8")
        user.put()
    
    return ret

#删除上传的CSS
@post("/advdeletecssajax")
def AdvDeleteCssAjaxPost():
    ret = {'status': 'ok'}
    user = get_current_user(forAjax=True)
    confirmKey = request.forms.action
    if confirmKey == 'delete':
        user.css_content = ''
        user.put()
    
    return json.dumps(ret)
        
#集成各种网络服务OAuth2认证的相关处理
@route("/oauth2/<authType>")
def AdvOAuth2(authType):
    if authType.lower() != 'pocket':
        return 'Auth Type ({}) Unsupported!'.format(authType)
        
    user = get_current_user()
    cbUrl = urljoin(DOMAIN, '/oauth2cb/pocket?redirect=/advarchive')
    pocket = Pocket(POCKET_CONSUMER_KEY, cbUrl)
    try:
        request_token = pocket.get_request_token()
        url = pocket.get_authorize_url(request_token)
    except Exception as e:
        return render_page('tipsback.html', 'Authorization Error', urltoback='/advarchive', tips=_('Authorization Error!<br/>{}').format(e))

    session = current_session()
    session.pocket_request_token = request_token
    session.save()
    redirect(url)
        
#OAuth2认证过程的回调
@route("/oauth2cb/<authType>")
def AdvOAuth2Callback(authType):
    if authType.lower() != 'pocket':
        return 'Auth Type ({}) Unsupported!'.format(authType)
        
    user = get_current_user()
    reUrl = redirect.query.redirect
    if not reUrl:
        reUrl = '/advsettings'
        
    pocket = Pocket(POCKET_CONSUMER_KEY)
    request_token = current_session().get('pocket_request_token', '')
    try:
        resp = pocket.get_access_token(request_token)
        user.pocket_access_token = resp.get('access_token', '')
        user.pocket_acc_token_hash = hashlib.md5(user.pocket_access_token.encode()).hexdigest()
        user.put()
        return render_page('tipsback.html', 'Success authorized', urltoback='/advarchive', tips=_('Success authorized by Pocket!'))
    except Exception as e:
        user.pocket_access_token = ''
        user.pocket_acc_token_hash = ''
        user.pocket = False
        user.put()
        return render_page('tipsback.html', 'Failed to authorzi', urltoback='/advarchive', 
            tips=_('Failed to request authorization of Pocket!<hr/>See details below:<br/><br/>{}').format(e))

#通过AJAX验证密码等信息的函数
@post("/verifyajax/verifType")
def VerifyAjaxPost(self, verifType):
    INSTAPAPER_API_AUTH_URL = "https://www.instapaper.com/api/authenticate"
    response.content_type = 'application/json'
    
    respDict = {'status':'ok', 'correct':0}
    if verifType.lower() != 'instapaper':
        respDict['status'] = _('Request type [{}] unsupported').format(verifType)
        return json.dumps(respDict)
    
    user = get_current_user(forAjax=True)
    
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
    
    return json.dumps(respDict)
    