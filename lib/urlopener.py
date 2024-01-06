#!usr/bin/Python
# -*- coding:utf-8 -*-
"""为了应付时不时出现的Too many redirects异常，使用此类打开链接。
此类会自动处理redirect和cookie，同时增加了失败自动重试功能
2024: 移植到Python3后改用requests，其实已经很好了，但是requests默认没有超时时间，
所以还是继续使用此模块封装超时时间吧，并且去掉自动重试功能"""
import requests
from config import CONNECT_TIMEOUT

class UrlOpener:
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
    
    @classmethod
    def CodeMap(cls, errCode):
        des = cls._codeMapDict.get(errCode, None)
        return '%d %s' % (errCode, des) if des else str(errCode)
    
    def __init__(self, host=None, timeout=CONNECT_TIMEOUT, headers=None):
        self.host = host
        self.timeout = timeout
        self.initHeaders = headers
        self.session = requests.session()
        
    def open(self, url, data=None, headers=None):
        #出现异常时response不是合法的对象，使用一个模拟的
        r = requests.models.Response()
        r.status_code = 555
        
        #竟然实际中还碰到以//开头的URL，真是大千世界无奇不有
        if url.startswith(r"//"):
            url = "https:" + url
        elif url.startswith('www'):
            url = "https://" + url
            
        if url.startswith("data:"): #网页内嵌内容data url
            import base64, re
            #data:image/png;base64,iVBORw...
            rxDataUri = re.compile("^data:(?P<mime>[a-z]+/[a-z]+);base64,(?P<data>.*)$", re.I | re.M | re.DOTALL)
            m = rxDataUri.match(url)
            try:
                r._content = base64.b64decode(m.group("data").encode("ascii")) #return bytes
                r.status_code = 200
            except Exception as e:
                r.status_code = 404
        else:
            try:
                if data:
                    r = self.session.post(url, data=data, headers=self.GetHeaders(url, headers), timeout=self.timeout)
                else:
                    r = self.session.get(url, headers=self.GetHeaders(url, headers), timeout=self.timeout)
            except Exception as e:
                default_log.warn("url {} failed {}.".format(url, str(e)))
        
        #有些网页头部没有编码信息，则使用chardet检测编码，否则requests会认为text类型的编码为"ISO-8859-1"
        if "charset" not in r.headers.get("Content-Type", "").lower():
            r.encoding = None #r.apparent_encoding
        return r
        
    def GetHeaders(self, url=None, extHeaders=None):
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Win64; x64; Trident/5.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if self.addReferer and (self.host or url):
            headers["Referer"] = self.host if self.host else url
        
        if self.initHeaders:
            headers.update(self.initHeaders)
        if extHeaders:
            headers.update(extHeaders)
        return headers
