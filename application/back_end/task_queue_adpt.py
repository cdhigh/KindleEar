#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#封装后台的任务队列，以适用不同的平台部署要求
#Author: cdhigh <https://github.com/cdhigh>
import os

__taskQueueSrv = os.getenv('TASK_QUEUE_SERVICE')
if __taskQueueSrv == "gae":
    from .task_queue_gae import * #type: ignore
elif __taskQueueSrv == 'apscheduler':
    from .task_queue_apscheduler import * #type: ignore
elif __taskQueueSrv == 'celery':
    from .task_queue_celery import * #type: ignore
elif __taskQueueSrv == 'rq':
    from .task_queue_rq import * #type: ignore
elif not __taskQueueSrv: #直接调用，并且不支持定时任务，主要测试使用
    def create_delivery_task(payload: dict):
        from ..work.worker import WorkerImpl
        return WorkerImpl(**payload)

    def create_url2book_task(payload: dict):
        from ..work.url2book import Url2BookImpl
        return Url2BookImpl(**payload)

    def create_notifynewsubs_task(payload: dict):
        from ..view.subscribe import NotifyNewSubscription
        return NotifyNewSubscription(**payload)

    def init_task_queue_service(app):
        pass
else:
    raise Exception(f'Invalid taskqueue service {__taskQueueSrv}')
