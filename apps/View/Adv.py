#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>
import datetime, urllib, urlparse, hashlib, StringIO
try:
    import json
except ImportError:
    import simplejson as json
    
import web
from PIL import Image
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import local_time, etagged, ke_encrypt, ke_decrypt
from lib.pocket import Pocket
from lib.urlopener import URLOpener
from config import *

#高级设置的主入口
class AdvSettings(BaseHandler):
    __url__ = "/adv"
    #@etagged()
    def GET(self):
        raise web.seeother(AdvDeliverNow.__url__)

#现在推送
class AdvDeliverNow(BaseHandler):
    __url__ = "/advdelivernow"
    @etagged()
    def GET(self):
        user = self.getcurrentuser()
        books = [item for item in Book.all() if user.name in item.users]
        return self.render('advdelivernow.html', "Deliver now", current='advsetting',
            user=user, advcurr='delivernow', books=books, booksnum=len(books))

#设置邮件白名单
class AdvWhiteList(BaseHandler):
    __url__ = "/advwhitelist"
    @etagged()
    def GET(self):
        user = self.getcurrentuser()
        return self.render('advwhitelist.html', "White List", current='advsetting',
            user=user, advcurr='whitelist')
        
    def POST(self):
        user = self.getcurrentuser()
        
        wlist = web.input().get('wlist')
        if wlist:
            if len(wlist) > 2: #预防有的人输入的过滤器带有单引号或双引号
                if wlist[0] in ('"', "'") and wlist[-1] in ('"', "'"):
                    wlist = wlist[1:-1]
            if wlist.startswith('*@'): #输入*@xx.xx则修改为@xx.xx
                wlist = wlist[2:]
            if wlist:
                WhiteList(mail=wlist, user=user).put()
        raise web.seeother(self.__url__)

#设置归档和分享配置项
class AdvArchive(BaseHandler):
    __url__ = "/advarchive"
    
    @etagged()
    def GET(self):
        user = self.getcurrentuser()
        
        return self.render('advarchive.html', "Archive", current='advsetting', user=user, advcurr='archive',
            savetoevernote=SAVE_TO_EVERNOTE, savetowiz=SAVE_TO_WIZ, savetopocket=SAVE_TO_POCKET, 
            savetoinstapaper=SAVE_TO_INSTAPAPER, ke_decrypt=ke_decrypt,
            shareonxweibo=SHARE_ON_XWEIBO, shareontweibo=SHARE_ON_TWEIBO, shareonfacebook=SHARE_ON_FACEBOOK,
            shareontwitter=SHARE_ON_TWITTER, shareontumblr=SHARE_ON_TUMBLR, openinbrowser=OPEN_IN_BROWSER)
        
    def POST(self):
        user = self.getcurrentuser()
        
        fuckgfw = bool(web.input().get('fuckgfw'))
        evernote = bool(web.input().get('evernote'))
        evernote_mail = web.input().get('evernote_mail', '')
        if not evernote_mail:
            evernote = False
        wiz = bool(web.input().get('wiz'))
        wiz_mail = web.input().get('wiz_mail', '')
        if not wiz_mail:
            wiz = False
        pocket = bool(web.input().get('pocket'))
        instapaper = bool(web.input().get('instapaper'))
        instapaper_username = web.input().get('instapaper_username', '')
        instapaper_password = web.input().get('instapaper_password', '')
        
        xweibo = bool(web.input().get('xweibo'))
        tweibo = bool(web.input().get('tweibo'))
        facebook = bool(web.input().get('facebook'))
        twitter = bool(web.input().get('twitter'))
        tumblr = bool(web.input().get('tumblr'))
        browser = bool(web.input().get('browser'))
        qrcode = bool(web.input().get('qrcode'))
        
        #将instapaper的密码加密
        if instapaper_username and instapaper_password:
            instapaper_password = ke_encrypt(instapaper_password, user.secret_key or '')
        else:
            instapaper_username = ''
            instapaper_password = ''
        
        user.share_fuckgfw = fuckgfw
        user.evernote = evernote
        user.evernote_mail = evernote_mail
        user.wiz = wiz
        user.wiz_mail = wiz_mail
        user.pocket = pocket
        user.instapaper = instapaper
        user.instapaper_username = instapaper_username
        user.instapaper_password = instapaper_password
        user.xweibo = xweibo
        user.tweibo = tweibo
        user.facebook = facebook
        user.twitter = twitter
        user.tumblr = tumblr
        user.browser = browser
        user.qrcode = qrcode
        user.put()
        raise web.seeother(self.__url__)

#设置URL过滤器
class AdvUrlFilter(BaseHandler):
    __url__ = "/advurlfilter"
    @etagged()
    def GET(self):
        user = self.getcurrentuser()
        return self.render('advurlfilter.html', "Url Filter", current='advsetting',
            user=user, advcurr='urlfilter')
        
    def POST(self):
        user = self.getcurrentuser()
        
        url = web.input().get('url')
        if url:
            UrlFilter(url=url,user=user).put()
        raise web.seeother(self.__url__)

#删除白名单或URL过滤器项目
class AdvDel(BaseHandler):
    __url__ = "/advdel"
    @etagged()
    def GET(self):
        user = self.getcurrentuser()
        delurlid = web.input().get('delurlid')
        delwlist = web.input().get('delwlist')
        if delurlid and delurlid.isdigit():
            flt = UrlFilter.get_by_id(int(delurlid))
            if flt:
                flt.delete()
            raise web.seeother('/advurlfilter')
        if delwlist and delwlist.isdigit():
            wlist = WhiteList.get_by_id(int(delwlist))
            if wlist:
                wlist.delete()
            raise web.seeother('/advwhitelist')

#导入自定义rss订阅列表，当前支持Opml格式
class AdvImport(BaseHandler):
    __url__ = "/advimport"
    @etagged()
    def GET(self, tips=None):
        user = self.getcurrentuser()
        return self.render('advimport.html', "Import", current='advsetting',
            user=user, advcurr='import', tips=tips)

    def POST(self):
        import opml
        x = web.input(importfile={})
        defaultIsfulltext = bool(x.get('defaultIsfulltext')) #默认是否按全文RSS导入
        if 'importfile' in x:
            user = self.getcurrentuser()
            try:
                rsslist = opml.from_string(x.importfile.file.read())
            except Exception as e:
                return self.GET(str(e))
            
            for o in self.walkOutline(rsslist):
                title, url, isfulltext = o.text, urllib.unquote_plus(o.xmlUrl), o.isFulltext #isFulltext为非标准属性
                if isfulltext.lower() in ('true', '1'):
                    isfulltext = True
                elif isfulltext.lower() in ('false', '0'):
                    isfulltext = False
                else:
                    isfulltext = defaultIsfulltext
                    
                if title and url:
                    try:
                        url = url.decode('utf-8')
                    except:
                        pass
                    rss = Feed.all().filter('book = ', user.ownfeeds).filter("url = ", url).get() #查询是否有重复的
                    if rss:
                        rss.title = title
                        rss.isfulltext = isfulltext
                        rss.put()
                    else:
                        Feed(title=title, url=url, book=user.ownfeeds, isfulltext=isfulltext,
                            time=datetime.datetime.utcnow()).put()
                            
            raise web.seeother('/my')
        else:
            raise web.seeother(self.__url__)
    
    def walkOutline(self, outline):
        #遍历opml的outline元素，支持不限层数的嵌套
        if not outline:
            return
        
        cnt = len(outline)
        for idx in range(cnt):
            o = outline[idx]
            if len(o) > 0:
                for subOutline in self.walkOutline(o):
                    yield subOutline
            yield o

class AdvExport(BaseHandler):
    """ 生成自定义rss订阅列表的Opml格式文件，让用户下载保存 """
    __url__ = "/advexport"
    def GET(self):
        user = self.getcurrentuser()
        
        #为了简单起见，就不用其他库生成xml，而直接使用字符串格式化生成
        opmlTpl = u"""<?xml version="1.0" encoding="utf-8" ?>
<opml version="2.0">
<head>
    <title>KindleEar.opml</title>
    <dateCreated>%s</dateCreated>
    <dateModified>%s</dateModified>
    <ownerName>KindleEar</ownerName>
</head>
<body>
%s
</body>
</opml>"""

        date = local_time('%a, %d %b %Y %H:%M:%S GMT', user.timezone)
        #添加时区信息
        if user.timezone != 0:
            date += '+%02d00' % user.timezone if user.timezone > 0 else '-%02d00' % abs(user.timezone)
        outlines = []
        for feed in Feed.all().filter('book = ', user.ownfeeds):
            outlines.append('    <outline type="rss" text="%s" xmlUrl="%s" isFulltext="%d" />' % 
                (feed.title, urllib.quote_plus(feed.url.encode('utf-8')), feed.isfulltext))
        outlines = '\n'.join(outlines)
        
        opmlfile = opmlTpl % (date, date, outlines)
        web.header("Content-Type", "text/xml;charset=utf-8")
        web.header("Content-Disposition", "attachment;filename=KindleEar_subscription.xml")
        return opmlfile.encode('utf-8')

#在本地选择一个图片上传做为自定义RSS书籍的封面
class AdvUploadCoverImage(BaseHandler):
    __url__ = "/advuploadcoverimage"
    @etagged()
    def GET(self, tips=None):
        user = self.getcurrentuser()
        return self.render('advcoverimage.html', "Cover Image", current='advsetting',
            user=user, advcurr='uploadcoverimage', formaction=AdvUploadCoverImageAjax.__url__, 
            deletecoverhref=AdvDeleteCoverImageAjax.__url__, tips=tips)

#AJAX接口的上传封面图片处理函数
class AdvUploadCoverImageAjax(BaseHandler):
    __url__ = "/advuploadcoverimageajax"
    MAX_IMAGE_PIXEL = 1024
    def POST(self):
        ret = 'ok'
        user = self.getcurrentuser(forAjax=True)
        try:
            x = web.input(coverfile={})
            file_ = x['coverfile'].file
            if user and file_:
                #将图像转换为JPEG格式，同时限制分辨率不超过1024
                img = Image.open(file_)
                width, height = img.size
                fmt = img.format
                if (width > self.MAX_IMAGE_PIXEL) or (height > self.MAX_IMAGE_PIXEL):
                    ratio = min(float(self.MAX_IMAGE_PIXEL)/float(width), float(self.MAX_IMAGE_PIXEL)/float(height))
                    img = img.resize((int(width*ratio), int(height*ratio)))
                data = StringIO.StringIO()
                img.save(data, 'JPEG')
                user.cover = db.Blob(data.getvalue())
                user.put()
        except Exception as e:
            ret = str(e)
            
        return ret

#删除上传的封面图片
class AdvDeleteCoverImageAjax(BaseHandler):
    __url__ = "/advdeletecoverimageajax"
    def POST(self):
        ret = {'status': 'ok'}
        user = self.getcurrentuser(forAjax=True)
        try:
            confirmKey = web.input().get('action')
            if user and confirmKey == 'delete':
                user.cover = None
                user.put()
        except Exception as e:
            ret['status'] = str(e)
            
        return json.dumps(ret)

#在本地选择一个样式文件上传做为所有书籍的样式
class AdvUploadCss(BaseHandler):
    __url__ = "/advuploadcss"
    @etagged()
    def GET(self, tips=None):
        user = self.getcurrentuser()
        return self.render('advuploadcss.html', "Stylesheet", current='advsetting',
            user=user, advcurr='uploadcss', formaction=AdvUploadCssAjax.__url__, 
            deletecsshref=AdvDeleteCssAjax.__url__, tips=tips)

#AJAX接口的上传CSS处理函数
class AdvUploadCssAjax(BaseHandler):
    __url__ = "/advuploadcssajax"
    def POST(self):
        ret = 'ok'
        user = self.getcurrentuser(forAjax=True)
        try:
            x = web.input(cssfile={})
            file_ = x['cssfile'].file
            if user and file_:
                #这里应该要验证样式表的有效性，但是现在先忽略了
                user.css_content = db.Text(file_.read(), encoding="utf-8")
                user.put()
        except Exception as e:
            ret = str(e)
            
        return ret

#删除上传的CSS
class AdvDeleteCssAjax(BaseHandler):
    __url__ = "/advdeletecssajax"
    def POST(self):
        ret = {'status': 'ok'}
        user = self.getcurrentuser(forAjax=True)
        try:
            confirmKey = web.input().get('action')
            if user and confirmKey == 'delete':
                user.css_content = ''
                user.put()
        except Exception as e:
            ret['status'] = str(e)
            
        return json.dumps(ret)
        
#集成各种网络服务OAuth2认证的相关处理
class AdvOAuth2(BaseHandler):
    __url__ = "/oauth2/(.*)"
    
    def GET(self, authType):
        if authType.lower() != 'pocket':
            return 'Auth Type(%s) Unsupported!' % authType
            
        user = self.getcurrentuser()
        cbUrl = urlparse.urljoin(DOMAIN, '/oauth2cb/pocket?redirect=/advarchive')
        pocket = Pocket(POCKET_CONSUMER_KEY, cbUrl)
        try:
            request_token = pocket.get_request_token()
            url = pocket.get_authorize_url(request_token)
        except Exception as e:
            return self.render('tipsback.html', 'Authorization Error', urltoback='/advarchive', tips=_('Authorization Error!<br/>%s') % str(e))
        
        main.session['pocket_request_token'] = request_token
        raise web.seeother(url)
        
#OAuth2认证过程的回调
class AdvOAuth2Callback(BaseHandler):
    __url__ = "/oauth2cb/(.*)"
    
    def GET(self, authType):
        if authType.lower() != 'pocket':
            return 'Auth Type(%s) Unsupported!' % authType
            
        user = self.getcurrentuser()
        reUrl = web.input().get('redirect')
        if not reUrl:
            reUrl = '/advsettings'
            
        pocket = Pocket(POCKET_CONSUMER_KEY)
        request_token = main.session.get('pocket_request_token', '')
        try:
            resp = pocket.get_access_token(request_token)
            user.pocket_access_token = resp.get('access_token', '')
            user.pocket_acc_token_hash = hashlib.md5(user.pocket_access_token).hexdigest()
            user.put()
            return self.render('tipsback.html', 'Success authorized', urltoback='/advarchive', tips=_('Success authorized by Pocket!'))
        except Exception as e:
            user.pocket_access_token = ''
            user.pocket_acc_token_hash = ''
            user.pocket = False
            user.put()
            return self.render('tipsback.html', 'Failed to authorzi', urltoback='/advarchive', 
                tips=_('Failed to request authorization of Pocket!<hr/>See details below:<br/><br/>%s') % str(e))

#通过AJAX验证密码等信息的函数
class VerifyAjax(BaseHandler):
    __url__ = "/verifyajax/(.*)"
    
    def POST(self, verType):
        INSTAPAPER_API_AUTH_URL = "https://www.instapaper.com/api/authenticate"
        web.header('Content-Type', 'application/json')
        
        respDict = {'status':'ok', 'correct':0}
        if verType.lower() != 'instapaper':
            respDict['status'] = _('Request type[%s] unsupported') % verType
            return json.dumps(respDict)
        
        user = self.getcurrentuser(forAjax=True)
        
        username = web.input().get('username', '')
        password = web.input().get('password', '')
        opener = URLOpener()
        apiParameters = {'username': username, 'password':password}
        ret = opener.open(INSTAPAPER_API_AUTH_URL, data=apiParameters)
        if ret.status_code in (200, 201):
            respDict['correct'] = 1
        elif ret.status_code == 403:
            respDict['correct'] = 0
        else:
            respDict['status'] = _("The Instapaper service encountered an error. Please try again later.")
        
        return json.dumps(respDict)
        