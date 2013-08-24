#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
电子书基类，每本投递到kindle的书籍抽象为这里的一个类

"""

import os, re, urllib, urlparse, random, imghdr, logging
from datetime import datetime
from urllib2 import *
import chardet
from google.appengine.api import urlfetch
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext import db

from bs4 import BeautifulSoup, Comment
from lib import feedparser
from lib.readability import readability
from lib.urlopener import URLOpener

from calibre.utils.img import rescale_image, mobify_image

from config import *

class UrlEncoding(db.Model):
    #缓存网站的编码记录，探测一次编码成功后，以后再也不需要重新探测
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
        
    def decode(self, content, url):
        result = content
        if not ALWAYS_CHAR_DETECT and self.encoding: # 先使用上次的编码打开文件尝试
            try:
                result = content.decode(self.encoding)
            except UnicodeDecodeError: # 解码错误，使用自动检测编码
                encoding = chardet.detect(content)['encoding']
                try:
                    result = content.decode(encoding)
                except UnicodeDecodeError: # 还是出错，则不转换，直接返回
                    self.encoding = None
                    result = content
                else: # 保存下次使用，以节省时间
                    self.encoding = encoding
                    #同时保存到数据库
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
            netloc = urlparse.urlsplit(url)[1]
            urlenc = UrlEncoding.all().filter('netloc = ', netloc).get()
            if urlenc: #先看数据库有没有
                enc = urlenc.feedenc if self.isfeed else urlenc.pageenc
                if enc:
                    try:
                        result = content.decode(enc)
                    except UnicodeDecodeError: # 出错，重新探测编码
                        self.encoding = chardet.detect(content)['encoding']
                    else:
                        self.encoding = enc
                        return result
                else: #数据库暂时没有数据
                    self.encoding = chardet.detect(content)['encoding']
            else:
                self.encoding = chardet.detect(content)['encoding']
            
            #使用探测到的编码解压
            try:
                result = content.decode(self.encoding)
            except UnicodeDecodeError: # 出错，则不转换，直接返回
                result = content
            else:
                #保存到数据库
                newurlenc = urlenc if urlenc else UrlEncoding(netloc=netloc)
                if self.isfeed:
                    newurlenc.feedenc = self.encoding
                else:
                    newurlenc.pageenc = self.encoding
                newurlenc.put()
        return result
        
class BaseFeedBook:
    """ base class of Book """
    title                 = ''
    __author__            = ''
    description           = ''
    max_articles_per_feed = 30
    oldest_article        = 7 #下载多长时间之内的文章，单位为天，0则不限制
    host                  = None # 有些网页的图像下载需要请求头里面包含Referer,使用此参数配置
    network_timeout       = None  # None则使用默认
    fetch_img_via_ssl     = False # 当网页为https时，其图片是否也转换成https
    language = 'und' #最终书籍的语言定义，比如zh-cn,en等
    
    #下面这两个编码建议设置，如果留空，则使用自动探测解码，稍耗费CPU
    feed_encoding = '' # RSS编码，一般为XML格式，直接打开源码看头部就有编码了
    page_encoding = '' # 页面编码，获取全文信息时的网页编码
    
    # 题图文件名，格式：gif(600*60)，所有图片文件存放在images/下面，文件名不需要images/前缀
    # 如果不提供此图片，软件使用PIL生成一个，但是因为GAE不能使用ImageFont组件
    # 所以字体很小，而且不支持中文标题，使用中文会出错
    mastheadfile = DEFAULT_MASTHEAD
    
    coverfile = DEFAULT_COVER #封面图片文件
    
    keep_image = True #生成的MOBI是否需要图片
    
    #是否按星期投递，留空则每天投递，否则是一个星期字符串列表
    #'Monday','Tuesday',...,'Sunday'，大小写敏感
    deliver_days = []
    
    #设置是否使用readability-lxml(Yuri Baburov)自动处理网页
    #正常来说，大部分的网页，readability处理完后的效果都不错
    #不过如果你需要更精细的控制排版和内容，可以设置为False
    #然后使用下面的一些选项和回调函数自己处理
    #一旦设置此选项为True，则没有必要关注其他的内容控制选项
    fulltext_by_readability = True
    
    #如果为True则使用instapaper服务先清理网页，否则直接连URL下载网页内容
    #instapaper的服务不太稳定，经常连接超时，建议设置为False
    #这样你需要自己编程清理网页，建议使用下面的keep_only_tags[]工具
    fulltext_by_instapaper = False
    
    # 背景知识：下面所说的标签为HTML标签，比如'body','h1','div','p'等都是标签
    
    # 仅抽取网页中特定的标签段，在一个复杂的网页中抽取正文，这个工具效率最高
    # 比如：keep_only_tags = [dict(name='div', attrs={'id':['article']}),]
    # 这个优先级最高，先处理了这个标签再处理其他标签。
    keep_only_tags = []
    
    # 顾名思义，删除特定标签前/后的所有内容，格式和keep_only_tags相同
    remove_tags_after = []
    remove_tags_before = []
    
    # 内置的几个必须删除的标签，不建议子类修改
    insta_remove_tags = ['script','object','video','embed','iframe','noscript']
    insta_remove_attrs = ['title','width','height','onclick','onload','id','class']
    insta_remove_classes = []
    insta_remove_ids = ['controlbar_container','left_buttons','right_buttons','title_label',]
    
    # 子类定制的HTML标签清理内容
    remove_tags = [] # 完全清理此标签
    remove_ids = [] # 清除标签的id属性为列表中内容的标签
    remove_classes = [] # 清除标签的class属性为列表中内容的标签
    remove_attrs = [] # 清除所有标签的特定属性，不清除标签内容
    
    # 一个字符串列表，可以包含正则表达式，在此列表中的url不会被下载
    # 可用于一些注定无法下载的链接，以便节省时间
    url_filters = []
    
    #每个子类必须重新定义这个属性，为RSS/网页链接列表
    #每个链接格式为元组：(分节标题, URL, fulltext)
    #最后一项fulltext是可选的，如果存在，取值为True/False
    #注意，如果分节标题是中文的话，增加u前缀，比如
    #(u'8小时最热', 'http://www.qiushibaike.com'),
    feeds = []
    
    #几个钩子函数，基类在适当的时候会调用，
    #子类可以使用钩子函数进一步定制
    
    #普通Feed在网页元素拆分分析前调用，全文Feed在FEED拆分前调用
    #网络上估计90%的RSS都是普通Feed，只有概要信息
    #content为网页字符串，记得处理后返回字符串
    def preprocess(self, content):
        return content
    
    #网页title处理，比如去掉网站标识，一长串的SEQ字符串等
    #返回处理后的title
    def processtitle(self, title):
        return re.sub(r'(\n)+', '', title)
    
    #如果要处理图像，则在处理图片前调用此函数，可以处理和修改图片URL等
    def soupbeforeimage(self, soup):
        return None
        
    #BeautifulSoup拆分网页分析处理后再提供给子类进一步处理
    #soup为BeautifulSoup实例引用，直接在soup上处理即可，不需要返回值
    def soupprocessex(self, soup):
        return None
    
    #Items()生成器里面每个Feed返回给MOBI生成模块前对内容的最后处理机会
    #content为网页字符串，记得返回处理后的字符串
    def postprocess(self, content):
        return content
    
    #------------------------------------------------------------
    # 下面的内容为类实现细节
    #------------------------------------------------------------
    def __init__(self, log=None):
        self.log = default_log if log is None else log
        self.compiled_urlfilters = []
    
    @property
    def timeout(self):
        return self.network_timeout if self.network_timeout else CONNECTION_TIMEOUT
        
    def isfiltered(self, url):
        if not self.url_filters:
            return False
        elif not self.compiled_urlfilters:
            self.compiled_urlfilters = [re.compile(unicode(flt), re.I) for flt in self.url_filters]
        
        if not isinstance(url, unicode):
            url = unicode(url)
        for flt in self.compiled_urlfilters:
            if flt.match(url):
                return True
        return False
        
    @classmethod
    def urljoin(self, base, url):
        #urlparse.urljoin()处理有..的链接有点问题，此函数修正此问题。
        join = urlparse.urljoin(base,url)
        url = urlparse.urlsplit(join)
        path = os.path.normpath(url.path)
        return urlparse.urlunsplit((url.scheme,url.netloc,path,url.query,url.fragment))

    def FragToXhtml(self, content, title, htmlencoding='utf-8', addtitleinbody=False):
        #将HTML片段嵌入完整的XHTML框架中
        frame = u"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head><meta http-equiv="Content-Type" content="text/html; charset=%s">
<title>%s</title>
<style type="text/css">
    p{text-indent:2em;}
    h1{font-weight:bold;}
</style>
</head><body>
%s
<p>%s</p>
</body></html>
"""
        if content.find('<html') > 0:
            return content
        else:
            t = u"<h1>%s</h1>" % title if addtitleinbody else ""
            if not htmlencoding:
                htmlencoding = 'utf-8'
            return frame % (htmlencoding, title, t, content)
    
    def FetchTitle(self, content, default=' '):
        pn = re.compile(r'<title.*?>(.*?)</title>', re.S|re.I)
        mt = pn.search(content)
        return mt.group(1) if mt else default
        
    def url_unescape(self, value):
        s = urllib.unquote_plus(value)
        if isinstance(s, str):
            s = s.decode("utf-8")
        return s
        
    def ParseFeedUrls(self):
        """ return list like [(section,title,url,desc),..] """
        urls = []
        tnow = datetime.utcnow()
        urladded = set()
                
        for feed in self.feeds:
            section, url = feed[0], feed[1]
            isfulltext = feed[2] if len(feed) > 2 else False
            timeout = self.timeout+10 if isfulltext else self.timeout
            opener = URLOpener(self.host, timeout=timeout)
            result = opener.open(url)
            if result.status_code == 200 and result.content:
                if self.feed_encoding:
                    content = result.content.decode(self.feed_encoding)
                else:
                    content = AutoDecoder(True).decode(result.content,url)    
                feed = feedparser.parse(content)
                
                for e in feed['entries'][:self.max_articles_per_feed]:
                    if self.oldest_article > 0 and hasattr(e, 'updated_parsed'):
                        updated = e.updated_parsed
                        if updated:
                            delta = tnow - datetime(*(updated[0:6]))
                            if delta.days*86400+delta.seconds > 86400*self.oldest_article:
                                self.log.debug("article '%s' is too old"%e.title)
                                continue
                    #支持HTTPS
                    urlfeed = e.link.replace('http://','https://') if url.startswith('https://') else e.link
                    if urlfeed in urladded:
                        continue
                        
                    desc = None
                    if isfulltext:
                        if hasattr(e, 'content') and e.content[0]['value']:
                            desc = e.content[0]['value']
                        elif hasattr(e, 'description'):
                            desc = e.description
                        else:
                            self.log.warn('fulltext feed item no has desc,link to webpage for article.(%s)'%e.title)
                    urls.append((section, e.title, urlfeed, desc))
                    urladded.add(urlfeed)
            else:
                self.log.warn('fetch rss failed(%d):%s'%(result.status_code,url))
        
        return urls
        
    def Items(self, opts=None):
        """
        生成器，返回一个元组
        对于HTML：section,url,title,content,brief
        对于图片，mime,url,filename,content,brief
        """
        urls = self.ParseFeedUrls()
        readability = self.readability if self.fulltext_by_readability else self.readability_by_soup
        prevsection = ''
        decoder = AutoDecoder(False)
        for section, ftitle, url, desc in urls:
            if not desc: #非全文RSS
                if section != prevsection or prevsection == '':
                    decoder.encoding = '' #每个小节都重新探测编码
                    prevsection = section
                
                article = self.fetcharticle(url, decoder)
                if not article:
                    continue
            else:
                article = self.FragToXhtml(desc, ftitle)
            
            #如果是图片，title则是mime
            for title, imgurl, imgfn, content, brief in readability(article,url,opts):
                if title.startswith(r'image/'): #图片
                    yield (title, imgurl, imgfn, content, brief)
                else:
                    if not title: title = ftitle
                    content =  self.postprocess(content)
                    yield (section, url, title, content, brief)
    
    def fetcharticle(self, url, decoder):
        #使用同步方式获取一篇文章
        if self.fulltext_by_instapaper and not self.fulltext_by_readability:
            url = "http://www.instapaper.com/m?u=%s" % self.url_unescape(url)
        
        opener = URLOpener(self.host, timeout=self.timeout)
        result = opener.open(url)
        status_code, content = result.status_code, result.content
        if status_code != 200 or not content:
            self.log.warn('fetch article failed(%d):%s.' % (status_code,url))
            return None
        
        if self.page_encoding:
            return content.decode(self.page_encoding)
        else:
            return decoder.decode(content,url)
        
    def readability(self, article, url, opts=None):
        #使用readability-lxml处理全文信息
        #因为图片文件占内存，为了节省内存，这个函数也做为生成器
        content = self.preprocess(article)
        
        # 提取正文
        doc = readability.Document(content)
        summary = doc.summary(html_partial=True)
        title = doc.short_title()
        title = self.processtitle(title)
        #if summary.startswith('<body'): #readability解析出错
        #    html = content
        #else:
        html = self.FragToXhtml(summary, title, addtitleinbody=True)
        
        #因为现在只剩文章内容了，使用BeautifulSoup也不会有什么性能问题
        soup = BeautifulSoup(html, "lxml")
        self.soupbeforeimage(soup)
        
        for attr in ['id','class']:
            for tag in soup.find_all(attrs={attr:True}):
                del tag[attr]
        for cmt in soup.find_all(text=lambda text:isinstance(text, Comment)):
            cmt.extract()
        
        if self.keep_image:
            opener = URLOpener(self.host, timeout=self.timeout)
            for img in soup.find_all('img',attrs={'src':True}):
                imgurl = img['src']
                if img.get('height') in ('1','2','3','4','5') \
                    or img.get('width') in ('1','2','3','4','5'):
                    self.log.warn('img size too small,take away it:%s' % imgurl)
                    img.decompose()
                    continue
                if not imgurl.startswith('http'):
                    imgurl = urlparse.urljoin(url, imgurl)
                if self.fetch_img_via_ssl and url.startswith('https://'):
                    imgurl = imgurl.replace('http://', 'https://')
                if self.isfiltered(imgurl):
                    self.log.warn('img filtered:%s' % imgurl)
                    img.decompose()
                    continue
                imgresult = opener.open(imgurl)
                imgcontent = self.process_image(imgresult.content,opts) if imgresult.status_code==200 else None
                if imgcontent:
                    imgtype = imghdr.what(None, imgcontent)
                    if imgtype:
                        imgmime = r"image/" + imgtype
                        fnimg = "%d.%s" % (random.randint(10000,99999999), 'jpg' if imgtype=='jpeg' else imgtype)
                        img['src'] = fnimg
                        yield (imgmime, imgurl, fnimg, imgcontent, None)
                    else:
                        img.decompose()
                else:
                    self.log.warn('fetch img failed(err:%d):%s' % (imgresult.status_code,imgurl))
                    img.decompose()
        else:
            for img in soup.find_all('img'):
                img.decompose()
        
        self.soupprocessex(soup)
        content = unicode(soup)
        
        #提取文章内容的前面一部分做为摘要
        brief = u''
        if GENERATE_TOC_DESC:
            body = soup.find('body')
            for h1 in body.find_all('h1'): # 去掉H1，避免和标题重复
                h1.decompose()
            for s in body.stripped_strings:
                brief += unicode(s) + u' '
                if len(brief) >= TOC_DESC_WORD_LIMIT:
                    brief = brief[:TOC_DESC_WORD_LIMIT]
                    break
        soup = None
        
        yield (title, None, None, content, brief)
        
    def readability_by_soup(self, article, url, opts=None):
        #因为图片文件占内存，为了节省内存，这个函数也做为生成器
        content = self.preprocess(article)
        soup = BeautifulSoup(content, "lxml")
        
        try:
            title = soup.html.head.title.string
        except AttributeError:
            self.log.warn('object soup invalid!(%s)'%url)
            return
            
        title = self.processtitle(title)
        soup.html.head.title.string = title
        
        if self.keep_only_tags:
            body = soup.new_tag('body')
            try:
                if isinstance(self.keep_only_tags, dict):
                    self.keep_only_tags = [self.keep_only_tags]
                for spec in self.keep_only_tags:
                    for tag in soup.find('body').find_all(**spec):
                        body.insert(len(body.contents), tag)
                soup.find('body').replace_with(body)
            except AttributeError: # soup has no body element
                pass
        
        def remove_beyond(tag, next): # 内联函数
            while tag is not None and getattr(tag, 'name', None) != 'body':
                after = getattr(tag, next)
                while after is not None:
                    ns = getattr(tag, next)
                    after.decompose()
                    after = ns
                tag = tag.parent
        
        if self.remove_tags_after:
            rt = [self.remove_tags_after] if isinstance(self.remove_tags_after, dict) else self.remove_tags_after
            for spec in rt:
                tag = soup.find(**spec)
                remove_beyond(tag, 'next_sibling')
        
        if self.remove_tags_before:
            tag = soup.find(**self.remove_tags_before)
            remove_beyond(tag, 'previous_sibling')
        
        remove_tags = self.insta_remove_tags + self.remove_tags
        remove_ids = self.insta_remove_ids + self.remove_ids
        remove_classes = self.insta_remove_classes + self.remove_classes
        remove_attrs = self.insta_remove_attrs + self.remove_attrs
        
        for tag in soup.find_all(remove_tags):
            tag.decompose()
        for id in remove_ids:
            for tag in soup.find_all(attrs={"id":id}):
                tag.decompose()
        for cls in remove_classes:
            for tag in soup.find_all(attrs={"class":cls}):
                tag.decompose()
        for attr in remove_attrs:
            for tag in soup.find_all(attrs={attr:True}):
                del tag[attr]
        for tag in soup.find_all(attrs={"type":"text/css"}):
            tag.decompose()
        for cmt in soup.find_all(text=lambda text:isinstance(text, Comment)):
            cmt.extract()
        
        if self.keep_image:
            opener = URLOpener(self.host, timeout=self.timeout)
            self.soupbeforeimage(soup)
            for img in soup.find_all('img',attrs={'src':True}):
                imgurl = img['src']
                if img.get('height') in ('1','2','3','4','5') \
                    or img.get('width') in ('1','2','3','4','5'):
                    self.log.warn('img size too small,take away it:%s' % imgurl)
                    img.decompose()
                    continue
                if not imgurl.startswith('http'):
                    imgurl = urlparse.urljoin(url, imgurl)
                if self.fetch_img_via_ssl and url.startswith('https://'):
                    imgurl = imgurl.replace('http://', 'https://')
                if self.isfiltered(imgurl):
                    self.log.warn('img filtered:%s' % imgurl)
                    img.decompose()
                    continue
                imgresult = opener.open(imgurl)
                imgcontent = self.process_image(imgresult.content,opts) if imgresult.status_code==200 else None
                if imgcontent:
                    imgtype = imghdr.what(None, imgcontent)
                    if imgtype:
                        imgmime = r"image/" + imgtype
                        fnimg = "%d.%s" % (random.randint(10000,99999999), 'jpg' if imgtype=='jpeg' else imgtype)
                        img['src'] = fnimg
                        yield (imgmime, imgurl, fnimg, imgcontent, None)
                    else:
                        img.decompose()
                else:
                    self.log.warn('fetch img failed(err:%d):%s' % (imgresult.status_code,imgurl))
                    img.decompose()
        else:
            for img in soup.find_all('img'):
                img.decompose()
        
        if not soup.find('h1'):
            h1 = soup.new_tag('h1')
            h1.string = title
            soup.find('body').insert(0,h1)
        
        self.soupprocessex(soup)
        content = unicode(soup)
        
        #提取文章内容的前面一部分做为摘要
        brief = u''
        if GENERATE_TOC_DESC:
            body = soup.find('body')
            for h1 in body.find_all('h1'): # 去掉H1，避免和标题重复
                h1.decompose()
            for s in body.stripped_strings:
                brief += unicode(s) + u' '
                if len(brief) >= TOC_DESC_WORD_LIMIT:
                    brief = brief[:TOC_DESC_WORD_LIMIT]
                    break
        soup = None
        
        yield (title, None, None, content, brief)        
    
    def process_image(self, data, opts):
        try:
            if not opts or not opts.process_images or not opts.process_images_immediately:
                return data
            elif opts.mobi_keep_original_images:
                return mobify_image(data)
            else:
                return rescale_image(data, png2jpg=opts.image_png_to_jpg,
                                graying=opts.graying_image,
                                reduceto=opts.reduce_image_to)
        except Exception:
            return None

class WebpageBook(BaseFeedBook):
    fulltext_by_readability = False
    # 直接在网页中获取信息
    def Items(self, opts=None):
        """
        生成器，返回一个元组
        对于HTML：section,url,title,content,brief
        对于图片，mime,url,filename,content,brief
        """
        cnt4debug = 0
        decoder = AutoDecoder(False)
        timeout = self.timeout
        for section, url in self.feeds:
            cnt4debug += 1
            if IsRunInLocal and cnt4debug > 1:
                break
            
            opener = URLOpener(self.host, timeout=timeout)
            result = opener.open(url)
            status_code, content = result.status_code, result.content
            if status_code != 200 or not content:
                self.log.warn('fetch article failed(%d):%s.' % (status_code,url))
                continue
            
            if self.page_encoding:
                content = content.decode(self.page_encoding)
            else:
                content = decoder.decode(content,url)
            
            content =  self.preprocess(content)
            soup = BeautifulSoup(content, "lxml")
            
            try:
                title = soup.html.head.title.string
            except AttributeError:
                self.log.warn('object soup invalid!(%s)'%url)
                continue
            
            title = self.processtitle(title)
            
            if self.keep_only_tags:
                body = soup.new_tag('body')
                try:
                    if isinstance(self.keep_only_tags, dict):
                        self.keep_only_tags = [self.keep_only_tags]
                    for spec in self.keep_only_tags:
                        for tag in soup.find('body').find_all(**spec):
                            body.insert(len(body.contents), tag)
                    soup.find('body').replace_with(body)
                except AttributeError: # soup has no body element
                    pass
            
            def remove_beyond(tag, next):
                while tag is not None and getattr(tag, 'name', None) != 'body':
                    after = getattr(tag, next)
                    while after is not None:
                        ns = getattr(tag, next)
                        after.decompose()
                        after = ns
                    tag = tag.parent
            
            if self.remove_tags_after:
                rt = [self.remove_tags_after] if isinstance(self.remove_tags_after, dict) else self.remove_tags_after
                for spec in rt:
                    tag = soup.find(**spec)
                    remove_beyond(tag, 'next_sibling')
            
            if self.remove_tags_before:
                tag = soup.find(**self.remove_tags_before)
                remove_beyond(tag, 'previous_sibling')
            
            remove_tags = self.insta_remove_tags + self.remove_tags
            remove_ids = self.insta_remove_ids + self.remove_ids
            remove_classes = self.insta_remove_classes + self.remove_classes
            remove_attrs = self.insta_remove_attrs + self.remove_attrs
            for tag in soup.find_all(remove_tags):
                tag.decompose()
            for id in remove_ids:
                for tag in soup.find_all(attrs={"id":id}):
                    tag.decompose()
            for cls in remove_classes:
                for tag in soup.find_all(attrs={"class":cls}):
                    tag.decompose()
            for attr in remove_attrs:
                for tag in soup.find_all(attrs={attr:True}):
                    del tag[attr]
            for tag in soup.find_all(attrs={"type":"text/css"}):
                tag.decompose()
            for cmt in soup.find_all(text=lambda text:isinstance(text, Comment)):
                cmt.extract()
            
            if self.keep_image:
                self.soupbeforeimage(soup)
                for img in soup.find_all('img',attrs={'src':True}):
                    imgurl = img['src']
                    if img.get('height') in ('1','2','3','4','5') \
                        or img.get('width') in ('1','2','3','4','5'):
                        self.log.warn('img size too small,take away it:%s' % imgurl)
                        img.decompose()
                        continue
                    if not imgurl.startswith('http'):
                        imgurl = urlparse.urljoin(url, imgurl)
                    if self.fetch_img_via_ssl and url.startswith('https://'):
                        imgurl = imgurl.replace('http://', 'https://')
                    if self.isfiltered(imgurl):
                        self.log.warn('img filtered:%s' % imgurl)
                        img.decompose()
                        continue
                    imgresult = opener.open(imgurl)
                    imgcontent = self.process_image(imgresult.content,opts) if imgresult.status_code==200 else None
                    if imgcontent:
                        imgtype = imghdr.what(None, imgcontent)
                        if imgtype:
                            imgmime = r"image/" + imgtype
                            fnimg = "%d.%s" % (random.randint(10000,99999999), 'jpg' if imgtype=='jpeg' else imgtype)
                            img['src'] = fnimg
                            yield (imgmime, imgurl, fnimg, imgcontent, None)
                        else:
                            img.decompose()
                    else:
                        self.log.warn('fetch img failed(err:%d):%s' % (imgresult.status_code,imgurl))
                        img.decompose()                
            else:
                for img in soup.find_all('img'):
                    img.decompose()
            
            self.soupprocessex(soup)
            content = unicode(soup)
            
            #提取文章内容的前面一部分做为摘要
            brief = u''
            if GENERATE_TOC_DESC:
                body = soup.find('body')
                for h1 in body.find_all('h1'): # 去掉H1，避免和标题重复
                    h1.decompose()
                for s in body.stripped_strings:
                    brief += unicode(s) + u' '
                    if len(brief) >= TOC_DESC_WORD_LIMIT:
                        brief = brief[:TOC_DESC_WORD_LIMIT]
                        break
            soup = None
            
            content =  self.postprocess(content)
            yield (section, url, title, content, brief)


