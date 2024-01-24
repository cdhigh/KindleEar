#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#一些常用工具函数

import os, sys, hashlib, base64, random, datetime
from urllib.parse import urlparse

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
def str_to_int(txt, default=0):
    try:
        return int(txt.strip())
    except:
        return default

#字符串转bool(txt)
def str_to_bool(txt):
    return (txt or '').lower().strip() in ('yes', 'true', 'on', '1')

def local_time(fmt="%Y-%m-%d %H:%M", tz=0):
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=tz)).strftime(fmt)

#隐藏真实email地址，使用星号代替部分字符
#输入单个email字符串或列表，返回部分隐藏的字符串
def hide_email(email):
    emailList = [email] if isinstance(email, str) else email
    newEmails = []
    for item in emailList:
        if '@' not in item:
            newEmails.append(item)
            continue

        item = item.split('@')
        if len(item[0]) < 4:
            return item[0][0] + '**@' + item[-1]
        to = item[0][0:2] + ''.join(['*' for s in item[0][2:-1]]) + item[0][-1]
        newEmails.append(to + '@' + item[-1])
    if not newEmails:
        return email
    elif len(newEmails) == 1:
        return newEmails[0]
    else:
        return newEmails

#隐藏真实的网址
def hide_website(site):
    if not site:
        return ''
        
    parts = urlparse(site)
    path = parts.path if parts.path else parts.netloc
    if '.' in path:
        pathArray = path.split('.')
        if len(pathArray[0]) > 4:
            pathArray[0] = pathArray[0][:2] + '**' + pathArray[0][-1]
        else:
            pathArray[0] = pathArray[0][0] + '**'
            pathArray[1] = pathArray[1][0] + '**'
        site = '.'.join(pathArray)
    elif len(path) > 4:
        site = path[:2] + '**' + path[-1]
    else:
        site = path[0] + '**'
    return site

#-----------以下几个函数为安全相关的
def new_secret_key(length=8):
    allchars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXZY0123456789'
    return ''.join([random.choice(allchars) for i in range(length)])
    
def ke_encrypt(txt: str, key: str):
    return _ke_auth_code(txt, key, 'ENCODE')
    
def ke_decrypt(txt: str, key: str):
    return _ke_auth_code(txt, key, 'DECODE')

def _ke_auth_code(txt: str, key: str, operation: str='DECODE'):
    if not txt:
        return ''

    key = hashlib.md5(key.encode('utf-8')).hexdigest()
    keyA = hashlib.md5(key[:16].encode('utf-8')).hexdigest()
    keyB = hashlib.md5(key[16:].encode('utf-8')).hexdigest()
    cryptKey = keyA + hashlib.md5(keyA.encode('utf-8')).hexdigest()
    keyLength = len(cryptKey)
    
    if operation == 'DECODE':
        txt = base64.urlsafe_b64decode(txt).decode('utf-8')
    else:
        txt = hashlib.md5((txt + keyB).encode('utf-8')).hexdigest()[:16] + txt
    stringLength = len(txt)
    
    result = ''
    box = list(range(256))
    rndkey = {}
    for i in range(256):
        rndkey[i] = ord(cryptKey[i % keyLength])
    
    j = 0
    for i in range(256):
        j = (j + box[i] + rndkey[i]) % 256
        tmp = box[i]
        box[i] = box[j]
        box[j] = tmp
    a = j = 0
    for i in range(stringLength):
        a = (a + 1) % 256
        j = (j + box[a]) % 256
        tmp = box[a]
        box[a] = box[j]
        box[j] = tmp
        result += chr(ord(txt[i]) ^ (box[(box[a] + box[j]) % 256]))

    if operation == 'DECODE':
        if result[:16] == hashlib.md5((result[16:] + keyB).encode('utf-8')).hexdigest()[:16]:
            return result[16:]
        else:
            return ''
    else:
        return base64.urlsafe_b64encode(result.encode('utf-8')).decode('utf-8')
