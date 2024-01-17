#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#基于UrlOpener实现一个简单的Browser(类似 mechanize)，给calibre的下载模块使用
#Author: cdhigh <https://github.com/cdhigh>
import io
from urllib.parse import urlparse
from urlopener import UrlOpener

class BrowserStateError(Exception):
    pass
class LinkNotFoundError(Exception):
    pass
class FormNotFoundError(Exception):
    pass

class UrlOpenerBytesIO(io.BytesIO):
    def __init__(self, buff, url):
        super().__init__(buff)
        self.url = url
    def geturl(self):
        return self.url

class UrlOpenerBrowser:
    def __init__(self, *args, **kwargs):
        self.addheaders = []
        self.passwords = {} #键为url，值为 (username, password)
        self.form = {}
        self.opener = UrlOpener()

    def set_request_gzip(self, handle: bool):
        self.handle_gzip = handle
    def set_handle_gzip(self, handle: bool):
        self.handle_gzip = handle
    def add_password(url: str, username: str, password: str):
        self.passwords[url] = (username, password)

    #返回的对象要有一个read()
    def open(self, url: str, data: dict=None, timeout: int=30):
        resp = self.opener.open(url, data, timeout=timeout)
        if resp.status_code == 200:
            #url_parts = urlparse(url)
            #if url_parts.path.lower().endswith(('.html', '.htm', '.xml', '.php', '.css', '.js')):
            #    return UrlOpenerBytesIO(resp.text.encode('utf-8'), url)
            #else:
            return UrlOpenerBytesIO(resp.content, url)
        else:
            return UrlOpenerBytesIO('', url)

    def open_novisit(self, url: str, data: dict=None, timeout: int=30):
        return self.open(url, data, timeout=timeout)

    def submit(self, *args, **kwds):
        pass
        #return self.open(self.click(*args, **kwds))

    def click(self, *args, **kwds):
        """See :meth:`mechanize.HTMLForm.click()` for documentation."""
        #if not self.viewing_html():
        #    raise BrowserStateError("not viewing HTML")
        #request = self.form.click(*args, **kwds)
        #return self._add_referer_header(request)
        pass

    def __getitem__(self, name):
        if self.form is None:
            raise BrowserStateError('No form selected')
        return self.form[name]

    def __setitem__(self, name, val):
        if self.form is None:
            raise BrowserStateError('No form selected')
        self.form[name] = val

    def select_form(self, name=None, predicate=None, nr=None, **attrs):
        pass

    def close(self):
        pass
    