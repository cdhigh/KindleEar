#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#中文讨论贴：http://www.hi-pda.com/forum/viewthread.php?tid=1213082
#Contributors:
# rexdf <https://github.com/rexdf>

import web

from apps.BaseHandler import BaseHandler
from apps.dbModels import *

from config import *

class AdvShare(BaseHandler):
    """ 设置归档和分享配置项 """
    def GET(self):
        user = self.getcurrentuser()
        current = 'advsetting'
        advcurr = 'share'
        savetoevernote = SAVE_TO_EVERNOTE
        savetowiz = SAVE_TO_WIZ
        shareonxweibo = SHARE_ON_XWEIBO
        shareontweibo = SHARE_ON_TWEIBO
        shareonfacebook = SHARE_ON_FACEBOOK
        shareontwitter = SHARE_ON_TWITTER
        shareontumblr = SHARE_ON_TUMBLR
        openinbrowser = OPEN_IN_BROWSER
        args = locals()
        args.pop('self')
        return self.render('advshare.html',"Share",**args)
        
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
        xweibo = bool(web.input().get('xweibo'))
        tweibo = bool(web.input().get('tweibo'))
        facebook = bool(web.input().get('facebook'))
        twitter = bool(web.input().get('twitter'))
        tumblr = bool(web.input().get('tumblr'))
        browser = bool(web.input().get('browser'))
        
        user.share_fuckgfw = fuckgfw
        user.evernote = evernote
        user.evernote_mail = evernote_mail
        user.wiz = wiz
        user.wiz_mail = wiz_mail
        user.xweibo = xweibo
        user.tweibo = tweibo
        user.facebook = facebook
        user.twitter = twitter
        user.tumblr = tumblr
        user.browser = browser
        user.put()
        
        raise web.seeother('')

class AdvUrlFilter(BaseHandler):
    """ 设置URL过滤器 """
    def GET(self):
        user = self.getcurrentuser()
        return self.render('advurlfilter.html',"Url Filter",current='advsetting',
            user=user,advcurr='urlfilter')
        
    def POST(self):
        user = self.getcurrentuser()
        
        url = web.input().get('url')
        if url:
            UrlFilter(url=url,user=user).put()
        raise web.seeother('')
        
class AdvDel(BaseHandler):
    #删除白名单或URL过滤器项目
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

class AdvWhiteList(BaseHandler):
    """ 设置邮件白名单 """
    def GET(self):
        user = self.getcurrentuser()
        return self.render('advwhitelist.html',"White List",current='advsetting',
            user=user,advcurr='whitelist')
        
    def POST(self):
        user = self.getcurrentuser()
        
        wlist = web.input().get('wlist')
        if wlist:
            WhiteList(mail=wlist,user=user).put()
        raise web.seeother('')