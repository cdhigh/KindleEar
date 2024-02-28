#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#任务队列rq
#Author: cdhigh <https://github.com/cdhigh>
import os, sys, json

#启动rq
#set FLASK_APP=main.py
#flask rq worker

from flask_rq2 import RQ

rq = RQ()

def init_task_queue_service(app):
    app.config['RQ_REDIS_URL'] = app.config['TASK_QUEUE_BROKER_URL']
    rq.init_app(app)
    #windows不支持，暂时屏蔽，正式版本需要取消注释
    #check_deliver.cron('0 */1 * * *', 'check_deliver') #每隔一个小时执行一次
    #remove_logs.cron('0 0 */1 * *', 'remove_logs') #每隔24小时执行一次
    return rq

@rq.job
def check_deliver():
    from ..view.deliver import MultiUserDelivery
    MultiUserDelivery()

@rq.job
def remove_logs():
    from ..view.logs import RemoveLogs
    RemoveLogs()

@rq.job
def start_rq_worker_impl(**payload):
    from ..work.worker import WorkerImpl
    return WorkerImpl(**payload)

@rq.job
def start_rq_url2book(**payload):
    from ..work.url2book import Url2BookImpl
    return Url2BookImpl(**payload)

def create_delivery_task(payload: dict):
    start_rq_worker_impl.queue(**payload)

def create_url2book_task(payload: dict):
    start_rq_url2book.queue(**payload)
