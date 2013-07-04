#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os, re, urllib, urlparse, random, imghdr, logging
from urllib2 import *
from google.appengine.api import urlfetch

from lib.BeautifulSoup import BeautifulSoup, Tag, Comment
from lib import feedparser
from lib.readability.readability import Document
from urlopener import URLOpener
import chardet

class AutoDecoder:
    def __init__(self):
        self.encoding = None
    def decode(self, content):
        result = content
        if self.encoding: # 先使用上次的编码打开文件尝试
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
        else:  # 暂时没有之前的编码信息
            self.encoding = chardet.detect(content)['encoding']
            try:
                result = content.decode(self.encoding)
            except UnicodeDecodeError: # 出错，则不转换，直接返回
                result = content
        return result
        
class BaseFeedBook:
    """ base class of Book """
    title                 = ''
    __author__            = ''
    description           = ''
    publisher             = ''
    category              = ''
    host                  = None # 有些网页的图像下载需要请求头里面包含Referer,使用此参数配置
    max_articles_per_feed = 40
    language = 'und' #最终书籍的语言定义，比如zh-cn,en等
    
    #下面这两个编码建议设置，如果留空，则使用自动探测解码，稍耗费CPU
    feed_encoding = '' # RSS编码，一般为XML格式，直接打开源码看头部就有编码了
    page_encoding = '' # 页面编码，获取全文信息时的网页编码
    
    # 题图文件名，格式：gif(600*60)，所有图片文件存放在images/下面，文件名不需要images/前缀
    # 如果不提供此图片，软件使用PIL生成一个，但是因为GAE不能使用ImageFont组件
    # 所以字体很小，而且不支持中文标题，使用中文会出错
    mastheadfile = ''
    
    coverfile = '' #封面图片文件
    
    keep_image = True #生成的MOBI是否需要图片
    
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
    insta_remove_attrs = ['title','width','height','onclick','onload']
    insta_remove_classes = []
    insta_remove_ids = ['controlbar_container','left_buttons','right_buttons','title_label',]
    
    # 子类定制的HTML标签清理内容
    remove_tags = [] # 完全清理此标签
    remove_ids = [] # 清除标签的id属性为列表中内容的标签
    remove_classes = [] # 清除标签的class属性为列表中内容的标签
    remove_attrs = [] # 清除所有标签的特定属性，不清除标签内容
    
    #每个子类必须重新定义这个属性，为RSS/网页链接列表
    #每个链接格式为元组：(分节标题, URL)
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
    @classmethod
    def urljoin(self, base, url):
        #urlparse.urljoin()处理有..的链接有点问题，此函数修正此问题。
        join = urlparse.urljoin(base,url)
        url = urlparse.urlsplit(join)
        path = os.path.normpath(url.path)
        return urlparse.urlunsplit((url.scheme,url.netloc,path,url.query,url.fragment))

    def FragToXhtml(self, content, title, htmlencoding='utf-8', addtitleinbody=False):
        #将HTML片段嵌入完整的XHTML框架中
        frame = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
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
            t = "<h1>%s</h1>" % title if addtitleinbody else ""
            htmlencoding = htmlencoding if htmlencoding else 'utf-8'
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
        """ return list like [(section,title,url),..] """
        urls = []
        opener = URLOpener(self.host)
        decoder = AutoDecoder()
        for section, url in self.feeds:
            result = opener.open(url)
            if result.status_code == 200:
                if self.feed_encoding:
                    feed = feedparser.parse(result.content.decode(self.feed_encoding))
                else:
                    feed = feedparser.parse(decoder.decode(result.content))
                for e in feed['entries'][:self.max_articles_per_feed]:
                    urls.append((section,e.title,e.link))
        return urls
        
    def Items(self):
        """
        生成器，返回一个元组
        对于HTML：section,url,title,content
        对于图片，mime,url,filename,content
        """
        urls = self.ParseFeedUrls()
        cnt4debug = 0
        decoder = AutoDecoder()
        for section, ftitle, url in urls:
            cnt4debug += 1
            if IsRunInLocal and cnt4debug > 1:
                break
            
            fulltext = self.readability if self.fulltext_by_readability else self.fulltext
            
            #如果是图片，title则是mime
            for title, imgurl, imgfn, content in fulltext(url, decoder):
                if title.startswith(r'image/'): #图片
                    yield (title, imgurl, imgfn, content)
                else:
                    if not title:
                        title = ftitle
                    content =  self.postprocess(content)
                    assert content
                    yield (section, url, title, content)
            
    def readability(self, url, decoder):
        #使用readability-lxml处理全文信息
        #因为图片文件占内存，为了节省内存，这个函数也做为生成器
        opener = URLOpener(self.host)
        result = opener.open(url)
        status_code, content = result.status_code, result.content
        if status_code != 200 or not content:
            logging.error('err(%d) to fetch %s.' % (status_code,url))
            return
            
        if self.page_encoding:
            content = content.decode(self.page_encoding)
        else:
            content = decoder.decode(content)
        
        content = self.preprocess(content)
        
        # 提取正文
        doc = Document(content)
        summary = doc.summary(html_partial=True)
        title = doc.short_title()
        title = self.processtitle(title)
        html = self.FragToXhtml(summary, title, addtitleinbody=True)
        
        #因为现在只剩文章内容了，使用BeautifulSoup也不会有什么性能问题
        if self.keep_image:
            soup = BeautifulSoup(html)
            
            for cmt in soup.findAll(text=lambda text:isinstance(text, Comment)):
                cmt.extract
            
            self.soupbeforeimage(soup)
            
            for img in soup.findAll('img'):
                imgurl = img['src']
                if not imgurl.startswith('http') and not imgurl.startswith('www'):
                    imgurl = self.urljoin(url, imgurl)
                imgresult = opener.open(imgurl)
                imgcontent = imgresult.content if imgresult.status_code == 200 else None
                if imgcontent:
                    imgtype = imghdr.what(None, imgcontent)
                    if imgtype:
                        imgmime = r"image/" + imgtype
                        if imgtype == 'jpeg':
                            fnimg = "%d.jpg" % random.randint(10000,99999999)
                        else:
                            fnimg = "%d.%s" % (random.randint(10000,99999999), imgtype)
                        img['src'] = fnimg
                        yield (imgmime, imgurl, fnimg, imgcontent)
                        
        yield (title, None, None, html)
        
    def fulltext(self, url, decoder):
        #因为图片文件占内存，为了节省内存，这个函数也做为生成器
        if self.fulltext_by_instapaper:
            url = "http://www.instapaper.com/m?u=%s" % self.url_unescape(url)
        opener = URLOpener(self.host)
        result = opener.open(url)
        status_code, content = result.status_code, result.content
        if status_code != 200 or not content:
            logging.error('err(%d) to fetch %s.' % (status_code,url))
            return
        
        if self.page_encoding:
            content = content.decode(self.page_encoding)
        else:
            content = decoder.decode(content)
        
        content = self.preprocess(content)
        soup = BeautifulSoup(content)
        
        try:
            title = soup.html.head.title.string
        except AttributeError:
            logging.error('object soup invalid!(%s)'%url)
            return
            
        title = self.processtitle(title)
        soup.html.head.title.string = title
        
        if self.keep_only_tags:
            body = Tag(soup, 'body')
            try:
                if isinstance(self.keep_only_tags, dict):
                    self.keep_only_tags = [self.keep_only_tags]
                for spec in self.keep_only_tags:
                    for tag in soup.find('body').findAll(**spec):
                        body.insert(len(body.contents), tag)
                soup.find('body').replaceWith(body)
            except AttributeError: # soup has no body element
                pass
        
        def remove_beyond(tag, next): # 内联函数
            while tag is not None and getattr(tag, 'name', None) != 'body':
                after = getattr(tag, next)
                while after is not None:
                    ns = getattr(tag, next)
                    after.extract()
                    after = ns
                tag = tag.parent
        
        if self.remove_tags_after:
            rt = [self.remove_tags_after] if isinstance(self.remove_tags_after, dict) else self.remove_tags_after
            for spec in rt:
                tag = soup.find(**spec)
                remove_beyond(tag, 'nextSibling')
        
        if self.remove_tags_before:
            tag = soup.find(**self.remove_tags_before)
            remove_beyond(tag, 'previousSibling')
        
        remove_tags = self.insta_remove_tags + self.remove_tags
        remove_ids = self.insta_remove_ids + self.remove_ids
        remove_classes = self.insta_remove_classes + self.remove_classes
        remove_attrs = self.insta_remove_attrs + self.remove_attrs
        
        for tag in soup.findAll(remove_tags):
            tag.extract()
        for id in remove_ids:
            for tag in soup.findAll(attrs={"id":id}):
                tag.extract()
        for cls in remove_classes:
            for tag in soup.findAll(attrs={"class":cls}):
                tag.extract()
        for attr in remove_attrs:
            for tag in soup.findAll(attrs={attr:True}):
                del tag[attr]
        for tag in soup.findAll(attrs={"type":"text/css"}):
            tag.extract()
        for cmt in soup.findAll(text=lambda text:isinstance(text, Comment)):
            cmt.extract
        
        if self.keep_image:
            self.soupbeforeimage(soup)
            for img in soup.findAll('img'):
                imgurl = img['src']
                if not imgurl.startswith('http') and not imgurl.startswith('www'):
                    imgurl = self.urljoin(url, imgurl)
                imgresult = opener.open(imgurl)
                imgcontent = imgresult.content if imgresult.status_code == 200 else None
                if imgcontent:
                    imgtype = imghdr.what(None, imgcontent)
                    if imgtype:
                        imgmime = r"image/" + imgtype
                        if imgtype == 'jpeg':
                            fnimg = "%d.jpg" % random.randint(10000,99999999)
                        else:
                            fnimg = "%d.%s" % (random.randint(10000,99999999), imgtype)
                        img['src'] = fnimg
                        yield (imgmime, imgurl, fnimg, imgcontent)
        else:
            for img in soup.findAll('img'):
                img.extract()
        
        self.soupprocessex(soup)
        content = soup.renderContents('utf-8').decode('utf-8')
        soup = None
        
        yield (title, None, None, content)
        
class FulltextFeedBook(BaseFeedBook):
    # 在Feed中就有全文的RSS订阅
    def Items(self):
        itemsprocessed = []
        cnt4debug = 0
        opener = URLOpener(self.host)
        decoder = AutoDecoder()
        for section, url in self.feeds:
            content = None
            cnt4debug += 1
            if IsRunInLocal and cnt4debug > 1:
                break
            
            result = opener.open(url)
            status_code, content = result.status_code, result.content
            if status_code != 200 and content:
                logging.error('err(%d) to fetch %s.' % (status_code,url))
                continue
            
            if self.feed_encoding:
                content = content.decode(self.feed_encoding)
            else:
                content = decoder.decode(content)
            
            content = self.preprocess(content)
            
            feed = feedparser.parse(content)
            for e in feed['entries']:
                # 全文RSS中如果有广告或其他不需要的内容，可以在postprocess去掉
                desc = self.postprocess(e.description)
                desc = self.FragToXhtml(desc, e.title, self.feed_encoding)
                
                if self.keep_image:
                    soup = BeautifulSoup(content)
                    self.soupbeforeimage(soup)
                    for img in soup.findAll('img'):
                        imgurl = img['src']
                        if not imgurl.startswith('http') and not imgurl.startswith('www'):
                            imgurl = self.urljoin(url, imgurl)
                        imgresult = opener.open(imgurl)
                        imgcontent = imgresult.content if imgresult.status_code == 200 else None
                        if imgcontent:
                            imgtype = imghdr.what(None, imgcontent)
                            if imgtype:
                                imgmime = r"image/" + imgtype
                                if imgtype == 'jpeg':
                                    fnimg = "%d.jpg" % random.randint(10000,99999999)
                                else:
                                    fnimg = "%d.%s" % (random.randint(10000,99999999), imgtype)
                                img['src'] = fnimg
                                yield (imgmime, imgurl, fnimg, imgcontent)
                    self.soupprocessex(soup)
                    desc = soup.renderContents('utf-8').decode('utf-8')
                    soup = None
                
                if e.title not in itemsprocessed and desc:
                    itemsprocessed.append(e.title)
                    yield (section, e.link, e.title, desc)


class WebpageBook(BaseFeedBook):
    fulltext_by_readability = False
    # 直接在网页中获取信息
    def Items(self):
        """
        生成器，返回一个元组
        对于HTML：section,url,title,content
        对于图片，mime,url,filename,content
        """
        cnt4debug = 0
        decoder = AutoDecoder()
        for section, url in self.feeds:
            cnt4debug += 1
            if IsRunInLocal and cnt4debug > 1:
                break
            
            opener = URLOpener(self.host)
            result = opener.open(url)
            status_code, content = result.status_code, result.content
            if status_code != 200 or not content:
                logging.error('err(%d) to fetch %s.' % (status_code,url))
                continue
            
            if self.page_encoding:
                content = content.decode(self.page_encoding)
            else:
                content = decoder.decode(content)
            
            content =  self.preprocess(content)
            soup = BeautifulSoup(content)
            
            try:
                title = soup.html.head.title.string
            except AttributeError:
                logging.error('object soup invalid!(%s)'%url)
                continue
            
            title = self.processtitle(title)
            
            if self.keep_only_tags:
                body = Tag(soup, 'body')
                try:
                    if isinstance(self.keep_only_tags, dict):
                        self.keep_only_tags = [self.keep_only_tags]
                    for spec in self.keep_only_tags:
                        for tag in soup.find('body').findAll(**spec):
                            body.insert(len(body.contents), tag)
                    soup.find('body').replaceWith(body)
                except AttributeError: # soup has no body element
                    pass
            
            def remove_beyond(tag, next): # 鍐呭祵鍑芥暟
                while tag is not None and getattr(tag, 'name', None) != 'body':
                    after = getattr(tag, next)
                    while after is not None:
                        ns = getattr(tag, next)
                        after.extract()
                        after = ns
                    tag = tag.parent
            
            if self.remove_tags_after:
                rt = [self.remove_tags_after] if isinstance(self.remove_tags_after, dict) else self.remove_tags_after
                for spec in rt:
                    tag = soup.find(**spec)
                    remove_beyond(tag, 'nextSibling')
            
            if self.remove_tags_before:
                tag = soup.find(**self.remove_tags_before)
                remove_beyond(tag, 'previousSibling')
            
            remove_tags = self.insta_remove_tags + self.remove_tags
            remove_ids = self.insta_remove_ids + self.remove_ids
            remove_classes = self.insta_remove_classes + self.remove_classes
            remove_attrs = self.insta_remove_attrs + self.remove_attrs
            for tag in soup.findAll(remove_tags):
                tag.extract()
            for id in remove_ids:
                for tag in soup.findAll(attrs={"id":id}):
                    tag.extract()
            for cls in remove_classes:
                for tag in soup.findAll(attrs={"class":cls}):
                    tag.extract()
            for attr in remove_attrs:
                for tag in soup.findAll(attrs={attr:True}):
                    del tag[attr]
            for tag in soup.findAll(attrs={"type":"text/css"}):
                tag.extract()
            for cmt in soup.findAll(text=lambda text:isinstance(text, Comment)):
                cmt.extract
            
            if self.keep_image:
                self.soupbeforeimage(soup)
                for img in soup.findAll('img'):
                    imgurl = img['src']
                    if not imgurl.startswith('http') and not imgurl.startswith('www'):
                        imgurl = self.urljoin(url, imgurl)
                    imgresult = opener.open(imgurl)
                    imgcontent = imgresult.content if imgresult.status_code == 200 else None
                    if imgcontent:
                        imgtype = imghdr.what(None, imgcontent)
                        if imgtype:
                            imgmime = r"image/" + imgtype
                            if imgtype == 'jpeg':
                                fnimg = "%d.jpg" % random.randint(10000,99999999)
                            else:
                                fnimg = "%d.%s" % (random.randint(10000,99999999), imgtype)
                            img['src'] = fnimg
                            yield (imgmime, imgurl, fnimg, imgcontent)
            else:
                for img in soup.findAll('img'):
                    img.extract()
            
            self.soupprocessex(soup)
            content = soup.renderContents('utf-8').decode('utf-8')
            soup = None
            content =  self.postprocess(content)
            yield (section, url, title, content)
        