#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#任务队列GAE接口实现
#Author: cdhigh <https://github.com/cdhigh>
import os, json
from urllib.parse import urlencode, urlparse
appId = os.getenv('APP_ID') #google cloud库会patchos.environ，需要先获取环境变量
serverLoc = os.getenv('SERVER_LOCATION')

from google.cloud import tasks_v2
DEFAULT_QUEUE_NAME = "default"

def init_task_queue_service(app):
    pass

#外部调用此接口即可
def create_delivery_task(payload: dict):
    create_http_task('/worker', payload, 'GET')

def create_url2book_task(payload: dict):
    create_http_task('/url2book', payload, 'POST') #payload里面的urls可能很长，需要使用POST

#创建一个任务
#url: 任务要调用的链接
#payload: 要传递给url的参数，为一个Python字典
#之所以使用HTTP.GET但是这里传入的是payload，而不是在调用方将payload合入url是为了兼容各种任务队列实现
#返回创建的任务实例
def create_http_task(url, payload, method='GET'):
    client = tasks_v2.CloudTasksClient()
    taskParent = client.queue_path(appId, serverLoc, DEFAULT_QUEUE_NAME)

    if method == 'GET':
        task = {"app_engine_http_request": {"http_method": tasks_v2.HttpMethod.GET}}
        #转换字典为查询字符串
        params = {'relative_uri': urlparse(url)._replace(query=urlencode(payload, doseq=True)).geturl()}
    else: #转换字典为post的body内容
        task = {"app_engine_http_request": {"http_method": tasks_v2.HttpMethod.POST}}
        params = {'relative_uri': url, 'headers': {"Content-type": "application/json"}, 'body': json.dumps(payload).encode()}
        
    task["app_engine_http_request"].update(params)
    return client.create_task(request={'parent': taskParent, 'task': task})
