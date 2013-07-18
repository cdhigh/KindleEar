#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""GAE中不能直接使用WEB.PY的session，使用此Store代替dbstore"""
from web.session import Store  
from google.appengine.api import memcache  
import web  
import time  
  
class MemcacheStore(Store):
    def __init__(self, memcache):
        self.memcache = memcache
        
    def __contains__(self, key):   
        data = self.memcache.get(key)   
        return bool(data)
    
    def __getitem__(self, key):   
        now = time.time()   
        value = self.memcache.get(key)  
        if not value:   
            raise KeyError   
        else:
            value['attime'] = now
            self.memcache.replace(key,value)
            return value
    
    def __setitem__(self, key, value):   
        now = time.time()
        value['attime'] = now
        s = self.memcache.get(key)
        if s:
            self.memcache.replace(key,value)
        else:
            self.memcache.add(key,value,web.config.session_parameters['timeout'])
    
    def __delitem__(self, key):
        self.memcache.delete(key)
    
    def cleanup(self, timeout): 
        pass
    