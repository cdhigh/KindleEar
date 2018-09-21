#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
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
        return self.render('setting.html', "Setting",
            current='setting', user=user, mail_sender=SRC_EMAIL, tips=tips)
        
    def POST(self):
        user = self.getcurrentuser()
        webInput = web.input()
        kemail = webInput.get('kindleemail')
        mytitle = webInput.get("rt")
        sgenable = bool(webInput.get('sgenable'))
        sgapikey = webInput.get('sgapikey')
        if not kemail:
            tips = _("Kindle E-mail is requied!")
        elif not mytitle:
            tips = _("Title is requied!")
        elif sgenable and (not sgapikey):
            tips = _("Need sendgrid ApiKey!")
        else:
            user.kindle_email = kemail
            user.timezone = int(webInput.get('timezone', TIMEZONE))
            user.send_time = int(webInput.get('sendtime'))
            user.enable_send = bool(webInput.get('enablesend'))
            user.book_type = webInput.get('booktype')
            user.device = webInput.get('devicetype') or 'kindle'
            user.use_title_in_feed = bool(webInput.get('titlefrom') == 'feed')
            user.titlefmt = webInput.get('titlefmt')
            alldays = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
            user.send_days = [day for day in alldays if webInput.get(day)]
            user.merge_books = bool(webInput.get('mergebooks'))
            user.book_mode = webInput.get('bookmode')
            user.remove_hyperlinks = webInput.get('removehyperlinks')
            user.sgenable = sgenable
            user.sgapikey = sgapikey
            user.put()
            
            myfeeds = user.ownfeeds
            myfeeds.language = webInput.get("lng")
            myfeeds.title = mytitle
            myfeeds.keep_image = bool(webInput.get("keepimage"))
            myfeeds.oldest_article = int(webInput.get('oldest', 7))
            myfeeds.users = [user.name] if webInput.get("enablerss") else []
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