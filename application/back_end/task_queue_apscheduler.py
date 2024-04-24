#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#任务队列APScheduler
#Author: cdhigh <https://github.com/cdhigh>
import os, random

from flask_apscheduler import APScheduler
from apscheduler.schedulers.background import BackgroundScheduler

_broker_url = os.getenv('TASK_QUEUE_BROKER_URL')
if _broker_url.startswith('redis://'):
    import redis
    from apscheduler.jobstores.redis import RedisJobStore
    _client = RedisJobStore()
    _client.redis = redis.from_url(_broker_url)
    jobstores = {"default": _client}
elif _broker_url.startswith('mongodb://'):
    import pymongo
    from apscheduler.jobstores.mongodb import MongoDBJobStore
    _client = pymongo.MongoClient(_broker_url)
    jobstores = {"default": MongoDBJobStore(client=_client)}
elif _broker_url.startswith(('sqlite://', 'mysql://', 'postgresql://')):
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    jobstores = {"default": SQLAlchemyJobStore(url=_broker_url)}
elif _broker_url == 'memory':
    from apscheduler.jobstores.memory import MemoryJobStore
    jobstores = {"default": MemoryJobStore()}
else:
    raise ValueError('Unsupported TASK_QUEUE_BROKER_URL type: {_broker_url}')

scheduler = APScheduler(scheduler=BackgroundScheduler(jobstores=jobstores))

#https://viniciuschiele.github.io/flask-apscheduler/rst/api.html
scheduler.api_enabled = True #提供/scheduler/jobs等几个有用的url

def init_task_queue_service(app):
    scheduler.init_app(app)
    scheduler.start()
    app.extensions["scheduler"] = scheduler
    return scheduler

#@scheduler.task('interval', id='check_deliver', hours=1, misfire_grace_time=20*60, coalesce=True)
@scheduler.task('cron', minute=40, id='check_deliver', misfire_grace_time=20*60, coalesce=True)
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
    reason = payload.get('reason', 'cron')
    scheduler.add_job(f'Worker{random.randint(0, 1000)}', WorkerImpl, args=[userName, recipeId, reason], 
        misfire_grace_time=20*60, replace_existing=True)

def create_url2book_task(payload: dict):
    from ..work.url2book import Url2BookImpl
    userName = payload.get('userName', '')
    urls = payload.get('urls', '')
    title = payload.get('title', '')
    key = payload.get('key', '')
    action = payload.get('action', '')
    text = payload.get('text', '')
    args = [userName, urls, title, key, action, text]
    scheduler.add_job(f'Url2Book{random.randint(0, 1000)}', Url2BookImpl, args=args, misfire_grace_time=20*60,
        replace_existing=True)
