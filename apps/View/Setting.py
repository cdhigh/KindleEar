#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#中文讨论贴：http://www.hi-pda.com/forum/viewthread.php?tid=1213082
#Contributors:
# rexdf <https://github.com/rexdf>

import gettext

import web

from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import etagged
from config import *

#import main

class Setting(BaseHandler):
    __url__ = "/setting"
    @etagged()
    def GET(self, tips=None):
        user = self.getcurrentuser()
        return self.render('setting.html',"Setting",
            current='setting',user=user,mail_sender=SRC_EMAIL,tips=tips)
        
    def POST(self):
        user = self.getcurrentuser()
        kemail = web.input().get('kindleemail')
        mytitle = web.input().get("rt")
        if not kemail:
            tips = _("Kindle E-mail is requied!")
        elif not mytitle:
            tips = _("Title is requied!")
        else:
            user.kindle_email = kemail
            user.timezone = int(web.input().get('timezone', TIMEZONE))
            user.send_time = int(web.input().get('sendtime'))
            user.enable_send = bool(web.input().get('enablesend'))
            user.book_type = web.input().get('booktype')
            user.device = web.input().get('devicetype') or 'kindle'
            user.use_title_in_feed = bool(web.input().get('titlefrom') == 'feed')
            user.titlefmt = web.input().get('titlefmt')
            alldays = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
            user.send_days = [day for day in alldays if web.input().get(day)]
            user.merge_books = bool(web.input().get('mergebooks'))
            user.put()
            
            myfeeds = user.ownfeeds
            myfeeds.language = web.input().get("lng")
            myfeeds.title = mytitle
            myfeeds.keep_image = bool(web.input().get("keepimage"))
            myfeeds.oldest_article = int(web.input().get('oldest', 7))
            myfeeds.users = [user.name] if web.input().get("enablerss") else []
            myfeeds.put()
            tips = _("Settings Saved!")
        
        return self.GET(tips)

class SetLang(BaseHandler):
    __url__ = "/lang/(.*)"
    def GET(self, lang):
        lang = lang.lower()
        if lang not in main.supported_languages:
            return "language invalid!"
        main.session.lang = lang
        raise web.seeother(r'/')