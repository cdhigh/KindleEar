#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#一些常用工具函数

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
        return base64.urlsafe_b64encode(result.encode('utf-8'))


#基于readability-lxml修改的提取网页标题的函数，增加CJK语种支持
def shorten_webpage_title(title):
    if not title:
        return ""
    
    zhPattern = re.compile('[\u4e00-\u9fff]+') # CJK unicode range
    
    #去除多余空格和转换一些HTML转义字符
    title = " ".join(title.split())
    entities = {"\u2014": "-", "\u2013": "-", "&mdash;": "-", "&ndash;": "-",
        "\u00A0": " ", "\u00AB": '"', "\u00BB": '"', "&quot;": '"'}
    for c, r in entities.items():
        if c in title:
            title = title.replace(c, r)
    
    orig = title

    candidates = set()

    for item in [".//h1", ".//h2", ".//h3"]:
        for e in list(doc.iterfind(item)):
            if e.text:
                add_match(candidates, e.text, orig)
            if e.text_content():
                add_match(candidates, e.text_content(), orig)

    for item in TITLE_CSS_HEURISTICS:
        for e in doc.cssselect(item):
            if e.text:
                add_match(candidates, e.text, orig)
            if e.text_content():
                add_match(candidates, e.text_content(), orig)

    if candidates:
        title = sorted(candidates, key=len)[-1]
    else:
        for delimiter in [" | ", " - ", " :: ", " / "]:
            if delimiter in title:
                parts = orig.split(delimiter)
                lp0 = parts[0].split() #split by space
                lpl = parts[-1].split()
                if len(lp0) >= 4:
                    title = parts[0]
                    break
                # added by cdhigh, CJK? no use space to split words
                elif zhPattern.search(parts[0]) and len(parts[0]) > 4:
                    title = parts[0]
                    break
                elif len(lpl) >= 4:
                    title = parts[-1]
                    break
                # added by cdhigh, CJK? no use space to split words
                elif zhPattern.search(parts[-1]) and len(parts[-1]) > 4:
                    title = parts[-1]
                    break
        else:
            if ": " in title:
                parts = orig.split(": ")
                if len(parts[-1].split()) >= 4:
                    title = parts[-1]
                # added by cdhigh
                elif zhPattern.search(parts[-1]) and len(parts[-1]) > 4:
                    title = parts[-1]
                else:
                    title = orig.split(": ", 1)[1]
    
    # added by cdhigh
    if zhPattern.search(title):
        if not 4 < len(title) < 100:
            return orig
    elif not 15 < len(title) < 150:
        return orig
    
    return title