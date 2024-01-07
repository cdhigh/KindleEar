#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>

import web

from apps.BaseHandler import BaseHandler
from apps.dbModels import *

from lib.autodecoder import UrlEncoding

class DbViewer(BaseHandler):
    __url__ = "/dbviewer"
    def GET(self):
        self.login_required('admin')
        #可以修改UrlEncoding，如果chardet自动检测的编码错误的话
        action = web.input().get('action')
        if action == 'modurlenc':
            id_ = int(web.input().get('id', 0))
            feedenc = web.input().get('feedenc')
            pageenc = web.input().get('pageenc')
            urlenc = UrlEncoding.get_by_id(id_)
            if urlenc:
                if feedenc: urlenc.feedenc = feedenc
                if pageenc: urlenc.pageenc = pageenc
                urlenc.put()
        elif action == 'delurlenc':
            id_ = int(web.input().get('id', 0))
            urlenc = UrlEncoding.get_by_id(id_)
            if urlenc:
                urlenc.delete()
        return self.render('dbviewer.html', "DbViewer",
            books=Book.all(),users=KeUser.all(),
            feeds=Feed.all().order('book'),urlencs=UrlEncoding.all())