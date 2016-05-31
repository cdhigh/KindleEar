#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>

from apps.BaseHandler import BaseHandler
from apps.utils import etagged

class Home(BaseHandler):
    __url__ = r"/"
    @etagged()
    def GET(self):
        return self.render('home.html',"Home")