#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#投递相关功能

from collections import defaultdict
from bottle import route, request
from apps.back_end import create_http_task
from apps.base_handler import *
from apps.db_models import *
from apps.utils import local_time
from books import BookClass

#根据设置，将书籍预先放到队列之后一起推送，或马上单独推送
#queueToPush: 一个defaultdict(list)实例
#user: KeUser实例
#bookId: 书籍数据库实例ID
#separate: 是否单独推送
#feedsId: 自定义RSS的数据库实例ID
def queueOneBook(queueToPush, user, bookId, separate, feedsId=None):
    param = {"u": user.name, "id_": bookId}
    if feedsId:
        param['feedsId'] = feedsId
    
    if user.merge_books and not separate and not feedsId:
        queueToPush[user.name].append(str(bookId)) #合并推送
    else:
        create_http_task("/worker", param)

#启动推送队列中的书籍
#queueToPush: 一个defaultdict(list)实例
def flushQueueToPush(queueToPush):
    for name in queueToPush:
        param = {'u': name, 'id_': ','.join(queueToPush[name])}
        create_http_task("/worker", param)

#判断需要推送哪些书籍
@route("/deliver")
def Deliver():
    query = request.query
    userName = query.u
    id_ = query.id_
    feedsId = query.feedsId
    if id_: #多个ID使用','分隔
        id_ = [int(item) for item in id_.split(',') if item.isdigit()]
    
    queueToPush = defaultdict(list)
    
    books = Book.all()
    if userName: #现在投递【测试使用】，不需要判断时间和星期
        user = KeUser.all().filter("name = ", userName).get()
        if not user or not user.kindle_email:
            return render_page('autoback.html', "Delivering", tips=_('The username not exist or the email of kindle is empty.'))

        sent = []
        if id_: #推送特定账号指定的书籍，这里不判断特定账号是否已经订阅了指定的书籍，只要提供就推送
            booksToPush = [Book.get_by_id(item) for item in id_ if Book.get_by_id(item)]
        else: #推送特定账号所有的书籍
            booksToPush = [item for item in books if userName in item.users]
        
        for book in booksToPush:
            queueOneBook(queueToPush, user, book.key().id(), book.separate, feedsId)
            sent.append(book.title)
        self.flushqueue()

        if len(sent):
            tips = _("Book(s) ({}) put to queue!").format(', '.join(sent))
        else:
            tips = _("No book to deliver!")

        return render_page('autoback.html', "Delivering", tips=tips)
    
    #定时cron调用
    sentCnt = 0
    for book in books:
        if not book.users: #没有用户订阅此书
            continue
        
        bkCls = None
        if book.builtin:
            bkCls = BookClass(book.title)
            if not bkCls:
                continue
        
        #确定此书是否需要下载
        for u in book.users:
            user = KeUser.all().filter("enable_send = ", True).filter("name = ", u).get()
            if not user or not user.kindle_email:
                continue
                
            #先判断当天是否需要推送
            day = local_time('%A', user.timezone)
            usrdays = user.send_days
            if bkCls and bkCls.deliver_days: #按星期推送
                days = bkCls.deliver_days
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
            if bkCls and bkCls.deliver_times:
                times = bkCls.deliver_times
                if not isinstance(times, list):
                    times = [times]
                if h not in times:
                    continue
            elif user.send_time != h:
                continue
            
            #到了这里才是需要推送的
            queueOneBook(queueToPush, user, book.key().id(), book.separate)
            sentCnt += 1
    flushQueueToPush()
    return "Put {} books to queue!".format(sentCnt)
