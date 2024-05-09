#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#投递历史页面和维护投递历史
#Author: cdhigh <https://github.com/cdhigh>
import datetime
from operator import attrgetter
from flask import Blueprint, request, render_template, current_app as app
from flask_babel import gettext as _
from ..base_handler import *
from ..back_end.db_models import *

bpLogs = Blueprint('bpLogs', __name__)

@bpLogs.route("/logs", endpoint='Mylogs')
@login_required()
def Mylogs(user: KeUser):
    myLogs = GetOrderedDeliverLog(user.name, 10)

    #其他用户的推送记录
    logs = {}
    if user.name == app.config['ADMIN_NAME']:
        for u in KeUser.get_all(KeUser.name != app.config['ADMIN_NAME']):
            theLog = GetOrderedDeliverLog(u.name, 5)
            if theLog:
                logs[u.name] =  theLog

    return render_template('logs.html', tab='logs', mylogs=myLogs, logs=logs, utcnow=datetime.datetime.utcnow)

#每天自动运行的任务，清理过期log
@bpLogs.route("/removelogs")
def RemoveLogsRoute():
    return RemoveLogs()

def RemoveLogs():
    #停止过期用户的推送
    now = datetime.datetime.utcnow()
    for user in KeUser.select():
        if user.cfg('enable_send') and user.expires and (user.expires < now):
            user.set_cfg('enable_send', '')
            user.save()

    #清理30天之前的推送记录
    time30 = now - datetime.timedelta(days=30)
    cnt = DeliverLog.delete().where(DeliverLog.datetime < time30).execute()
    cnt += LastDelivered.delete().where(LastDelivered.datetime < time30).execute()
    return "{} lines delivery log removed.".format(cnt)

#查询推送记录，按时间倒排
def GetOrderedDeliverLog(userName, limit):
    myLogs = sorted(DeliverLog.get_all(DeliverLog.user == userName), key=attrgetter('datetime'), reverse=True)
    return myLogs[:limit]
