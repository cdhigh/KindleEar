#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>

import gettext

import web

from google.appengine.api import taskqueue

from collections import defaultdict
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import local_time
from books import BookClass

class Deliver(BaseHandler):
    """ 判断需要推送哪些书籍 """
    __url__ = "/deliver"
    def queueit(self, usr, bookid, separate, feedsId=None):
        param = {"u":usr.name, "id":bookid}
        if feedsId:
            param['feedsId'] = feedsId
        
        if usr.merge_books and not separate and not feedsId:
            self.queue2push[usr.name].append(str(bookid)) #合并推送
        else:
            taskqueue.add(url='/worker', queue_name="deliverqueue1", method='GET',
                params=param, target="worker")
        
    def flushqueue(self):
        for name in self.queue2push:
            param = {'u':name, 'id':','.join(self.queue2push[name])}
            taskqueue.add(url='/worker', queue_name="deliverqueue1", method='GET',
                params=param, target="worker")
        self.queue2push = defaultdict(list)
        
    def GET(self):
        username = web.input().get('u')
        id_ = web.input().get('id')
        feedsId = web.input().get('feedsId')
        if id_:
            id_ = [int(item) for item in id_.split('|') if item.isdigit()]
        
        self.queue2push = defaultdict(list)
        
        books = Book.all()
        if username: #现在投递【测试使用】，不需要判断时间和星期
            user = KeUser.all().filter("name = ", username).get()
            if not user or not user.kindle_email:
                return self.render('autoback.html', "Delivering", tips=_('The username not exist or the email of kindle is empty.'))

            sent = []
            if id_: #推送特定账号指定的书籍，这里不判断特定账号是否已经订阅了指定的书籍，只要提供就推送
                books2push = [Book.get_by_id(item) for item in id_ if Book.get_by_id(item)]
            else: #推送特定账号所有的书籍
                books2push = [item for item in books if username in item.users]
            
            for book in books2push:
                self.queueit(user, book.key().id(), book.separate, feedsId)
                sent.append(book.title)
            self.flushqueue()

            if len(sent):
                tips = _("Book(s) (%s) put to queue!") % u', '.join(sent)
            else:
                tips = _("No book to deliver!")

            return self.render('autoback.html', "Delivering", tips=tips)
        
        #定时cron调用
        sentcnt = 0
        for book in books:
            if not book.users: #没有用户订阅此书
                continue
            
            bkcls = None
            if book.builtin:
                bkcls = BookClass(book.title)
                if not bkcls:
                    continue
            
            #确定此书是否需要下载
            for u in book.users:
                user = KeUser.all().filter("enable_send = ",True).filter("name = ", u).get()
                if not user or not user.kindle_email:
                    continue
                    
                #先判断当天是否需要推送
                day = local_time('%A', user.timezone)
                usrdays = user.send_days
                if bkcls and bkcls.deliver_days: #按星期推送
                    days = bkcls.deliver_days
                    if not isinstance(days, list):
                        days = [days]
                    if day not in days:
                        continue
                elif usrdays and day not in usrdays: #为空也表示每日推送
                    continue
                    
                #时间判断
                h = int(local_time("%H", user.timezone)) + 1
                if h >= 24:
                    h -= 24
                if bkcls and bkcls.deliver_times:
                    times = bkcls.deliver_times
                    if not isinstance(times, list):
                        times = [times]
                    if h not in times:
                        continue
                elif user.send_time != h:
                    continue
                
                #到了这里才是需要推送的
                self.queueit(user, book.key().id(), book.separate)
                sentcnt += 1
        self.flushqueue()
        return "Put <strong>%d</strong> books to queue!" % sentcnt
        