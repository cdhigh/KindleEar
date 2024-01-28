#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""让requests能访问本地文件，类似 file://filepath
session = requests.session()
session.mount('file://', LocalFileAdapter())
r = session.get('file:///path/to/your/file')
"""
import errno, os, stat, locale, io, requests, re

class LocalFileAdapter(requests.adapters.BaseAdapter):
    winAbsPathExpr = re.compile(r'^/{0,1}[A-Za-z]:[\\/].*$')

    def __init__(self, set_content_length=False):
        super().__init__()
        self._set_content_length = set_content_length

    def send(self, request, **kwargs):
        if request.method not in ("GET", "HEAD"):
            raise ValueError(f"Invalid request method {request.method}")

        path = request.url
        if path.startswith('file://'):
            path = path[7:]
        if winAbsPathExpr.match(path) and path.startswith('/'):
            path = path[1:]
        #path = os.path.abspath(path)
        resp = requests.Response()
        try:
            resp.raw = io.open(path, "rb")
            resp.raw.release_conn = resp.raw.close
        except IOError as e:
            if e.errno == errno.EACCES:
                resp.status_code = requests.codes.forbidden
            elif e.errno == errno.ENOENT:
                resp.status_code = requests.codes.not_found
            else:
                resp.status_code = requests.codes.bad_request

            resp_str = str(e).encode(locale.getpreferredencoding(False))
            resp.raw = io.BytesIO(resp_str)
            if self._set_content_length:
                resp.headers["Content-Length"] = len(resp_str)
            resp.raw.release_conn = resp.raw.close
        else:
            resp.status_code = requests.codes.ok
            resp.url = request.url
            if self._set_content_length:
                resp_stat = os.fstat(resp.raw.fileno())
                if stat.S_ISREG(resp_stat.st_mode):
                    resp.headers["Content-Length"] = resp_stat.st_size

        return resp

    def close(self):
        pass

