#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#任务队列celery
#Author: cdhigh <https://github.com/cdhigh>

#启动celery
#celery -A main.celery_app worker --loglevel=info --logfile=d:\celery.log --concurrency=2 -P eventlet
#celery -A main.celery_app beat -s /home/celery/var/run/celerybeat-schedule --loglevel=info --logfile=d:\celery.log --concurrency=2 -P eventlet
from celery import Celery, Task, shared_task
from celery.schedules import crontab

def init_task_queue_service(app):
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
                
    app.config.from_mapping(
        CELERY={'broker_url': app.config['TASK_QUEUE_BROKER_URL'],
            'result_backend': app.config['TASK_QUEUE_RESULT_BACKEND'],
            'task_ignore_result': True,
        },)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()

    celery_app.conf.beat_schedule = {
        'check_deliver': {
            'task': 'check_deliver',
            'schedule': crontab(minute=0, hour='*/1'), #每个小时
            'args': []
        },
        'remove_logs': {
            'task': 'remove_logs', #每天凌晨
            'schedule': crontab(minute=0, hour=0, day_of_month='*/1'),
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

def create_delivery_task(payload: dict):
    start_celery_worker_impl.delay(**payload)

def create_url2book_task(payload: dict):
    start_celery_url2book.delay(**payload)
