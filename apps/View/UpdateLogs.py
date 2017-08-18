#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>
import web

from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import etagged

class Uplogs(BaseHandler):
    __url__ = "/updatelogs"
    @etagged()
    def GET(self, tips=None):
        uplogs = UpdateLog.all()
        return self.render('updatelogs.html', "Update log", current='updatelogs', uplogs=uplogs, tips=tips)
    

    def POST(self):
        uplogs = UpdateLog.all()
        for log in uplogs:
            name = log.comicname
            count = int(web.input().get(name.encode("utf")))
            if count == 0:
                log.delete()
            elif count != log.updatecount:
                log.delete()
                dl = UpdateLog(comicname=name, updatecount=count)
                dl.put()

        newname = web.input().get("newname")
        newcount = web.input().get("newcount")
        if newname != "" and newcount != "":
            dl = UpdateLog(comicname=newname, updatecount=int(newcount))
            dl.put()
            
        tips = _("Settings Saved!")
        
        return self.GET(tips)
