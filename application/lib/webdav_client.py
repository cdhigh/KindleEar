#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#最简 WebDAV 客户端类，支持：
#上传文件（PUT）
#创建目录（MKCOL）
#检查文件是否存在（HEAD）
#Author: cdhigh <https://github.com/cdhigh>
import os
from urllib.parse import urljoin, urlparse, urlunparse
from urlopener import UrlOpener

class WebdavError(Exception):
    def __init__(self, statusCode, message='', response=None):
        self.statusCode = statusCode
        self.message = message
        self.response = response
        super().__init__(self.__str__())

    def __str__(self):
        msg = f"Webdav failed: {self.statusCode}"
        if self.message:
            msg += f": {self.message}"
        return msg

#最简 WebDAV 客户端类
class SimpleWebdavClient:
    def __init__(self, host, port=None, username=None, password=None):
        if port:
            parsed = urlparse(host)
            port = parsed.port or port #还是优先使用host里面的port(如果存在的话)
            netloc = f'{parsed.hostname}:{port}'
            host = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        self.host = host if host.endswith('/') else host + '/'
        self.auth = (username, password) if username else None
        self.opener = UrlOpener(host=self.host)

    #上传一个文件内容，失败抛出异常
    #remotePath: 服务器目录
    #data: 文件二进制内容
    def upload(self, remotePath, data):
        url = urljoin(self.host, remotePath.replace('\\', '/').lstrip('/'))
        resp = self.opener.open(url, data=data, method='PUT', auth=self.auth)
        if resp.status_code not in (200, 201, 204):
            raise WebdavError(resp.status_code, resp.reason, resp)

    #查询服务器目录是否存在
    def fileExists(self, remotePath):
        url = urljoin(self.host, remotePath.replace('\\', '/').lstrip('/'))
        response = self.opener.open(url, method='HEAD', auth=self.auth)
        return response.status_code == 200

    #创建服务器目录
    def makeDir(self, remoteDir):
        url = urljoin(self.host, remoteDir.replace('\\', '/').rstrip('/') + '/')
        response = self.opener.open(url, method='MKCOL', auth=self.auth)
        return response.status_code in (201, 405)  # 405: Already exists

    # 递归创建目录（路径中的每一层）
    def ensureRemoteDir(self, remotePath):
        parts = remotePath.replace('\\', '/').strip('/').split('/')
        for i in range(1, len(parts) + 1):
            subdir = '/'.join(parts[:i])
            r = self.makeDir(subdir + '/')
