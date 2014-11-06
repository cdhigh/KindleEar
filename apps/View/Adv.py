#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#中文讨论贴：http://www.hi-pda.com/forum/viewthread.php?tid=1213082
#Contributors:
# rexdf <https://github.com/rexdf>
import datetime, urllib
import web

from google.appengine.api import memcache

from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import local_time
from config import *

MEMC_ADV_ID = '!#AdvSettings@'

class AdvSettings(BaseHandler):
    """ 高级设置的主入口 """
    __url__ = "/advsettings"
    def GET(self):
        prevUrl = memcache.get(MEMC_ADV_ID)
        if prevUrl in (AdvShare.__url__, AdvUrlFilter.__url__, AdvWhiteList.__url__, AdvImport.__url__):
            raise web.seeother(prevUrl)
        else:
            memcache.set(MEMC_ADV_ID, AdvWhiteList.__url__, 86400)
            raise web.seeother(AdvWhiteList.__url__)

class AdvShare(BaseHandler):
    """ 设置归档和分享配置项 """
    __url__ = "/advshare"
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
        memcache.set(MEMC_ADV_ID, self.__url__, 86400)
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
        memcache.set(MEMC_ADV_ID, self.__url__, 86400)
        raise web.seeother('')

class AdvUrlFilter(BaseHandler):
    """ 设置URL过滤器 """
    __url__ = "/advurlfilter"
    def GET(self):
        user = self.getcurrentuser()
        memcache.set(MEMC_ADV_ID, self.__url__, 86400)
        return self.render('advurlfilter.html',"Url Filter",current='advsetting',
            user=user,advcurr='urlfilter')
        
    def POST(self):
        user = self.getcurrentuser()
        
        url = web.input().get('url')
        if url:
            UrlFilter(url=url,user=user).put()
        memcache.set(MEMC_ADV_ID, self.__url__, 86400)
        raise web.seeother('')
        
class AdvDel(BaseHandler):
    __url__ = "/advdel"
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
    __url__ = "/advwhitelist"
    def GET(self):
        user = self.getcurrentuser()
        memcache.set(MEMC_ADV_ID, self.__url__, 86400)
        return self.render('advwhitelist.html',"White List",current='advsetting',
            user=user,advcurr='whitelist')
        
    def POST(self):
        user = self.getcurrentuser()
        
        wlist = web.input().get('wlist')
        if wlist:
            WhiteList(mail=wlist,user=user).put()
        memcache.set(MEMC_ADV_ID, self.__url__, 86400)
        raise web.seeother('')

class AdvImport(BaseHandler):
    """ 导入自定义rss订阅列表，当前支持Opml格式 """
    __url__ = "/advimport"
    def GET(self, tips=None):
        user = self.getcurrentuser()
        memcache.set(MEMC_ADV_ID, self.__url__, 86400)
        return self.render('advimport.html',"Import",current='advsetting',
            user=user,advcurr='import',tips=tips)

    def POST(self):
        import opml
        x = web.input(importfile={})
        memcache.set(MEMC_ADV_ID, self.__url__, 86400)
        if 'importfile' in x:
            user = self.getcurrentuser()
            try:
                rsslist = opml.from_string(x.importfile.file.read())
            except Exception as e:
                return self.GET(str(e))
            
            for o in self.walkOutline(rsslist):
                title, url, isfulltext = o.text, urllib.unquote_plus(o.xmlUrl), o.isFulltext #isFulltext为非标准属性
                isfulltext = bool(isfulltext.lower() in ('true', '1'))
                if title and url:
                    rss = Feed.all().filter('book = ', user.ownfeeds).filter("url = ", url).get() #查询是否有重复的
                    if rss:
                        rss.title = title
                        rss.isfulltext = isfulltext
                        rss.put()
                    else:
                        Feed(title=title,url=url,book=user.ownfeeds,isfulltext=isfulltext,
                            time=datetime.datetime.utcnow()).put()
                            
            memcache.delete('%d.feedscount'%user.ownfeeds.key().id())
            raise web.seeother('/my')
        else:
            raise web.seeother('')
    
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
                (feed.title, urllib.quote_plus(feed.url), feed.isfulltext))
        outlines = '\n'.join(outlines)
        
        opmlfile = opmlTpl % (date, date, outlines)
        web.header("Content-Type","text/xml;charset=utf-8")
        web.header("Content-Disposition","attachment;filename=KindleEar_subscription.xml")
        return opmlfile.encode('utf-8')

