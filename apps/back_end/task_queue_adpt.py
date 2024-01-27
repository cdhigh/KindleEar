#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#封装后台的任务队列，以适用不同的平台部署要求
#Author: cdhigh <https://github.com/cdhigh>

import json
from config import *

if TASK_QUEUE_TYPE == "gae":
    from google.cloud import tasks_v2
    DEFAULT_QUEUE_NAME = "default"

    #外部调用此接口即可
    def create_delivery_task(payload):
        create_http_task('/worker', payload)

    #创建一个任务
    #url: 任务要调用的链接
    #payload: 要传递给url的参数，为一个Python字典
    #返回创建的任务实例
    def create_http_task(url, payload):
        client = tasks_v2.CloudTasksClient()

        httpRequest = tasks_v2.HttpRequest(http_method=tasks_v2.HttpMethod.GET, url=url,
                headers={"Content-type": "application/json"}, body=json.dumps(payload).encode(),)
        task = tasks_v2.Task(httpRequest=httpRequest)
        taskParent = client.queue_path(APP_ID, SERVER_LOCATION, DEFAULT_QUEUE_NAME)
        return client.create_task(tasks_v2.CreateTaskRequest(parent=taskParent, task=task))

    
else:
    def create_delivery_task(payload):
        pass
