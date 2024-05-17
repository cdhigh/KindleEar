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

    today = user.local_time("%Y-%m-%d ")
    return render_template('logs.html', tab='logs', mylogs=myLogs, logs=logs, today=today)

#每天自动运行的任务，清理过期log
@bpLogs.route("/removelogs")
def RemoveLogsRoute():
    return RemoveLogs()

def RemoveLogs():
    ret = []
    #停止过期用户的推送和删除过期的收件箱内容
    now = datetime.datetime.utcnow()
    cnt = 0
    for user in KeUser.select():
        if user.cfg('enable_send') and user.expires and (user.expires < now):
            user.set_cfg('enable_send', '')
            user.save()
        inbound_email = user.cfg('inbound_email', '')
        keep_in_email_days = int(user.cfg('keep_in_email_days'))
        if ('save' in inbound_email) and (keep_in_email_days > 0):
            expTime = now - datetime.timedelta(days=keep_in_email_days)
            #在GAE平台很多人经常出现索引建立失败的情况，这里不能使用除了相等之外的数据库组合查询和组合删除查询
            #所以就逐个删除好了
            items = [item for item in InBox.select(InBox.id, InBox.datetime).where(InBox.user == user.name) 
                if (item.datetime < expTime)]
            for item in items:
                item.delete_instance()
                cnt += 1


    #彻底删除一天以前被标识为已删除的邮件(针对所有用户)
    expTime = now - datetime.timedelta(days=1)
    items = [item for item in InBox.select(InBox.id, InBox.datetime).where(InBox.status == 'deleted') 
        if (item.datetime < expTime)]
    for item in items:
        item.delete_instance()
        cnt += 1

    if cnt:
        ret.append(f"Removed a total of {cnt} record of InBox.")
        
    #清理临时目录
    tmpDir = os.environ.get('KE_TEMP_DIR')
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






