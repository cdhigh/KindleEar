#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""requests默认没有使用超时时间，有时候会卡死，使用此模块封装超时时间和一些表单功能
为了尽量兼容calibre使用的mechanize无头浏览器，加了很多有用没用的接口
"""
import sys, requests, weakref, re, traceback
from types import MethodType
from urllib.request import urlopen #仅用来进行base64 data url解码
from urllib.parse import quote, unquote, urlunparse, urlparse, urlencode, parse_qs
from bs4 import BeautifulSoup
from html_form import HTMLForm

class UrlOpener:
    #headers 可以传入一个字典或元祖列表
    #file_stub 用于本地文件读取，如果为None，则使用python的open()函数
    def __init__(self, *, host=None, timeout=30, headers=None, file_stub=None, user_agent=None, **kwargs):
        self.host = host
        self.timeout = timeout or 30
        #addheaders不使用字典是为了和mechanize接口兼容
        self.addheaders = [ #下面的代码假定第一个元素为 'User-Agent'
            ('User-Agent', "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Win64; x64; Trident/5.0)"),
            ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
            ("Accept-Encoding", "gzip, deflate"),]
        headers = headers.items() if isinstance(headers, dict) else (headers or [])
        self.addheaders.extend([(key, value) for key, value in headers])
        if user_agent:
            self.addheaders[0] = ('User-Agent', user_agent)

        self.fs = file_stub #FsDictStub
        self.session = requests.session()
        self.prevRespRef = None #对Response实例的一个弱引用
        self.form = None
        self.soup = None
        self.history = []

    #默认情况如果data!=None，则使用post，否则使用get，可以使用method参数覆盖此默认行为
    #此函数不会抛出异常，判断 resp.status_code 即可
    def open(self, url, data=None, headers=None, timeout=None, method=None, **kwargs):
        self.prevRespRef = None
        self.form = None
        self.soup = None

        if isinstance(url, UrlRequest):
            req = url
            url = req.url
            data = req.data
            headers = req.headers
            timeout = req.timeout
            method = req.method
            self.history.append(req)
        else:
            self.history.append(UrlRequest(url=url, data=data, headers=headers, method=method, timeout=self.timeout))

        if url.startswith('file:'): #本地文件
            resp = self.open_local_file(url)
        elif url.startswith("data:"): #网页内嵌内容data url
            resp = self.decode_data_url(url)
        else:
            resp = self.open_remote_url(url, data, headers, timeout, method, **kwargs)

        return self.patch_response(resp)
    
    #远程连接互联网的url
    def open_remote_url(self, url, data, headers, timeout, method, **kwargs):
        timeout = timeout if timeout else self.timeout
        headers = self.get_headers(url, headers)
        method = 'POST' if data and (method != 'GET') else 'GET'
        url = self.build_url(url, data, method)
        if method == 'GET':
            req_func = self.session.get
            data = None
        else:
            req_func = self.session.post
        
        try:
            resp = req_func(url, data=data, headers=headers, timeout=timeout, **kwargs)
        except Exception as e:
            resp = requests.models.Response()
            resp.status_code = 555
            default_log.warning(f"open_remote_url: {method} {url} failed: {traceback.format_exc()}")
            
        #有些网页头部没有编码信息，则使用chardet检测编码，否则requests会认为text类型的编码为"ISO-8859-1"
        if "charset" not in resp.headers.get("Content-Type", "").lower():
            resp.encoding = None #resp.apparent_encoding
        return resp

    #兼容mechanize接口，给response添加一个几个方法和属性，避免其他人定义的recipe失效
    def patch_response(self, resp):
        resp_read_method = lambda self: self.content if self.status_code == 200 else b'' 
        resp.read = MethodType(resp_read_method, resp)
        resp.geturl = MethodType(lambda self: self.url, resp)
        resp.getcode = MethodType(lambda self: self.status_code, resp)
        resp.code = resp.status_code
        resp.get_all_header_names = MethodType(lambda self, normalize=True: self.headers.keys(), resp)
        resp.get_all_header_values = MethodType(lambda self, name, normalize=True: [self.headers.get(name)], resp)
        resp.info = MethodType(lambda self: self.headers, resp)
        resp.__getitem__ = MethodType(lambda self, name: self.headers.get(name), resp)
        resp.get = MethodType(lambda self, name, default=None: self.headers.get(name, default), resp)
        self.prevRespRef = weakref.ref(resp) #用于可能的select_form()操作
        return resp

    #构建最终要使用的url
    def build_url(self, url, data, method):
        if url.startswith("//"):
            url = f'http:{url}'
        elif url.startswith('www'):
            url = f'http://{url}'

        parts = urlparse(url)._replace(fragment='')
        if method == 'GET' and data:
            query = parse_qs(parts.query)
            query.update(data)
            query = urlencode(query, doseq=True)
            parts = parts._replace(query=query)

        return urlunparse(parts)

    #读取本地文件
    def open_local_file(self, url):
        url = url[7:] if url.startswith('file://') else url[5:]
        if url.startswith('//'):
            url = url[1:]
        plat = sys.platform.lower()
        if ('win32' in plat or 'win64' in plat) and url.startswith('/'): #windows平台
            url = url[1:]

        resp = requests.models.Response()
        try:
            if self.fs:
                resp._content = self.fs.read(url, 'rb')
            else:
                with read(url, 'rb') as f:
                    resp._content = f.read()
            resp.status_code = 200
        except Exception as e:
            resp.status_code = 404
            default_log.warning(f"open_local_file {url} failed: {str(e)}")
        return resp

    #将data url解码为二进制数据
    def decode_data_url(self, url):
        resp = requests.models.Response()
        try:
            resp._content = urlopen(url).read()
            resp.status_code = 200
        except Exception:
            resp.status_code = 404
        return resp

    def open_novisit(self, *args, **kwargs):
        return self.open(*args, **kwargs)

    #获取上次open()调用后的数据包的BeautifulSoup解析实例，不一定成功，如果数据包已经被垃圾回收则返回None
    def get_soup(self):
        if not self.soup:
            resp = self.prevRespRef() if self.prevRespRef else None
            if resp and resp.status_code == 200:
                self.soup = BeautifulSoup(resp.text, 'lxml')
        return self.soup

    def forms(self):
        soup = self.get_soup()
        return [HTMLForm(form) for form in soup.find_all('form')] if soup else []

    #选择一个form，接下来可以用来登录
    #name: 表单的名字
    #predicate: 一个回调函数，参数为HTMLForm对象
    #nr: 第几个表单，序号从0开始
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
        resp = self.prevRespRef() if self.prevRespRef else None
        if not resp or not self.soup or not self.form:
            resp = requests.models.Response()
            resp.status_code = 555
            return self.patch_response(resp)

        action = self.form.get('action') or resp.url
        method = self.form.get('method', 'GET').upper()
        payload = self.form.get_all_values()
        return self.open(action, data=payload, method=method)

    submit_selected = submit

    #找到一个符合条件的url
    def find_link(self, text=None, text_regex=None, name=None, name_regex=None, url=None, 
        url_regex=None, tag=None, predicate=None, nr=0):
        soup = self.get_soup()
        if not soup:
            return None
        links = soup.find_all('a', attrs={'href': True})
        if text:
            text = text.lower()
            links = [link for link in links if text in (link.string or '').lower()]
        elif text_regex:
            if isinstance(text_regex, (str, bytes)):
                text_regex = re.compile(text_regex, re.IGNORECASE)
            links = [link for link in links if text_regex.search((link.string or ''))]
        elif name:
            links = [link for link in links if link.get('name', None) == name]
        elif name_regex:
            if isinstance(name_regex, (str, bytes)):
                name_regex = re.compile(name_regex, re.IGNORECASE)
            links = [link for link in links if name_regex.search(link.get('name', ''))]
        elif url:
            url = url.lower()
            links = [link for link in links if url in link.get('href', '').lower()]
        elif url_regex:
            if isinstance(url_regex, (str, bytes)):
                url_regex = re.compile(url_regex, re.IGNORECASE)
            links = [link for link in links if url_regex.search(link.get('href', ''))]

        if nr and nr < len(links):
            return links[nr].get('href', None)
        elif links:
            return links[0].get('href', None)
        else:
            return None

    #找到并打开一个url，可以使用正则表达式
    def follow_link(link=None, **kwargs):
        if not link:
            link = self.find_link(**kwargs)

        if link:
            return self.open(link)
        else:
            resp = requests.models.Response()
            resp.status_code = 555
            resp._content = b''
            self.form = None
            self.soup = None
            self.prevRespRef = weakref.ref(resp)
            return self.patch_response(resp)

    #构建网络请求使用的header字典
    def get_headers(self, url=None, extra_headers=None):
        headers = {k: v for k, v in self.addheaders}
        if self.host:
            referer = self.host
        else:
            referer = urlparse(url).netloc if url else ''
        if referer:
            headers.setdefault('Referer', referer)
        if extra_headers:
            headers.update(extra_headers)
        return headers

    #添加或修改一个headers值
    def set_current_header(self, key, value):
        headers = {key: value for key, value in self.addheaders}
        headers[key] = value
        self.addheaders = [(k, v) for k, v in headers.items()]
        
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

    #设置登录账号或密码信息
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
    def add_client_certificate(self, *args, **kwargs):
        pass
    def geturl(self):
        return self.history[-1].url if self.history else ''
    def back(self, n=1):
        n = abs(n)
        while self.history and n:
            self.history.pop()
            n -= 1
        return self.open(self.history[-1]) if self.history else None
        
    def reload(self):
        pass
    def response(self):
        return self.prevRespRef() if self.prevRespRef else None

    @classmethod
    def CodeMap(cls, errCode):
        return '{} {}'.format(errCode, cls._codeMapDict.get(errCode, ''))

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
        429 : 'You exceeded your current quota',
        500 : 'Internal Server Error',
        501 : 'Not Implemented',
        502 : 'Bad Gateway',
        503 : 'Service Unavailable',
        504 : 'Gateway Timeout',
        505 : 'HTTP Version Not Supported',
        
        #------- Custom Code -----------------
        529 : 'OverQuota Error',
        530 : 'Timeout',
        531 : 'Response Too Large Error',
        532 : 'SSLCertificate Error',
        533 : 'UnAuthorized Error',
        534 : 'Download Error',
        535 : 'General Download Error',
        555 : 'Unknown Error',
    }

#只是为兼容 mechanize
class UrlRequest:
    def __init__(self, url, data=None, headers=None, origin_req_host=None, unverifiable=False, 
        visit=None, timeout=30, method=None, **kwargs):
        self.url = url
        self.data = data
        self.headers = headers or {}
        self.origin_req_host = origin_req_host
        self.unverifiable = unverifiable
        self.visit = visit
        self.timeout = timeout
        self.method = method
    def set_data(self, data):
        self.data = data
    def add_data(self, data):
        self.data = data
    def get_data(self):
        return self.data
    def add_header(self, key, val=None):
        self.headers[key] = val
    def get_header(self, key, default=None):
        return self.headers.get(key, default)
    def has_header(self, key):
        return key in self.headers
    add_unredirected_header = add_header
    def get_method(self):
        return self.method
    def has_data(self):
        return self.data is not None
    def has_proxy(self):
        return False
    def header_items(self):
        return list(self.headers.items())

