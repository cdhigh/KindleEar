#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""requests默认没有超时时间，使用此模块封装超时时间和一些表单功能
为了尽量兼容mechanize，加了很多有用没用的接口
"""
import sys, requests, weakref
from urllib.request import urlopen #用来进行base64 data url解码
from bs4 import BeautifulSoup
from html_form import HTMLForm

class UrlOpener:
    def __init__(self, host=None, timeout=30, headers=None, **kwargs):
        self.host = host
        self.timeout = timeout
        self.addheaders = [("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")]
        if headers:
            for key, value in (headers.items() if isinstance(headers, dict) else headers):
                self.addheaders.append((key, value))
        if 'user_agent' in kwargs:
            self.addheaders.append(('User-Agent', kwargs.get('user_agent')))
        else:
            self.addheaders.append(('User-Agent', "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Win64; x64; Trident/5.0)"))
        self.fs = kwargs.get('file_stub', None) #FsDictStub
        self.session = requests.session()
        self.prevRespRef = None
        self.form = None
        self.soup = None

    def open(self, url, data=None, headers=None, timeout=None, **kwargs):
        #出现异常时response不是合法的对象，使用一个模拟的
        r = requests.models.Response()
        r.status_code = 555
        timeout = timeout if timeout else self.timeout
        self.prevRespRef = None
        self.form = None
        self.soup = None
        
        #竟然实际中还碰到以//开头的URL，真是大千世界无奇不有
        if url.startswith(r"//"):
            url = "https:" + url
        elif url.startswith('www'):
            url = "https://" + url
        
        if url.startswith('file:'): #本地文件
            url = url[7:] if url.startswith('file://') else url[5:]
            _plat = sys.platform.lower()
            if ('win32' in _plat or 'win64' in _plat) and url.startswith('/'): #windows平台
                url = url[1:]
            return self.open_local_file(url)
        elif url.startswith("data:"): #网页内嵌内容data url
            try:
                r._content = urlopen(url).read()
                r.status_code = 200
            except Exception:
                r.status_code = 404
        else:
            try:
                if data:
                    r = self.session.post(url, data=data, headers=self.get_headers(url, headers), timeout=timeout)
                else:
                    r = self.session.get(url, headers=self.get_headers(url, headers), timeout=timeout)
            except Exception as e:
                default_log.warning("url {} failed {}.".format(url, str(e)))
        
        #有些网页头部没有编码信息，则使用chardet检测编码，否则requests会认为text类型的编码为"ISO-8859-1"
        if "charset" not in r.headers.get("Content-Type", "").lower():
            r.encoding = None #r.apparent_encoding

        #兼容mechanize接口，给response添加一个read()，避免其他人定义的recipe失效
        r.read = lambda slf: slf.content if slf.status_code == 200 else b'' 
        self.prevRespRef = weakref.ref(r) #用于可能的select_form()操作
        return r
    
    def open_local_file(self, fileName):
        r = requests.models.Response()
        r.status_code = 555
        try:
            if self.fs:
                r._content = self.fs.read(url, 'rb')
            else:
                with read(url, 'rb') as f:
                    r._content = f.read()
            r.status_code = 200
        except:
            r.status_code = 404

        r.read = lambda slf: slf.content if slf.status_code == 200 else b'' 
        self.prevRespRef = weakref.ref(r)
        return r

    def open_novisit(self, *args, **kwargs):
        return self.open(*args, **kwargs)

    def get_soup(self):
        if not self.soup:
            resp = self.prevRespRef()
            if resp and resp.status_code == 200:
                self.soup = BeautifulSoup(resp.text, 'lxml')
        return self.soup

    def forms(self):
        soup = self.get_soup()
        return [HTMLForm(form) for form in soup.find_all('form')] if soup else []

    #选择一个form，接下来可以用来登录
    #name: 表单的名字
    #predicate: 一个回调函数，参数为HTMLForm对象
    #nr: 第几个表单
    def select_form(self, name=None, predicate=None, nr=None, **attrs):
        soup = self.get_soup()
        if not soup:
            return

        if name is not None:
            form = soup.find('form', attrs={"name": name})
            if form:
                self.form = HTMLForm(form)
        elif predicate is not None:
            for form in soup.find_all('form'):
                hForm = HTMLForm(form)
                if predicate(hForm):
                    self.form = HTMLForm(form)
                    break
        elif nr is not None:
            forms = list(soup.find_all('form'))
            if nr < len(forms):
                self.form = HTMLForm(forms[nr])
        elif attrs:
            form = soup.find('form', attrs=attrs)
            if form:
                self.form = HTMLForm(form)

    #提交之前选择出来的表单
    def submit(self, *args, **kwargs):
        resp = self.prevRespRef()
        if not resp or not self.soup or not self.form:
            return

        action = self.form.get('action') or resp.url
        #method = self.form.get('method')
        payload = {}
        for tag in self.form.find_all():
            name = tag.get('name')
            value = tag.get('value')
            if name is not None and value is not None:
                payload[name] = value

        return self.open(action, data=payload)

    #找到一个符合条件的url
    def find_link(self, text=None, text_regex=None, name=None, name_regex=None, url=None, 
        url_regex=None, tag=None, predicate=None, nr=0):
        soup = self.get_soup()
        if not soup:
            return None
        links = soup.find_all('a')
        if text:
            links = [link for link in links if text in link.string]
        if text_regex:
            links = [link for link in links if text_regex.search(link.string)]
        if name:
            links = [link for link in links if link.get('name') == name]
        if name_regex:
            links = [link for link in links if link.get('name') and name_regex.search(link.get('name'))]
        if url:
            links = [link for link in links if url in link.get('href', '')]
        if url_regex:
            links = [link for link in links if link.get('href') and url_regex.search(link.get('href'))]
        if nr and nr < len(links):
            return links[nr]
        elif links:
            return links[0]
        else:
            return None

    #找到并打开一个url，可以使用正则表达式
    def follow_link(link=None, **kwargs):
        if not link:
            link = self.find_link(**kwargs)

        if link:
            return self.open(link)
        else:
            r = requests.models.Response()
            r.status_code = 555
            r._content = b''
            self.prevRespRef = None
            self.form = None
            self.soup = None
            r.read = lambda slf: slf.content if slf.status_code == 200 else b'' 
            self.prevRespRef = weakref.ref(r)
            return r

    def get_headers(self, url=None, extra_headers=None):
        headers = {}
        for key, value in self.addheaders:
            headers[key] = value
        if (self.host or url) and 'Referer' not in headers:
            headers["Referer"] = self.host if self.host else url
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def set_current_header(self, key, value):
        for idx in range(len(self.addheaders)):
            if self.addheaders[idx][0] == key:
                self.addheaders[idx] = (key, value)
                break
        else:
            self.addheaders.append((key, value))

    def set_simple_cookie(self, name, value, domain, path='/'):
        self.session.cookies.set(name, value, domain)

    def close(self):
        if self.session is not None:
            self.session.cookies.clear()
            self.session.close()
            self.session = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __setitem__(self, name, value):
        if self.form:
            self.form[name] = value

    def set_handle_refresh(self, r):
        pass
    def set_handle_redirect(self, r):
        pass
    def set_debug_http(self, d):
        pass
    def set_handle_gzip(self, h):
        pass

    @classmethod
    def CodeMap(cls, errCode):
        des = cls._codeMapDict.get(errCode, None)
        return '{} {}'.format(errCode, des) if des else str(errCode)
    _codeMapDict = {
        200 : 'Ok',
        201 : 'Created',
        202 : 'Accepted',
        203 : 'Non-Authoritative Information',
        204 : 'No Content',
        205 : 'Reset Content',
        206 : 'Partial Content',
        300 : 'Multiple Choices',
        301 : 'Moved Permanently',
        302 : 'Found',
        303 : 'See Other',
        304 : 'Not Modified',
        305 : 'Use Proxy',
        307 : 'Temporary Redirect',
        400 : 'Bad Request',
        401 : 'Unauthorized',
        402 : 'Payment Required',
        403 : 'Forbidden',
        404 : 'Not Found',
        405 : 'Method Not Allowed',
        406 : 'Not Acceptable',
        407 : 'Proxy Authentication Required',
        408 : 'Request Timeout',
        409 : 'Conflict',
        410 : 'Gone',
        411 : 'Length Required',
        412 : 'Precondition Failed',
        413 : 'Request Entity Too Large',
        414 : 'Request-URI Too Long',
        415 : 'Unsupported Media Type',
        416 : 'Requested Range Not Satisfiable',
        417 : 'Expectation Failed',
        500 : 'Internal Server Error',
        501 : 'Not Implemented',
        502 : 'Bad Gateway',
        503 : 'Service Unavailable',
        504 : 'Gateway Timeout',
        505 : 'HTTP Version Not Supported',
        
        #------- Custom Code -----------------
        529 : 'OverQuotaError',
        530 : 'Timeout',
        531 : 'ResponseTooLargeError',
        532 : 'SSLCertificateError',
        533 : 'UnAuthorizedError',
        534 : 'DownloadError',
        535 : 'GeneralDownloadError',
    }


