#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#封装后台的任务队列，以适用不同的平台部署要求
#Author: cdhigh <https://github.com/cdhigh>
import os, json

__TASK_QUEUE_SERVICE = os.getenv('TASK_QUEUE_SERVICE')
if __TASK_QUEUE_SERVICE == "gae":
    from google.cloud import tasks_v2
    DEFAULT_QUEUE_NAME = "default"

    def init_task_queue_service(app):
        pass

    #外部调用此接口即可
    def create_delivery_task(payload: dict):
        create_http_task('/worker', payload)

    def create_url2book_task(payload: dict):
        create_http_task('/url2book', payload)

    #创建一个任务
    #url: 任务要调用的链接
    #payload: 要传递给url的参数，为一个Python字典
    #返回创建的任务实例
    def create_http_task(url, payload):
        client = tasks_v2.CloudTasksClient()

        task = {"app_engine_http_request": {
            "http_method": tasks_v2.HttpMethod.GET,
            "relative_uri": url,}
            }
        if payload:
            task["app_engine_http_request"]["headers"] = {"Content-type": "application/json"}
            task["app_engine_http_request"]["body"] = json.dumps(payload).encode()
        return client.create_task(task=task)

        #httpRequest = tasks_v2.HttpRequest(http_method=tasks_v2.HttpMethod.GET, url=url,
        #        headers={"Content-type": "application/json"}, body=json.dumps(payload).encode(),)
        #task = tasks_v2.Task(httpRequest=httpRequest)
        #taskParent = client.queue_path(APP_ID, SERVER_LOCATION, DEFAULT_QUEUE_NAME)
        #return client.create_task(tasks_v2.CreateTaskRequest(parent=taskParent, task=task))
    
elif __TASK_QUEUE_SERVICE == 'celery':
    from celery import Celery, Task, shared_task
    from ..work.worker import WorkerImpl
    from ..work.url2book import Url2BookImpl

    def init_task_queue_service(app):
        class FlaskTask(Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
                    
        app.config.from_mapping(
            CELERY={'broker_url': app.config['CELERY_BROKER_URL'],
                'result_backend': app.config['CELERY_RESULT_BACKEND'],
                'task_ignore_result': True,
            },)

        celery_app = Celery(app.name, task_cls=FlaskTask)
        celery_app.config_from_object(app.config["CELERY"])
        celery_app.set_default()
        app.extensions["celery"] = celery_app
        return celery_app
    
    @shared_task(ignore_result=True)
    def start_celery_worker_impl(**payload):
        return WorkerImpl(**payload)

    @shared_task(ignore_result=True)
    def start_celery_url2book(**payload):
        return Url2BookImpl(**payload)

    def create_delivery_task(payload: dict):
        start_celery_worker_impl.delay(**payload)

    def create_url2book_task(payload: dict):
        start_celery_url2book.delay(**payload)

elif not __TASK_QUEUE_SERVICE:
    from ..work.worker import WorkerImpl
    from ..work.url2book import Url2BookImpl
    def create_delivery_task(payload: dict):
        return WorkerImpl(**payload)

    def create_url2book_task(payload: dict):
        return Url2BookImpl(**payload)

    def init_task_queue_service(app):
        pass
        
