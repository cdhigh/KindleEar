#!usr/bin/Python
# -*- coding:utf-8 -*-
"""异步urlfetch封装类"""
from google.appengine.api import urlfetch
from google.appengine.runtime import apiproxy_errors
from config import CONNECTION_TIMEOUT

MAX_ASYNC_REQUESTS = 5 #最大支持10，数值越大越容易出现流量越限异常

class AsyncURLOpener:
    def __init__(self,log=None):
        self.actives = []
        self.pendings = []
        self.log = log if log else default_log
    
    def fetch(self, url, timeout=CONNECTION_TIMEOUT, *args):
        rpc = urlfetch.create_rpc(deadline=timeout)
        if len(self.actives) < MAX_ASYNC_REQUESTS:
            self.actives.append((rpc,url,args))
            urlfetch.make_fetch_call(rpc, url, allow_truncated=False,
                follow_redirects=True, validate_certificate=False)
        else:
            self.pendings.append((rpc,url,args))
        return rpc
    
    def get_result(self):
        #生成器，逐个返回成功的结果，失败的不再返回，内部记录logs
        while self.actives:
            rpc,url,args = self.actives.pop(0)
            success = False
            try:
                result = rpc.get_result()
            except apiproxy_errors.DeadlineExceededError:
                self.log.warn('async fetch timeout:%s' % url)
                continue
            except urlfetch.DownloadError as e:
                self.log.warn("async fetch error(%s):%s"%(str(e),url))
                continue #仅记录log，不用返回错误信息给上级
            except Exception as e:
                self.log.warn('%s:%s' % (type(e), url))
                continue
            else:
                success = True
            finally: #启动一个新的异步请求
                if self.pendings:
                    newrpc,newurl,newargs = self.pendings.pop(0)
                    self.actives.append((newrpc,newurl,newargs))
                    urlfetch.make_fetch_call(newrpc, newurl, allow_truncated=False,
                        follow_redirects=True, validate_certificate=False)
            if success:
                yield result,url,args