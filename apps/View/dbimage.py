#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>

from apps.BaseHandler import BaseHandler
from apps.utils import etagged
import web, StringIO

#读取数据库中的图像数据，如果为dbimage/cover则返回当前用户的封面图片
class DbImage(BaseHandler):
    __url__ = r"/dbimage/(.*)"
    @etagged()
    def GET(self, id_):
        if id_ != 'cover':
            return ''
        
        user = self.getcurrentuser() 
        if user and user.cover:
            web.header("Content-Type", "image/jpeg")
            return user.cover
        else:
            raise web.notfound()
            