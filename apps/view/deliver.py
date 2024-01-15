#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#投递相关功能

from collections import defaultdict
from flask import Blueprint, render_template, request
from flask_babel import gettext as _
from apps.back_end.task_queue_adpt import create_http_task
from apps.base_handler import *
from apps.back_end.db_models import *
from apps.utils import local_time
from books import BookClass

bpDeliver = Blueprint('bpDeliver', __name__)

#根据设置，将书籍预先放到队列之后一起推送，或马上单独推送
#queueToPush: 一个defaultdict(list)实例
#user: KeUser实例
#bookId: 书籍数据库实例ID
#separate: 是否单独推送
#feedIds: 自定义RSS的数据库实例ID，多个ID使用逗号分隔
def queueOneBook(queueToPush: defaultdict, user: KeUser, bookId: str, separate: bool, feedIds: str=None):
    param = {"u": user.name, "id_": bookId}
    if feedIds:
        param['feedIds'] = feedIds
    
    if user.merge_books and not separate and not feedIds:
        queueToPush[user.name].append(str(bookId)) #合并推送
    else:
        create_http_task("/worker", param)

#启动推送队列中的书籍
#queueToPush: 一个defaultdict(list)实例
def flushQueueToPush(queueToPush: defaultdict):
    for name in queueToPush:
        create_http_task("/worker", {'u': name, 'id_': ','.join(queueToPush[name])})

#判断需要推送哪些书籍
@bpDeliver.route("/deliver")
def Deliver():
    args = request.args
    userName = args.get('u')
    
    if userName: #现在投递【测试使用】，不需要判断时间和星期
        bookIds = args.get('id_')
        feedIds = args.get('feedIds')
        return SingleUserDeliver(userName, bookIds, feedIds)
    else: #如果不指定userName，说明是定时cron调用
        return MultiUserDeliver()


#判断所有账号所有书籍，确定哪些需要推送
def MultiUserDeliver():
    queueToPush = defaultdict(list)
    bookInstList = [item for item in Book.get_all() if item.users] #先剔除没有用户订阅的书籍
    sentCnt = 0
    for book in bookInstList:
        bkCls = None
        if book.builtin:
            bkCls = BookClass(book.title)
            if not bkCls:
                continue
        
        #确定此书是否需要下载
        for u in book.users:
            user = KeUser.select().where(KeUer.name == u).where(KeUser.enable_send == True).first()
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
            queueOneBook(queueToPush, user, book.key_or_id_string, book.separate)
            sentCnt += 1
    flushQueueToPush(queueToPush)
    return "Put {} books to queue!".format(sentCnt)

#判断指定用户的书籍和订阅哪些需要推送
#userName: 账号名
#bookIds: 书籍ID列表，逗号分隔的ID列表字符串，如果指定了这个参数，则不管用户是否订阅都直接推送
#feedIds: 如果不希望推送特定账号下所有订阅的自定义RSS，可以传入一个逗号分隔的ID列表字符串
def SingleUserDeliver(userName: str, bookIds: str=None, feedIds: str=None):
    user = KeUser.get_one(KeUser.name == userName)
    if not user or not user.kindle_email:
        return render_template('autoback.html', tips=_('The username not exist or the email of kindle is empty.'))

    sent = []
    if bookIds: #推送特定账号指定的书籍，这里不判断特定账号是否已经订阅了指定的书籍，只要提供就推送
        booksToPush = list(filter(bool, [Book.get_by_id_or_none(item) for item in bookIds.split(',')]))
    else: #推送特定账号所有的书籍
        booksToPush = [item for item in Book.get_all() if userName in item.users]
    
    bkQueue = {user.name: []}
    for book in booksToPush:
        queueOneBook(bkQueue, user, book.key_or_id_string, book.separate, feedIds)
        sent.append(book.title)
    self.flushQueueToPush(bkQueue)

    if len(sent):
        tips = _("Book(s) ({}) put to queue!").format(', '.join(sent))
    else:
        tips = _("No book to deliver!")

    return render_template('autoback.html', tips=tips)
