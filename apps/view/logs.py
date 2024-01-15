#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#投递历史页面和维护投递历史
import datetime
from operator import attrgetter
from flask import Blueprint, request, render_template
from flask_babel import gettext as _
from apps.base_handler import *
from apps.back_end.db_models import *
from google.appengine.api.datastore_errors import NeedIndexError
from config import ADMIN_NAME

bpLogs = Blueprint('bpLogs', __name__)

#查询推送记录，按时间倒排
def GetOrderedDeliverLogWithLimit(userName, limit):
    myLogs = list(DeliverLog.get_all(DeliverLog.username == userName))
    myLogs.sort(key=attrgetter('datetime'), reverse=True)
    return myLogs[:limit]

def GetOrderedLastDeliveredWithLimit(userName='', limit=100):
    if userName:
        myLogs = list(LastDelivered.get_all(LastDelivered.username == userName))
    else:
        myLogs = list(LastDelivered.get_all())
    myLogs.sort(key=attrgetter('datetime'), reverse=True)
    return myLogs[:limit]

@bpLogs.route("/logs", endpoint='Mylogs')
@login_required()
def Mylogs():
    user = get_login_user()
    myLogs = GetOrderedDeliverLogWithLimit(user.name, 10)

    #其他用户的推送记录
    logs = {}
    if user.name == ADMIN_NAME:
        for u in KeUser.get_all(KeUser.name != ADMIN_NAME):
            u1 = GetOrderedDeliverLogWithLimit(u.name, 5)
            if ul:
                logs[u.name] =  ul

    #管理员可以查看所有用户的已推送期号，其他用户只能查看自己的已推送期号
    if user.name == ADMIN_NAME:
        lastDelivered = GetOrderedLastDeliveredWithLimit()
    else:
        lastDelivered = GetOrderedLastDeliveredWithLimit(user.name, 100)

    if len(lastDelivered) == 0:
        lastDelivered = None

    return render_template('logs.html', tab='logs', mylogs=myLogs, logs=logs, lastDelivered=lastDelivered)

#每天自动运行的任务，清理过期log
@bpLogs.route("/removelogs")
def RemoveLogs():
    #停止过期用户的推送
    for user in KeUser.get_all(KeUser.enable_send == True):
        if user.expires and (user.expires < datetime.datetime.utcnow()):
            user.enable_send = False
            user.save()

    #清理3之前的推送记录
    cnt = 0
    for item in DeliverLog.get_all(DeliverLog.datetime < (datetime.datetime.utcnow() - datetime.timedelta(days=30))):
        cnt += 1
        item.delete()
    for item in LastDelivered.get_all(LastDelivered.datetime < (datetime.datetime.utcnow() - datetime.timedelta(days=90))):
        cnt += 1
        item.delete()

    return "{} lines delivery log removed.<br />".format(cnt)

#修改/删除已推送期号的AJAX处理函数
@bpLogs.post("/lastdelivered/<mgrType>", endpoint='LastDeliveredAjaxPost')
@login_required(forAjax=True)
def LastDeliveredAjaxPost(mgrType):
    user = get_login_user()
    mgrType = mgrType.lower()

    if mgrType == 'delete':
        id_ = request.form.get('id_')
        dbItem = LastDelivered.get_by_id_or_none(id_)
        if dbItem:
            dbItem.delete()
            return {'status': 'ok'}
        else:
            return {'status': _('The LastDelivered item ({}) not exist!').format(id_)}
    elif mgrType == 'change':
        id_ = request.form.get('id_')
        num = request.form.get('num')
        try:
            num = int(num)
        except:
            return {'status': _('The id or num is invalid!')}

        dbItem = LastDelivered.get_by_id_or_none(id_)
        if dbItem:
            dbItem.num = num
            dbItem.record = '' #手工修改了期号则清空文字描述
            dbItem.save()
            return {'status': 'ok', 'num': num}
        else:
            return {'status': _('The LastDelivered item ({}) not exist!').format(id_)}
    else:
        return {'status': 'Unknown command: {}'.format(mgrType)}
