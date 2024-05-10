#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#投递历史页面和维护投递历史
#Author: cdhigh <https://github.com/cdhigh>
import os, shutil, datetime, time
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

    #清理临时目录
    ret = []
    tmpDir = app.config['KE_TEMP_DIR']
    if tmpDir and os.path.exists(tmpDir):
        ret.append(DeleteOldFiles(tmpDir, 1))

    #清理30天之前的推送记录
    time30 = now - datetime.timedelta(days=30)
    cnt = DeliverLog.delete().where(DeliverLog.datetime < time30).execute()
    cnt += LastDelivered.delete().where(LastDelivered.datetime < time30).execute()
    ret.append(f"Removed a total of {cnt} lines of delivery log.")
    return '<br/>'.join(ret)

#查询推送记录，按时间倒排
def GetOrderedDeliverLog(userName, limit):
    myLogs = sorted(DeliverLog.get_all(DeliverLog.user == userName), key=attrgetter('datetime'), reverse=True)
    return myLogs[:limit]

#删除某个目录下创建/修改时间超过多少天的文件和目录
def DeleteOldFiles(root_dir, days):
    cutoffTime = time.time() - (days * 24 * 60 * 60)
    fileCnt = 0
    dirCnt = 0
    for root, dirs, files in os.walk(root_dir, topdown=False):
        for file in files:
            filePath = os.path.join(root, file)
            if os.path.getmtime(filePath) < cutoffTime:
                try:
                    os.remove(filePath)
                    fileCnt += 1
                except:
                    pass

        for directory in dirs:
            dirPath = os.path.join(root, directory)
            #目录没有修改时间
            if os.path.getctime(dirPath) < cutoffTime:
                try:
                    shutil.rmtree(dirPath)
                    dirCnt += 1
                except:
                    pass

    return (f'Deleted a total of {fileCnt} temporary files in "{root_dir}".'
        f'<br/>Deleted a total of {dirCnt} temporary directories in "{root_dir}".')






