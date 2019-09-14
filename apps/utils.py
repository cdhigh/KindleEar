#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Author:
# cdhigh <https://github.com/cdhigh>
#Contributors:
# rexdf <https://github.com/rexdf>
import os, sys
from functools import wraps
from hashlib import md5
import web
from config import *
import datetime
import gettext
import re

#当异常出现时，使用此函数返回真实引发异常的文件名，函数名和行号
def get_exc_location():
    #追踪到最终的异常引发点
    exc_info = sys.exc_info()[2]
    last_exc = exc_info.tb_next
    while (last_exc.tb_next):
        last_exc = last_exc.tb_next
    fileName = os.path.basename(last_exc.tb_frame.f_code.co_filename)
    funcName = last_exc.tb_frame.f_code.co_name
    lineNo = last_exc.tb_frame.f_lineno
    last_exc = None
    exc_info = None
    return fileName, funcName, lineNo

#字符串转整数，出错则返回0
def str_to_int(txt):
    try:
        return int(txt.strip())
    except:
        return 0

def local_time(fmt="%Y-%m-%d %H:%M", tz=TIMEZONE):
    return (datetime.datetime.utcnow()+datetime.timedelta(hours=tz)).strftime(fmt)

def hide_email(email):
    """ 隐藏真实email地址，使用星号代替部分字符 """
    if not email or '@' not in email:
        return email
    email = email.split('@')
    if len(email[0]) < 4:
        return email[0][0] + '**@' + email[-1]
    to = email[0][0:2] + ''.join(['*' for s in email[0][2:-1]]) + email[0][-1]
    return to + '@' + email[-1]
    
def set_lang(lang):
    """ 设置网页显示语言 """
    tr = gettext.translation('lang', 'i18n', languages=[lang])
    tr.install(True)
    main.jjenv.install_gettext_translations(tr)

def fix_filesizeformat(value, binary=False):
    " bugfix for do_filesizeformat of jinja2 "
    bytes = float(value)
    base = binary and 1024 or 1000
    prefixes = [
        (binary and 'KiB' or 'kB'),(binary and 'MiB' or 'MB'),
        (binary and 'GiB' or 'GB'),(binary and 'TiB' or 'TB'),
        (binary and 'PiB' or 'PB'),(binary and 'EiB' or 'EB'),
        (binary and 'ZiB' or 'ZB'),(binary and 'YiB' or 'YB'),]
    if bytes < base:
        return '1 Byte' if bytes == 1 else '%d Bytes' % bytes
    else:
        for i, prefix in enumerate(prefixes):
            unit = base ** (i + 2)
            if bytes < unit:
                return '%.1f %s' % ((base * bytes / unit), prefix)
        return '%.1f %s' % ((base * bytes / unit), prefix)

        
#将etag应用于具体页面的装饰器
#此装饰器不能减轻服务器压力，但是可以减小客户端的再次加载页面时间
def etagged():
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwds):
            rsp_data = func(*args, **kwds)
            if type(rsp_data) is unicode:
                etag = '"%s"' % md5(rsp_data.encode('utf-8', 'ignore')).hexdigest()
            else:
                etag = '"%s"' % md5(rsp_data).hexdigest()
            #格式参见：<http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.26>
            n = set([x.strip().lstrip('W/') for x in web.ctx.env.get('HTTP_IF_NONE_MATCH', '').split(',')])
            if etag in n:
                raise web.notmodified()
            else:
                web.header('ETag', etag)
                web.header('Cache-Control', 'no-cache')
                return rsp_data
        return wrapper
    return decorator
    
#-----------以下几个函数为安全相关的
def new_secret_key(length=8):
    import random
    allchars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXZY0123456789'
    return ''.join([random.choice(allchars) for i in range(length)])
    
def ke_encrypt(s, key):
    return auth_code(s, key, 'ENCODE')
    
def ke_decrypt(s, key):
    return auth_code(s, key, 'DECODE')

def auth_code(string, key, operation='DECODE'):
    import hashlib,base64
    key = str(key) if key else ''
    string = str(string)
    key = hashlib.md5(key).hexdigest()
    keya = hashlib.md5(key[:16]).hexdigest()
    keyb = hashlib.md5(key[16:]).hexdigest()
    cryptkey = keya + hashlib.md5(keya).hexdigest()
    key_length = len(cryptkey)
    
    if operation == 'DECODE':
        string = base64.urlsafe_b64decode(string)
    else:
        string = hashlib.md5(string + keyb).hexdigest()[:16] + string
    string_length = len(string)
    
    result = ''
    box = range(256)
    rndkey = {}
    for i in range(256):
        rndkey[i] = ord(cryptkey[i % key_length])
    
    j = 0
    for i in range(256):
        j = (j + box[i] + rndkey[i]) % 256
        tmp = box[i]
        box[i] = box[j]
        box[j] = tmp
    a = j = 0
    for i in range(string_length):
        a = (a + 1) % 256
        j = (j + box[a]) % 256
        tmp = box[a]
        box[a] = box[j]
        box[j] = tmp
        result += chr(ord(string[i]) ^ (box[(box[a] + box[j]) % 256]))
    if operation == 'DECODE':
        if result[:16] == hashlib.md5(result[16:] + keyb).hexdigest()[:16]:
            return result[16:]
        else:
            return ''
    else:
        return base64.urlsafe_b64encode(result)
        