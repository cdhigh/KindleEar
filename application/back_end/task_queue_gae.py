#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#任务队列GAE
#Author: cdhigh <https://github.com/cdhigh>
import json
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
    
