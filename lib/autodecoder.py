#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
KindleEar网页解码器，综合判断HTTP响应包头，HTML文件META信息，chardet检测编码来解码
对于chardet检测的情况，则通过缓存解码结果到数据库，实现准确性和效率的平衡。
Author: cdhigh <https://github.com/cdhigh>
"""
import urlparse, re
from google.appengine.ext import db
import chardet

from config import ALWAYS_CHAR_DETECT, TRUST_ENCODING_IN_HEADER_OR_META

class UrlEncoding(db.Model):
    #缓存网站的编码记录，chardet探测一次编码成功后，以后再也不需要重新探测
    netloc = db.StringProperty()
    feedenc = db.StringProperty()
    pageenc = db.StringProperty()

def HostEncoding(url, isfeed=True):
    #查询数据库对应此URL的编码信息，注意返回为unicode格式
    netloc = urlparse.urlsplit(url)[1]
    urlenc = UrlEncoding.all().filter('netloc = ', netloc).get()
    if urlenc:
        return urlenc.feedenc if isfeed else urlenc.pageenc
    else:
        return u''

class AutoDecoder:
    # 封装数据库编码缓存和同一网站文章的编码缓存
    # 因为chardet是非常慢的，所以需要那么复杂的缓存和其他特殊处理
    def __init__(self, isfeed=True):
        self.encoding = None
        self.isfeed = isfeed #True:Feed,False:page

    def decode(self, content, url=None, headers=None):
        if not content:
            return ''
            
        #ALWAYS_CHAR_DETECT是优先级最高的
        if ALWAYS_CHAR_DETECT:
            try:
                return content.decode(chardet.detect(content)['encoding'])
            except UnicodeDecodeError:
                pass #chardet检测错误，留待后面根据header解码
        
        #如果提供了响应包的headers，则优先使用headers中的编码和html文件中的meta编码
        #因为有些网页的chardet检测编码是错误的，使用html头可以避免此错误
        #但是html头其实也不可靠，所以再提取文件内的meta信息比对，两者一致才通过(有开关控制)
        #否则的话，还是相信chardet的结果吧
        encoding_m = get_encoding_from_content(content)
        encoding_h = get_encoding_from_headers(headers) if headers else None
        
        if encoding_m or encoding_h:
            if encoding_h == encoding_m:
                try: #'ignore'表明即使有部分解码出错，但是因为http和html都声明为此编码，则可信度已经很高了
                    return content.decode(encoding_h, 'ignore')
                except:
                    pass
            if TRUST_ENCODING_IN_HEADER_OR_META:
                if encoding_m:
                    try:
                        return content.decode(encoding_m)
                    except:
                        pass
                if encoding_h:
                    try:
                        return content.decode(encoding_h)
                    except:
                        pass
        
        return self.decode_by_chardet(content, url)
        
    def decode_by_chardet(self, content, url=None):
        """有双级缓存的解码器
        第一级缓存是上一篇文章的编码，第二级缓存是数据库保存的此网站编码"""
        result = content    
        if self.encoding: # 先使用上次的编码打开文件尝试
            try:
                result = content.decode(self.encoding)
            except UnicodeDecodeError: # 解码错误，使用自动检测编码
                encoding = chardet.detect(content)['encoding']
                try:
                    result = content.decode(encoding)
                except: # 还是出错，则不转换，直接返回
                    try:
                        result = content.decode(encoding, 'ignore')
                    except:
                        result = content
                    self.encoding = None
                else: # 保存下次使用，以节省时间
                    self.encoding = encoding
                    #同时保存到数据库
                    if url:
                        netloc = urlparse.urlsplit(url)[1]
                        urlenc = UrlEncoding.all().filter('netloc = ', netloc).get()
                        if urlenc:
                            enc = urlenc.feedenc if self.isfeed else urlenc.pageenc
                            if enc != encoding:
                                if self.isfeed:
                                    urlenc.feedenc = encoding
                                else:
                                    urlenc.pageenc = encoding
                                urlenc.put()
                        elif self.isfeed:
                            UrlEncoding(netloc=netloc,feedenc=encoding).put()
                        else:
                            UrlEncoding(netloc=netloc,pageenc=encoding).put()
        else:  # 暂时没有之前的编码信息
            if url:
                netloc = urlparse.urlsplit(url)[1]
                urlenc = UrlEncoding.all().filter('netloc = ', netloc).get()
            else:
                netloc = None
                urlenc = None
                
            if urlenc: #先看数据库有没有
                enc = urlenc.feedenc if self.isfeed else urlenc.pageenc
                if enc:
                    try:
                        result = content.decode(enc)
                    except UnicodeDecodeError: # 出错，重新检测编码
                        self.encoding = chardet.detect(content)['encoding']
                    else:
                        self.encoding = enc
                        default_log.warn('Decoded by buffered encoding(%s): [%s]' % (enc, url))
                        return result
                else: #数据库暂时没有数据
                    self.encoding = chardet.detect(content)['encoding']
            else:
                self.encoding = chardet.detect(content)['encoding']

            #使用检测到的编码解压
            try:
                result = content.decode(self.encoding)
            except: # 出错，则不转换，直接返回
                try:
                    result = content.decode(self.encoding, 'ignore')
                except:
                    result = content
            else:
                #保存到数据库
                if url:
                    newurlenc = urlenc if urlenc else UrlEncoding(netloc=netloc)
                    if self.isfeed:
                        newurlenc.feedenc = self.encoding
                    else:
                        newurlenc.pageenc = self.encoding
                    newurlenc.put()
        
        default_log.warn('Decoded (%s) by chardet: [%s]' % (self.encoding or 'Unknown Encoding', url))
        
        return result

def get_encoding_from_content(content):
    if content[:5] == '<?xml':
        charset_re = re.compile(r'<\?xml.*?encoding=["\']*(.+?)["\'].*\?>', re.I)
        m = charset_re.search(content[:100])
    else:
        charset_re = re.compile(r'<meta.*?charset=["\']*(.+?)["\'>]', re.I)
        m = charset_re.search(content[:1000])
    return rectify_encoding(m.group(1).strip("'\" ")) if m else None

def get_encoding_from_headers(headers):
    from cgi import parse_header
    content_type = headers.get('content-type')
    if not content_type:
        return None
    
    content_type, params = parse_header(content_type)
    return rectify_encoding(params['charset'].strip("'\" ")) if 'charset' in params else None

def rectify_encoding(encoding):
    "真实世界如此残酷，要如此复杂的纠正编码（修改自网络）"
    if not encoding:
        return None
    
    #有空格则取空格前的部分
    if encoding.find(' ') > 0:
        encoding = encoding.partition(' ')[0].strip()
    
    #常见的一些错误写法纠正
    errata = {'8858':'8859', '8559':'8859', '5889':'8859', '2313':'2312', '2132':'2312',
            '2321':'2312', 'gb-2312':'gb2312', 'gbk2312':'gbk', 'gbs2312':'gb2312',
            '.gb2312':'gb2312', '.gbk':'gbk', 'uft-8':'utf-8', 'utf8':'utf-8', 'x-euc':'euc'}
    for e in errata:
        if e in encoding:
            encoding = encoding.replace(e, errata[e])
            break

    # 调整为正确的编码方式
    if encoding.startswith('8859'):
        encoding = 'iso-%s' % encoding
    elif encoding.startswith('cp-'):
        encoding = 'cp%s' % encoding[3:]
    elif encoding.startswith('euc-'):
        encoding = 'euc_%s' % encoding[4:]
    elif encoding.startswith('windows') and not encoding.startswith('windows-'):
        encoding = 'windows-%s' % encoding[7:]
    elif encoding.find('iso-88') >= 0:
        encoding = encoding[encoding.find('iso-88'):]
    elif encoding.startswith('is0-'):
        encoding = 'iso%s' % encoding[4:]
    elif encoding.find('ascii') >= 0:
        encoding = 'ascii'
    
    #调整为python标准编码
    translate = { 'windows-874':'iso-8859-11', 'en_us':'utf8', 'macintosh':'iso-8859-1',
        'euc_tw':'big5_tw', 'th':'tis-620', 'zh-cn':'gbk', 'gb_2312-80':'gb2312',
        'iso-latin-1':'iso-8859-1', 'windows-31j':'shift_jis', 'x-sjis':'shift_jis',
        'none':'null', 'no':'null', '0ff':'null'}
    for t in translate:
        if encoding == t:
            encoding = translate[t]
            break
    
    return encoding.lower()
