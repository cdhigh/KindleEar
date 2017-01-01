#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>
from operator import attrgetter
import datetime
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import etagged
from google.appengine.api.datastore_errors import NeedIndexError

class Mylogs(BaseHandler):
    __url__ = "/logs"
    @etagged()
    def GET(self):
        user = self.getcurrentuser()
        try:
            mylogs = DeliverLog.all().filter("username = ", user.name).order('-time').fetch(limit=10)
        except NeedIndexError: #很多人不会部署，经常出现没有建立索引的情况，干脆碰到这种情况直接消耗CPU时间自己排序得了
            mylogs = sorted(DeliverLog.all().filter("username = ", user.name), key=attrgetter('time'), reverse=True)[:10]
        logs = {}
        if user.name == 'admin':
            for u in KeUser.all().filter("name != ", 'admin'):
                try:
                    ul = DeliverLog.all().filter("username = ", u.name).order('-time').fetch(limit=5)
                except NeedIndexError:
                    ul = sorted(DeliverLog.all().filter("username = ", user.name), key=attrgetter('time'), reverse=True)[:5]
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