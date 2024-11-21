#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#任务队列celery
#Author: cdhigh <https://github.com/cdhigh>

#启动celery
#celery -A main.celery_app worker --loglevel=info --logfile=d:\celery.log --concurrency=2 -P eventlet
#celery -A main.celery_app beat -s /home/celery/var/run/celerybeat-schedule --loglevel=info --logfile=d:\celery.log --concurrency=2 -P eventlet
import os
from celery import Celery, Task, shared_task
from celery.schedules import crontab

def init_task_queue_service(app):
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    broker_url = app.config['TASK_QUEUE_BROKER_URL']
    backend_url = broker_url
    transport_opts = {}
    if broker_url.startswith(('sqlite://', 'mysql://', 'postgresql://')):
        broker_url = f'sqla+{broker_url}'
    elif broker_url.startswith('file://'): #using a filesystem, ensure the folder exists
        if broker_url.startswith('file:////?/'): #windows
            dir_ = broker_url[11:]
        elif broker_url.startswith('file:///'): #linux/mac
            dir_ = broker_url[8:]
        else:
            raise ValueError('The value of TASK_QUEUE_BROKER_URL is invalid')
        dir_in = os.path.join(dir_, 'data_in')
        dir_out = os.path.join(dir_, 'data_out')
        dir_procsed = os.path.join(dir_, 'processed')
        transport_opts = {'data_folder_in': dir_in, 'data_folder_out': dir_out, 'processed_folder': dir_procsed, 
            'store_processed': True}
        for d in [dir_, dir_in, dir_out, dir_procsed]:
            if not os.path.isdir(d):
                os.makedirs(d)
        broker_url = 'filesystem://'

    if backend_url.startswith(('sqlite://', 'mysql://', 'postgresql://')):
        backend_url = f'db+{backend_url}'

    app.config.from_mapping(
        CELERY={'broker_url': broker_url,
            'result_backend': backend_url,
            'mongodb_backend_settings': {
                'database': 'kindleear',
                'taskmeta_collection': 'kindleear_taskqueue',
            },
            'broker_transport_options': transport_opts,
            'task_ignore_result': True,
        },)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()

    celery_app.conf.beat_schedule = {
        'check_deliver': {
            'task': 'check_deliver',
            'schedule': crontab(minute='50', hour='*/1'), #每个小时
            'args': []
        },
        'remove_logs': {
            'task': 'remove_logs', #每天凌晨
            'schedule': crontab(minute='0', hour='0', day_of_month='*/1'),
            'args': []
        },
    }
    app.extensions["celery"] = celery_app
    return celery_app

@shared_task(name="check_deliver", ignore_result=True)
def check_deliver():
    from ..view.deliver import MultiUserDelivery
    MultiUserDelivery()

@shared_task(name="remove_logs", ignore_result=True)
def remove_logs():
    from ..view.logs import RemoveLogs
    RemoveLogs()

@shared_task(ignore_result=True)
def start_celery_worker_impl(**payload):
    from ..work.worker import WorkerImpl
    return WorkerImpl(**payload)

@shared_task(ignore_result=True)
def start_celery_url2book(**payload):
    from ..work.url2book import Url2BookImpl
    return Url2BookImpl(**payload)

@shared_task(ignore_result=True)
def start_celery_notifynewsubs(**payload):
    from ..view.subscribe import NotifyNewSubscription
    return NotifyNewSubscription(**payload)

def create_delivery_task(payload: dict):
    start_celery_worker_impl.delay(**payload) #type:ignore

def create_url2book_task(payload: dict):
    start_celery_url2book.delay(**payload) #type:ignore

def create_notifynewsubs_task(payload: dict):
    start_celery_notifynewsubs.delay(**payload) #type:ignore

