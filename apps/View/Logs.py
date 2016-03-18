#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>

import datetime
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import etagged

class Mylogs(BaseHandler):
    __url__ = "/logs"
    @etagged()
    def GET(self):
        user = self.getcurrentuser()
        mylogs = DeliverLog.all().filter("username = ", user.name).order('-time').fetch(limit=10)
        logs = {}
        if user.name == 'admin':
            for u in KeUser.all().filter("name != ", 'admin'):
                ul = DeliverLog.all().filter("username = ", u.name).order('-time').fetch(limit=5)
                if ul:
                    logs[u.name] =  ul
        return self.render('logs.html', "Deliver log", current='logs',
            mylogs=mylogs, logs=logs)
        
class RemoveLogs(BaseHandler):
    __url__ = "/removelogs"
    def GET(self):
        # 停止过期用户的推送
        for user in KeUser.all().filter('enable_send = ', True):
            if user.expires and (user.expires < datetime.datetime.utcnow()):
                user.enable_send = False
                user.put()
        
        query = DeliverLog.all()
        query.filter('datetime < ', datetime.datetime.utcnow() - datetime.timedelta(days=25))
        logs = query.fetch(1000)
        c = len(logs)
        db.delete(logs)
        
        return "%s lines log removed.<br />" % c