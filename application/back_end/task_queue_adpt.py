#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#封装后台的任务队列，以适用不同的平台部署要求
#Author: cdhigh <https://github.com/cdhigh>
import os, sys, json

__TASK_QUEUE_SERVICE = os.getenv('TASK_QUEUE_SERVICE')
if __TASK_QUEUE_SERVICE == "gae":
    from .task_queue_gae import *
    
elif __TASK_QUEUE_SERVICE == 'apscheduler':
    from .task_queue_apscheduler import *

elif __TASK_QUEUE_SERVICE == 'celery':
    from .task_queue_celery import *

elif __TASK_QUEUE_SERVICE == 'rq':
    from .task_queue_rq import *

elif not __TASK_QUEUE_SERVICE: #直接调用，并且不支持定时任务
    from ..work.worker import WorkerImpl
    from ..work.url2book import Url2BookImpl
    def create_delivery_task(payload: dict):
        return WorkerImpl(**payload)

    def create_url2book_task(payload: dict):
        return Url2BookImpl(**payload)

    def init_task_queue_service(app):
        pass
        
