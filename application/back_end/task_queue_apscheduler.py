#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#任务队列APScheduler
#Author: cdhigh <https://github.com/cdhigh>
import random

from flask_apscheduler import APScheduler
#from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED

scheduler = APScheduler()

#https://viniciuschiele.github.io/flask-apscheduler/rst/api.html
scheduler.api_enabled = True #提供/scheduler/jobs等几个有用的url

def init_task_queue_service(app):
    scheduler.init_app(app)
    #scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED)
    scheduler.start()
    app.extensions["scheduler"] = scheduler
    return scheduler

#APScheduler会自动删除trigger为date的任务，这个函数不需要了
#def job_listener(event):
#    scheduler.remove_job(event.job_id)

#@scheduler.task('interval', id='check_deliver', hours=1, misfire_grace_time=20*60, coalesce=True)
@scheduler.task('cron', minute=50, id='check_deliver', misfire_grace_time=20*60, coalesce=True)
def check_deliver():
    from ..view.deliver import MultiUserDelivery
    MultiUserDelivery()

@scheduler.task('interval', id='remove_logs', days=1, misfire_grace_time=20*60, coalesce=True)
def remove_logs():
    from ..view.logs import RemoveLogs
    RemoveLogs()

def create_delivery_task(payload: dict):
    from ..work.worker import WorkerImpl
    userName = payload.get('userName', '')
    recipeId = payload.get('recipeId', '')
    scheduler.add_job(f'Worker{random.randint(0, 1000)}', WorkerImpl, args=[userName, recipeId], 
        misfire_grace_time=20*60, replace_existing=True)

def create_url2book_task(payload: dict):
    from ..work.url2book import Url2BookImpl
    userName = payload.get('userName', '')
    urls = payload.get('urls', '')
    subject = payload.get('subject', '')
    action = payload.get('action', '')
    args = [userName, urls, subject, action]
    scheduler.add_job(f'Url2Book{random.randint(0, 1000)}', Url2BookImpl, args=args, misfire_grace_time=20*60,
        replace_existing=True)
