#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""linux平台的postfix的content filter，将其注册为postfix的content filter即可在VPS上实现类似部署在GAE的邮件中转功能。 
此文件是受 <https://github.com/thingless/mailglove> 启发而编写的。
核心 /etc/postfix/master.cf 配置行
mycustomfilter unix - n n - - pipe
  flags=F user=your_user argv=/path/to/email_filter.py
"""
import sys, requests

def process_email():
    data = sys.stdin.buffer.read()
    headers = {'Content-Type': 'application/octet-stream'}
    res = requests.post(url='http://172.0.0.1/mail', data=data, headers=headers)

    #错误码参考：<https://manpages.ubuntu.com/manpages/lunar/man3/sysexits.h.3head.html>
    #EX_UNAVAILABLE: 69, postfix会将邮件退回
    #EX_TEMPFAIL: 75, postfix之后会尝试再次投递
    #0: 成功
    return 1 #让postfix丢弃邮件

if __name__ == "__main__":
    sys.exit(process_email())
