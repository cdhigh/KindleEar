#!usr/bin/Python
# -*- coding:utf-8 -*-
"""为了应付时不时出现的Too many redirects异常，使用此类打开链接。
此类会自动处理redirect和cookie，同时增加了失败自动重试功能"""
import urllib, urllib2, Cookie, urlparse, time
from google.appengine.api import urlfetch
from google.appengine.runtime.apiproxy_errors import OverQuotaError
from config import CONNECTION_TIMEOUT

class URLOpener:
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
    
    def __init__(self, host=None, maxfetchcount=2, maxredirect=5, 
              timeout=CONNECTION_TIMEOUT, addreferer=True, headers=None):
        self.cookie = Cookie.SimpleCookie()
        self.maxFetchCount = maxfetchcount
        self.maxRedirect = maxredirect
        self.host = host
        self.addReferer = addreferer
        self.timeout = timeout
        self.realurl = ''
        self.initHeaders = headers
    
    def open(self, url, data=None, headers=None):
        method = urlfetch.GET if data is None else urlfetch.POST
        self.realurl = url
        maxRedirect = self.maxRedirect
        
        class resp: #出现异常时response不是合法的对象，使用一个模拟的
            status_code=555
            content=''
            headers={}
        
        #竟然实际中还碰到以//开头的URL，真是大千世界无奇不有
        if url.startswith(r'//'):
            url = 'http:' + url
        elif url.startswith('www'):
            url = 'http://' + url
            
        response = resp()
        if url.startswith('data:'):
            import base64, re
            rxDataUri = re.compile("^data:(?P<mime>[a-z]+/[a-z]+);base64,(?P<data>.*)$", re.I | re.M | re.DOTALL)
            m = rxDataUri.match(url)
            try:
                response.content = base64.decodestring(m.group("data"))
                response.status_code = 200
            except Exception as e:
                response.status_code = 404
        else:
            while url and (maxRedirect > 0):
                cnt = 0
                while cnt < self.maxFetchCount:
                    try:
                        if data and isinstance(data, dict):
                            data = urllib.urlencode(self.EncodedDict(data))
                        response = urlfetch.fetch(url=url, payload=data, method=method,
                            headers=self._getHeaders(url, headers),
                            allow_truncated=False, follow_redirects=False, 
                            deadline=self.timeout, validate_certificate=False)
                    except urlfetch.DeadlineExceededError:
                        if response.status_code == 555:
                            response.status_code = 530
                        cnt += 1
                        time.sleep(1)
                    except urlfetch.ResponseTooLargeError:
                        if response.status_code == 555:
                            response.status_code = 531
                        break
                    except OverQuotaError:
                        if response.status_code == 555:
                            response.status_code = 529
                        cnt += 1
                        if cnt < self.maxFetchCount:
                            default_log.warn('OverQuotaError in url [%s], retry after 1 minute.' % url)
                            time.sleep(60)
                    except urlfetch.SSLCertificateError:
                        #有部分网站不支持HTTPS访问，对于这些网站，尝试切换http
                        if url.startswith(r'https://'):
                            url = url.replace(r'https://', r'http://')
                            if response.status_code == 555:
                                response.status_code = 532
                            continue #这里不用自增变量
                        else:
                            if response.status_code == 555:
                                response.status_code = 533
                            break
                    except urlfetch.DownloadError:
                        if response.status_code == 555:
                            response.status_code = 534
                        cnt += 1
                        #break
                    except Exception as e:
                        if response.status_code == 555:
                            response.status_code = 535
                            default_log.warn('url [%s] failed [%s].' % (url, str(e)))
                        break
                    else:
                        break
                
                data = None
                method = urlfetch.GET
                try:
                    self.SaveCookies(response.header_msg.getheaders('Set-Cookie'))
                except:
                    pass
                
                if response.status_code not in [300,301,302,303,307]: #只处理重定向信息
                    break
                
                urlnew = response.headers.get('Location')
                if urlnew and not urlnew.startswith("http"):
                    url = urlparse.urljoin(url, urlnew)
                else:
                    url = urlnew
                maxRedirect -= 1
        
        if maxRedirect <= 0:
            default_log.warn('Too many redirections:%s' % url)
        
        self.realurl = url
        return response
        
    def _getHeaders(self, url=None, extheaders=None):
        headers = {
             'User-Agent': "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Win64; x64; Trident/5.0)",
             'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                  }
        cookie = '; '.join(["%s=%s" % (v.key, v.value.encode('utf-8')) for v in self.cookie.values()])
        if cookie:
            headers['Cookie'] = cookie
            #default_log.warn(repr(self.cookie)) #TODO
        if self.addReferer and (self.host or url):
            headers['Referer'] = self.host if self.host else url
        
        if self.initHeaders:
            headers.update(self.initHeaders)
        if extheaders:
            headers.update(extheaders)
        return self.EncodedDict(headers)
        
    def SaveCookies(self, cookies):
        if not cookies:
            return
        self.cookie.load(cookies[0])
        for cookie in cookies[1:]:
            obj = Cookie.SimpleCookie()
            obj.load(cookie)
            for v in obj.values():
                self.cookie[v.key] = v.value
        #default_log.warn(repr(self.cookie)) #TODO
    
    #UNICODE编码的URL会出错，所以需要编码转换
    def EncodedDict(self, inDict):
        outDict = {}
        for k, v in inDict.iteritems():
            if isinstance(v, unicode):
                v = v.encode('utf-8')
            
            outDict[k] = v
        return outDict
        
        