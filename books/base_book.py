#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
KindleEar电子书基类，每本投递到kindle的书籍抽象为这里的一个类。
可以继承BaseFeedBook类而实现自己的定制书籍。
cdhigh <https://github.com/cdhigh>
"""
import os, re, imghdr, datetime, hashlib, io
from collections import namedtuple
from PIL import Image
from bs4 import BeautifulSoup, Comment
import feedparser
from urllib.parse import urljoin, urlparse, urlunparse, urlencode, parse_qs, unquote_plus, quote_plus
from lib import readability #修改了其htmls.py|shorten_title()
from lib.urlopener import UrlOpener
from apps.db_models import LastDelivered
from lib.image_tools import split_image_by_height, compress_image
from config import *

#通过一个图像文件生成一个HTML文件的模板
imageHtmlTemplate = """<html><head><meta http-equiv="Content-Type" content="text/html;charset=utf-8"><title>{title}</title></head><body><img src="{imgFilename}"/></body></html>"""

#将HTML片段嵌入完整的XHTML框架中的模板
xHtmlFrameTemplate = u"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head><meta http-equiv="Content-Type" content="text/html; charset={encoding}">
<title>{title}</title>
<style type="text/css">p{text-indent:2em;} h1{font-weight:bold;}</style></head>
<body>{bodyTitle}<p>{content}</p></body></html>"""

#分析RSS的XML返回的每一项的结构
ItemRssTuple = namedtuple("ItemRssTuple", "section title url desc")

#Items()返回的数据结构
#soup: BeautifulSoup实例
#thumbnailUrl: 文章中第一个图片文件的url
ItemHtmlTuple = namedtuple("ItemHtmlTuple", "section url title soup brief thumbnailUrl")

#每个图片
#图片的isThumbnail仅当其为article的第一个img为True
ItemImageTuple = namedtuple("ItemImageTuple", "mime url fileName content isThumbnail")

#每个CSS，其mime固定为 "text/css"
ItemCssTuple = namedtuple("ItemCssTuple", "url fileName content")

# base class of Book
class BaseFeedBook:
    title                 = ''
    __author__            = ''
    description           = ''
    max_articles_per_feed = 30
    oldest_article        = 7    #下载多长时间之内的文章，小于等于365则单位为天，大于365则单位为秒，0为不限制
    host                  = None # 有些网页的图像下载需要请求头里面包含Referer,使用此参数配置
    network_timeout       = None  # None则使用默认
    fetch_img_via_ssl     = False # 当网页为https时，其图片是否也转换成https
    language = 'und' #最终书籍的语言定义，比如zh-cn,en等

    extra_header = {}# 设置请求头包含的额外数据
    # 例如设置 Accept-Language：extra_header['Accept-Language'] = 'zh-CN,zh;q=0.8,en;q=0.6,ja;q=0.4'

    # 题图文件名，格式：gif(600*60)，所有图片文件存放在images/下面，文件名不需要images/前缀
    # 如果不提供此图片，软件使用PIL生成一个，但是因为GAE不能使用ImageFont组件
    # 所以字体很小，而且不支持中文标题，使用中文会出错
    masthead_file = DEFAULT_MASTHEAD
    
    #封面图片文件，如果值为一个字符串，则对应到images目录下的文件
    #如果需要在线获取封面或自己定制封面（比如加日期之类的），则可以自己写一个回调函数，输入一个参数（类实例），返回图片的二进制数据（支持gif/jpg/png格式）
    #回调函数要求为独立的函数，不能为类方法或实例方法。
    #如果回调函数返回的不是图片或为None，则还是直接使用DEFAULT_COVER
    cover_file = DEFAULT_COVER
    
    keep_image = True #生成的MOBI是否需要图片

    #是否按星期投递，留空则每天投递，否则是一个星期字符串列表
    #一旦设置此属性，则网页上设置的“星期推送”对此书无效
    #'Monday','Tuesday',...,'Sunday'，大小写敏感
    #比如设置为['Friday'] 或 ['Monday', 'Friday', 'Sunday']
    deliver_days = []

    #自定义书籍推送时间，一旦设置了此时间，则网页上设置的时间对此书无效
    #用此属性还可以实现一天推送多次
    #格式为整形列表，比如每天8点/18点推送，则设置为[8,18]
    #时区则自动使用订阅者的时区
    deliver_times = []

    #设置是否使用readability-lxml(Yuri Baburov)自动处理网页
    #正常来说，大部分的网页，readability处理完后的效果都不错
    #不过如果你需要更精细的控制排版和内容，可以设置为False
    #然后使用下面的一些选项和回调函数自己处理
    #一旦设置此选项为True，则没有必要关注其他的内容控制选项
    fulltext_by_readability = True

    #如果设置为True则需要提供用户名和密码，并且还要提供登陆URL
    #如果登陆界面比较复杂，有可能你需要重新实现login函数
    needs_subscription = False
    login_url = ''
    account = ''
    password = ''
    #None为自动猜测，字符串则是表单id或class，整数则为html中form序号（从0开始）
    login_form = None
    
    # 背景知识：下面所说的标签为HTML标签，比如'body','h1','div','p'等都是标签

    # 仅抽取网页中特定的标签段，在一个复杂的网页中抽取正文，这个工具效率最高
    # 内容为字典列表
    # 比如：keep_only_tags = [dict(name='div', attrs={'id':'article'}),]
    # 这个优先级最高，先处理了这个标签再处理其他标签。
    keep_only_tags = []

    # 顾名思义，删除特定标签前/后的所有内容，格式和keep_only_tags相同
    # 内容为字典列表
    remove_tags_after = []
    remove_tags_before = []

    # 内置的几个必须删除的标签，不建议子类修改
    # 内容为字符串列表
    insta_remove_tags = ['script', 'object', 'video', 'embed', 'noscript', 'style', 'link']
    insta_remove_attrs = ['width', 'height', 'onclick', 'onload', 'style']
    insta_remove_classes = []
    insta_remove_ids = ['controlbar_container',]

    #---------------add by rexdf-------------
    #下面的积极关键词,有些内容会被readability过滤掉，比如html5的figure，可以通过增加权重保留
    #这个是针对部分html5网站优化的，子类需要修改可以不用继承，因为子类往往针对特定某一网站，可以专门定制
    positive_classes = ['image-block', 'image-block-caption', 'image-block-ins']

    #图像最小大小，有些网站会在正文插入一个1*1像素的图像，大约是带有的水印信息，这样的图片视觉无意义，而且干扰thumbnail
    img_min_size = 1024
    #---------------end----------------------

    # 子类定制的HTML标签清理内容
    remove_tags = [] # 完全清理此标签，为字符串列表
    remove_ids = [] # 清除标签的id属性为列表中内容的标签，为字符串列表
    remove_classes = [] # 清除标签的class属性为列表中内容的标签，为字符串列表
    remove_attrs = [] # 清除所有标签的特定属性，不清除标签内容，为字符串列表

    # 添加到每篇文章的CSS，可以更完美的控制文章呈现
    # 仅需要CSS内容，不要包括<style type="text/css"></style>标签
    # 可以使用多行字符串
    extra_css = ''

    # 一个字符串列表，为正则表达式，在此列表中的url不会被下载
    # 可用于一些注定无法下载的图片链接，以便节省时间
    url_filters = []

    #每个子类必须重新定义这个属性，为RSS/网页链接列表
    #每个链接格式为元组：(分节标题, URL, isfulltext)
    #最后一项isfulltext是可选的，如果存在，取值为True/False
    #('8小时最热', 'http://www.qiushibaike.com'),
    feeds = []

    #几个钩子函数，基类在适当的时候会调用，
    #子类可以使用钩子函数进一步定制

    #普通Feed在网页元素拆分分析前调用，全文Feed在FEED拆分前调用
    #网络上大部分的RSS都是普通Feed，只有概要信息
    #content为网页字符串，记得处理后返回字符串
    def PreProcess(self, content):
        return content

    #网页title处理，比如去掉网站标识，一长串的SEQ字符串等
    #返回处理后的title
    def ProcessTitle(self, title):
        return re.sub(r'(\n)+', ' ', title)

    #如果要处理图像，则在处理图片前调用此函数，可以处理和修改图片URL等
    def ProcessBeforeImage(self, soup):
        return None

    #BeautifulSoup拆分网页分析处理后再提供给子类进一步处理
    #soup为BeautifulSoup实例引用，直接在soup上处理即可，不需要返回值
    def PostProcess(self, soup):
        return None

    #------------------------------------------------------------
    # 下面的内容为类实现细节
    #------------------------------------------------------------
    #log: logging实例
    #imgIndex: 初始图像文件名序号
    #opts: OptionValues实例，定义在makeoeb.py
    #user: 账号数据库行实例
    def __init__(self, log=None, imgIndex=0, opts=None, user=None):
        global default_log
        self.log = log if log else default_log
        self.compiled_urlfilters = []
        self.img_index = imgIndex
        self.opts = opts
        self.user = user
        self.last_delivered_volume = '' #如果需要在推送书籍的标题中提供当前期号之类的信息，可以使用此属性
        
    @property
    def timeout(self):
        return self.network_timeout if self.network_timeout else 30
        
    @property
    def AutoImageIndex(self):
        self.img_index += 1
        return self.img_index
    
    #判断URL是否在URL过滤器(黑名单)内
    def IsFiltered(self, url):
        if not self.url_filters:
            return False
        elif not self.compiled_urlfilters:
            self.compiled_urlfilters = [re.compile(flt, re.I) for flt in self.url_filters]

        for flt in self.compiled_urlfilters:
            if flt.match(url):
                return True
        return False
        
    #返回当前任务的用户名
    @property
    def UserName(self):
        return self.user.name if self.user else ADMIN_NAME

    # 返回最近推送的章节标题
    @property
    def LastDeliveredVolume(self):
        return self.last_delivered_volume
    
    #将HTML片段嵌入完整的XHTML框架中
    #encoding:网页编码
    #addTitleInBody: 除了HTML的head段，是否在正文body里面也添加Title
    def FragToXhtml(self, content, title, encoding='utf-8', addTitleInBody=False):
        if "<html" in content:
            return content
        else:
            t = "<h1>{}</h1>".format(title) if addTitleInBody else ""
            if not encoding:
                encoding = 'utf-8'
            return xHtmlFrameTemplate.format(encoding=encoding, title=title, bodyTitle=t, content=content)

    #分析RSS的XML文件，返回一个 ItemRssTuple 列表，里面包含了接下来需要抓取的链接或描述
    def ParseFeedUrls(self):
        urls = []
        tNow = datetime.datetime.utcnow()
        urlAdded = set()
        
        for feed in self.feeds:
            section, url = feed[0], feed[1]
            isFullText = feed[2] if len(feed) > 2 else False
            opener = UrlOpener(self.host, timeout=self.timeout, headers=self.extra_header)
            result = opener.open(url)
            if result.status_code == 200:
                #from lib.debug_utils import debug_mail
                #debug_mail(result.text, 'feed.xml')
                feed = feedparser.parse(result.text)
                
                for e in feed['entries'][:self.max_articles_per_feed]:
                    updated = None
                    if hasattr(e, 'updated_parsed') and e.updated_parsed:
                        updated = e.updated_parsed
                    elif hasattr(e, 'published_parsed') and e.published_parsed:
                        updated = e.published_parsed
                    elif hasattr(e, 'created_parsed'):
                        updated = e.created_parsed
                    
                    if self.oldest_article > 0 and updated:
                        updated = datetime.datetime(*(updated[0:6]))
                        delta = tNow - updated
                        if self.oldest_article > 365:
                            threshold = self.oldest_article #以秒为单位
                        else:
                            threshold = 86400*self.oldest_article #以天为单位
                        
                        if (delta.days * 86400) + delta.seconds > threshold:
                            self.log.info("Skip old article({}): {}".format(updated.strftime('%Y-%m-%d %H:%M:%S'), e.link))
                            continue
                    
                    title = e.title if hasattr(e, 'title') else 'Untitled'
                    urlFeed = e.link if hasattr(e, "link") else ""
                    if urlFeed in urlAdded:
                        continue
                    
                    desc = None
                    if isFullText:
                        summary = e.summary if hasattr(e, 'summary') else None
                        desc = e.content[0]['value'] if (hasattr(e, 'content')
                            and e.content[0]['value']) else None

                        #同时存在，因为有的RSS全文内容放在summary，有的放在content
                        #所以认为内容多的为全文
                        if summary and desc:
                            desc = summary if len(summary) > len(desc) else desc
                        elif summary:
                            desc = summary

                        if not desc:
                            if urlFeed:
                                self.log.warn('Fulltext item ({}) has no desc, fetch article from web.'.format(title))
                            else:
                                continue
                    
                    if urlFeed:
                        urlAdded.add(urlFeed)

                    #针对URL里面有unicode字符的处理，否则会出现Bad request
                    #后面参数里面的那一堆“乱码”是要求不处理ASCII的特殊符号，只处理非ASCII字符
                    urlFeed = quote_plus(urlFeed, r'''~`!@#$%^&*()|\\/,.<>;:"'{}[]?=-_+''')
                    urls.append(ItemRssTuple(section, title, urlFeed, desc))
            else:
                self.log.warn('fetch rss failed({}):{}'.format(UrlOpener.CodeMap(result.status_code), url))
                
        return urls

    #生成器，返回电子书中的每一项内容，包括HTML或图像文件，
    #每次返回一个命名元组，可能为 ItemHtmlTuple, ItemImageTuple, ItemCssTuple
    def Items(self):
        useTitleInFeed = self.user.use_title_in_feed if self.user else False
        urls = self.ParseFeedUrls() #返回 [ItemRssTuple,...]
        readability = self.Readability if self.fulltext_by_readability else self.ReadabilityBySoup
        prevSection = None
        opener = UrlOpener(self.host, timeout=self.timeout, headers=self.extra_header)
        for rssItem in urls:
            if not rssItem.desc: #普通RSS，需要到网上抓取
                if rssItem.section != prevSection:
                    prevSection = rssItem.section #每一段都采用不同的session，重新生成一个UrlOpener
                    opener = UrlOpener(self.host, timeout=self.timeout, headers=self.extra_header)
                    if self.needs_subscription:
                        result = self.login(opener)
                        #if result:
                        #    from lib.debug_utils import debug_mail, debug_save_ftp
                        #    debug_mail(result.text, 'login_result.html')
                        #    debug_save_ftp(result.text, 'login_result.html')
                        #else:
                        #    self.log.warn('func login return none!')                        
        
                resp = self.FetchArticle(rssItem.url, opener)
                if not resp:
                    continue
            else: #全文RSS，直接使用XML里面的描述生成一个HTML
                resp = self.FragToXhtml(rssItem.desc, rssItem.title)
            
            yield from readability(resp, rssItem)
                
    #使用readability-lxml处理全文信息
    #因为图片文件占内存，为了节省内存，这个函数也做为生成器
    #resp: 可能为字符串(描述片段生成的HTML)，也可能为 requests.Response 实例
    #rssItem: ItemRssTuple 实例
    #返回可能为：ItemHtmlTuple, ItemImageTuple, ItemCssTuple
    def Readability(self, resp, rssItem):
        url = rssItem.url
        title = ""
        if isinstance(resp, str): #程序生成的HTML，不需要提取正文的步骤
            summary = self.PreProcess(resp)
            if not summary:
                return None
        else: #实时网页内容
            content = self.PreProcess(resp.text)
            if not content:
                return None
            
            #提取正文
            try:
                doc = readability.Document(content, positive_keywords=self.positive_classes)
                summary = doc.summary(html_partial=False)
                title = doc.short_title()
            except:
                #如果提取正文出错，可能是图片（一个图片做为一篇文章，没有使用html包装）
                imgType = imghdr.what(None, resp.content)
                if imgType: #如果是图片，则使用一个简单的html做为容器
                    imgMime = "image/{}".format(imgType)
                    imgFn = "img{}.{}".format(self.ImgIndex, imgType.replace("jpeg", "jpg"))
                    yield ItemImageTuple(imgMime, url, imgFn, resp.content, False)
                    tmpHtml = imageHtmlTemplate.format(title="Picture", imgFilename=imgFn) #HTML容器
                    yield ItemHtmlTuple("", url, "Picture", BeautifulSoup(tmpHtml, "lxml"), "", "")
                else:
                    self.log.warn("Invalid article:{}".format(url))
                return None
            
        soup = BeautifulSoup(summary, "lxml")
        if not title:
            titleTag = soup.find('title')
            title = titleTag.string if titleTag else "Untitled"

        bodyTag = soup.find('body')
        headTag = soup.find('head')

        #如果readability解析失败，则启用备用算法（不够好，但有全天候适应能力）
        if not bodyTag or len(bodyTag.contents) == 0:
            from simpleextract import simple_extract
            summary = simple_extract(content)
            soup = BeautifulSoup(summary, "lxml")
            bodyTag = soup.find('body')
            if not bodyTag: #再次失败
                self.log.warn('Extract article content failed:{}'.format(url))
                return None
                
            headTag = soup.find('head')
            #增加备用算法提示，提取效果不好不要找我，类似免责声明：）
            info = soup.new_tag('p', style='color:#555555;font-size:60%;text-align:right;')
            info.string = 'extracted by alternative algorithm.'
            bodyTag.append(info)
            
            self.log.info('Use alternative algorithm to extract content:{}'.format(url))
            
        if not headTag:
            headTag = soup.new_tag('head')
            soup.html.insert(0, headTag)
        
        title = self.ProcessTitle(title)
        titleTag = headTag.find('title')
        if titleTag:
            titleTag.string = title
        else:
            titleTag = soup.new_tag('title')
            titleTag.string = title
            headTag.append(titleTag)
            
        #根据书籍内置remove_xxx 属性，清理一些元素
        self.removeSoupElements(soup)

        #添加额外的CSS
        if self.AddCustomCss(soup):
            yield ItemCssTuple("custom.css", "custom.css", self.user.css_content)

        #逐个处理文章内的图像链接，生成对应的图像文件
        thumbnailUrl = None
        for imgManifest in self.PrepareImageManifest(soup, url):
            if not thumbnailUrl and imgManifest.isThumbnail:
                thumbnailUrl = imgManifest.url
            yield imgManifest

        #整理文章格式，比如添加内容标题，转换HTML5标签等
        self.NormalizeArticle(soup, title)

        self.PostProcess(soup)

        #插入分享链接，如果有插入qrcode，则返回(imgName, imgContent)
        qrImg = self.AppendShareLinksToArticle(soup, url)
        if qrImg:
            yield ItemImageTuple("image/jpeg", url, qrImg[0], qrImg[1], False)

        if self.user and self.user.use_title_in_feed:
            title = rssItem.title

        #提取文章内容的前面一部分做为摘要
        brief = self.ExtractBrief(soup)
        yield ItemHtmlTuple(rssItem.section, url, title, soup, brief, thumbnailUrl)
        
    #使用BeautifulSoup手动解析网页，提取正文内容
    #因为图片文件占内存，为了节省内存，这个函数也做为生成器
    #resp: 可能为字符串(描述片段生成的HTML)，也可能为 requests.Response 实例
    #rssItem: ItemRssTuple 实例
    #返回可能为：ItemHtmlTuple, ItemImageTuple, ItemCssTuple
    def ReadabilityBySoup(self, resp, rssItem):
        article = resp if isinstance(resp, str) else resp.text
        content = self.PreProcess(article)
        if not content:
            return None

        url = rssItem.url
        soup = BeautifulSoup(content, "lxml")
        headTag = soup.find('head')
        if not headTag:
            self.log.warn("Object soup invalid:{}".format(url))
            return None

        titleTag = soup.find('title')
        if titleTag:
            title = titleTag.string
        else: #创建一个Title
            title = "Untitled"
            titleTag = soup.new_tag('title')
            titleTag.string = title
            head.append(titleTag)
        
        title = self.ProcessTitle(title)
        titleTag.string = title

        #如果仅保留一些Tag，则新建一个body，替换掉原来的body
        bodyTag = self.BuildNewSoupBody(soup) if self.keep_only_tags else soup.find("body")
        
        #根据书籍内置remove_xxx 属性，清理一些元素
        self.removeSoupElements(soup)

        #添加额外的CSS
        if self.AddCustomCss(soup):
            yield ItemCssTuple("custom.css", "custom.css", self.user.css_content)

        self.ProcessBeforeImage(soup)

        #逐个处理文章内的图像链接，生成对应的图像文件
        thumbnailUrl = None
        for imgManifest in self.PrepareImageManifest(soup, url):
            if not thumbnailUrl and imgManifest.isThumbnail:
                thumbnailUrl = imgManifest.url
            yield imgManifest

        #整理文章格式，比如添加内容标题，转换HTML5标签等
        self.NormalizeArticle(soup, title)
        
        self.PostProcess(soup)

        #插入分享链接，如果插入了qrcode，则返回(imgName, imgContent)
        qrImg = self.AppendShareLinksToArticle(soup, url)
        if qrImg:
            yield ItemImageTuple("image/jpeg", url, qrImg[0], qrImg[1], False)
        
        if self.user and self.user.use_title_in_feed:
            title = rssItem.title

        #提取文章内容的前面一部分做为摘要
        brief = self.ExtractBrief(soup)
        yield ItemHtmlTuple(rssItem.section, url, title, soup, brief, thumbnailUrl)
    
    #根据书籍 keep_only_tags 属性，创建一个新的 body 标签替代原先的
    #返回新创建的 body 标签
    def BuildNewSoupBody(self, soup):
        oldBodyTag = soup.find("body")
        bodyTag = soup.new_tag("body")
        keepOnlyTags = [self.keep_only_tags] if isinstance(self.keep_only_tags, dict) else self.keep_only_tags
        for spec in keepOnlyTags:
            for tag in oldBodyTag.find_all(**spec):
                bodyTag.insert(len(bodyTag.contents), tag)
        oldBodyTag.replace_with(bodyTag)
        return bodyTag

    #根据书籍内置remove_xxx 属性，清理一些元素
    def removeSoupElements(self, soup):
        for spec in self.remove_tags_after:
            tag = soup.find(**spec)
            remove_beyond(tag, 'next_sibling')

        for spec in self.remove_tags_before:
            tag = soup.find(**spec)
            remove_beyond(tag, 'previous_sibling')

        for tag in soup.find_all(self.insta_remove_tags + self.remove_tags):
            tag.decompose()
        for id_ in (self.insta_remove_ids + self.remove_ids):
            for tag in soup.find_all(attrs={"id": id_}):
                tag.decompose()
        for cls_ in (self.insta_remove_classes + self.remove_classes):
            for tag in soup.find_all(attrs={"class": cls_}):
                tag.decompose()
        for attr in (self.insta_remove_attrs + self.remove_attrs):
            for tag in soup.find_all(attrs={attr: True}):
                del tag[attr]
        for cmt in soup.find_all(text=lambda text: isinstance(text, Comment)):
            cmt.extract()
        
        #删除body的所有属性，以便InsertToc使用正则表达式匹配<body>
        bodyTag = soup.find("body")
        for attr in [attr for attr in bodyTag.attrs]:
            del bodyTag[attr]

    #逐个处理文章内的图像链接，生成对应的图像文件，然后使用生成器模式逐个返回 ItemImageTuple 实例
    #soup: BeautifulSoup 实例
    #url: 文章的URL
    def PrepareImageManifest(self, soup, url):
        if not self.keep_image: #不保留图像文件
            for imgTag in soup.find_all('img'):
                imgTag.decompose()
            return

        self.ProcessBeforeImage(soup)
        self.RectifyImageSrcInSoup(soup, url)
        opener = UrlOpener(self.host, timeout=self.timeout, headers=self.extra_header)
        allImgTag = list(soup.find_all('img'))
        for imgTag in allImgTag:
            imgUrl = imgTag["src"] if "src" in imgTag.attrs else ""
            if not imgUrl:
                imgTag.decompose()
                continue
                
            imgResult = opener.open(imgUrl)
            if imgResult.status_code != 200:
                self.log.warn('Fetch img failed({}):{}'.format(UrlOpener.CodeMap(imgResult.status_code), imgUrl))
                imgTag.decompose()
                continue

            imgContent = self.TransformImage(imgResult.content, self.SplitLongImage)
            
            if not isinstance(imgContent, list): #确认一个图片有没有分隔为多个图片
                imgContent = [imgContent]

            if len(imgContent[0]) < self.img_min_size: #图像太小，直接删除
                imgTag.decompose()
                continue

            #只需要判断第一个图像的格式即可，因为这个列表中的图像格式都一样
            imgType = imghdr.what(None, imgContent[0])
            if not imgType:
                imgTag.decompose()
                continue

            imgIndex = self.AutoImageIndex
            lastImgTag = imgTag
            imgPartUrl = imgUrl
            imgMime = "image/{}".format(imgType)
            imgType = imgType.replace("jpeg", "jpg")

            #第一个图片
            imgName = "img{}.{}".format(imgIndex, imgType)
            imgTag['src'] = imgName
            yield ItemImageTuple(imgMime, imgUrl, imgName, imgPartContent, True) #True-做为文章缩略图

            for idx, imgPartContent in enumerate(imgContent[1:]):
                imgName = "img{}_{}.{}".format(imgIndex, idx, imgType)
                imgPartUrl += '_'
                imgNew =  soup.new_tag('img', src=imgName)
                lastImgTag.insert_after(imgNew)
                lastImgTag = imgNew
                yield ItemImageTuple(imgMime, imgPartUrl, imgName, imgPartContent, False)

        #去掉图像上面的链接，以免误触后打开浏览器
        if self.user and self.user.remove_hyperlinks in ('image', 'all'):
            for imgTag in soup.find_all('img'):
                if imgTag.parent and imgTag.parent.parent and imgTag.parent.name == 'a':
                    imgTag.parent.replace_with(imgTag)
        
    #在文章中添加额外的自定义CSS，如果添加了文章外独立的CSS内容，返回True
    #调方根据user.css_content来生成custome.css文件
    def AddCustomCss(self, soup):
        headTag = soup.find("head")
        if self.extra_css:
            styleTag = soup.new_tag('style', type="text/css")
            styleTag.string = self.extra_css
            headTag.append(styleTag)
        
        #如果用户需要自定义CSS
        if self.user and self.user.css_content:
            styleTag = soup.new_tag('link', type='text/css', rel='stylesheet', href='custom.css')
            headTag.append(styleTag)
            return True
        else:
            return False

    #整理文章格式，比如添加内容标题，转换HTML5标签等
    def NormalizeArticle(self, soup, title):
        bodyTag = soup.find("body")
        hTag = bodyTag.find(['h1','h2'])
        if not hTag:
            hTag = soup.new_tag('h2')
            hTag.string = title
            bodyTag.insert(0, hTag)
        else:
            totallen = 0
            for tagPs in hTag.previous_siblings:
                totallen += len(tagPs.get_text(strip=True))
                if totallen > 50: #此H1/H2在文章中间出现，不是文章标题
                    newHtag = soup.new_tag('h2')
                    newHtag.string = title
                    bodyTag.insert(0, newHtag)
                    break

        #将HTML5标签转换为div
        for x in soup.find_all(['article', 'aside', 'header', 'footer', 'nav',
            'figcaption', 'figure', 'section', 'time']):
            x.name = 'div'

        #如果需要，去掉正文中的超链接(使用斜体下划线标识)，以避免误触
        if self.user and self.user.remove_hyperlinks in ('text', 'all'):
            for a_ in soup.find_all('a'):
                #a_.unwrap()
                a_.name = 'i'
                a_.attrs.clear()
                #a_.attrs['style'] = 'text-decoration:underline;'

    #提取文章内容的前面一部分做为摘要
    def ExtractBrief(self, soup):
        briefStrList = []
        briefLen = 0
        brief = ''
        #漫画模式不需要摘要
        if GENERATE_TOC_DESC and ((not self.user) or (self.user.book_mode != 'comic')):
            bodyTag = soup.find("body")
            for h in bodyTag.find_all(['h1','h2']): # 去掉h1/h2，避免和标题重复
                h.decompose()
            for s in bodyTag.stripped_strings:
                briefStrList.append(s)
                briefLen += len(s) + 1 #每次多一个空格
                if briefLen >= TOC_DESC_WORD_LIMIT:
                    brief = (" ".join(briefStrList))[:TOC_DESC_WORD_LIMIT]
                    break
        return brief

    #如果需要，纠正或规则化soup里面的图片地址，比如延迟加载等
    def RectifyImageSrcInSoup(self, soup, url=None):
        for img in soup.find_all('img'):
            #现在使用延迟加载图片技术的网站越来越多了，这里处理一下
            #注意：如果data-src|data-original|file之类的属性保存的不是真实url就没辙了
            imgUrl = img['src'] if 'src' in img.attrs else ''
            if not imgUrl or imgUrl.endswith('/none.gif'):
                for attr in img.attrs:
                    if attr != 'src' and (('src' in attr) or (attr == 'data-original')): #很多网站使用data-src|data-original
                        imgUrl = img[attr]
                        break
                if not imgUrl:
                    for attr in img.attrs:
                        if attr != 'src' and (('data' in attr) or ('file' in attr)): #如果上面的搜索找不到，再大胆一点猜测url
                            imgUrl = img[attr]
                            break
            
            if not imgUrl:
                img.decompose()
                continue
                
            if url and not imgUrl.startswith(('data:', 'http', 'www')):
                imgUrl = urljoin(url, imgUrl)
                
            if url and self.fetch_img_via_ssl and url.startswith('https://'):
                imgUrl = imgUrl.replace('http://', 'https://')
            
            if self.IsFiltered(imgUrl):
                self.log.warn('Image filtered:{}'.format(imgUrl))
                img.decompose()
                continue
            
            img['src'] = imgUrl #将更正的地址写回保存
            
            
    #根据一些配置，对图像进行处理，比如缩小，转灰度图，转格式，图像分隔等
    #data: 图像二进制内容
    #splitImageFunc: 用于分割图像的一个函数，传入参数为data，如果需要分割，则返回一个列表[data1,data2,...]，否则原样返回data
    #返回经过处理的图像二进制内容或分割为多个小图像文件二进制内容的列表
    def TransformImage(self, data, splitImageFunc):
        if not data:
            return None
        
        opts = self.opts
        if not (opts and opts.process_images and opts.process_images_immediately):
            return data

        splitedImages = splitImageFunc(data) if splitImageFunc else data
        if isinstance(splitedImages, list): #如果图被拆分，则返回一个图像列表，否则返回data
            return [compress_image(image, reduceTo=opts.reduce_image_to, pngToJpg=opts.image_png_to_jpg, graying=opts.graying_image) 
                for image in splitedImages]
        else:
            return compress_image(splitedImages, reduceTo=opts.reduce_image_to, pngToJpg=opts.image_png_to_jpg, graying=opts.graying_image)
        
    #如果一个图片太长，则将其分割成多个图片，方便在电子书上阅读
    #如果不需要分割，则可以原样返回data
    def SplitLongImage(self, data):
        if not THRESHOLD_SPLIT_LONG_IMAGE:
            return data
        
        threshold = max(self.opts.dest.screen_size[1], THRESHOLD_SPLIT_LONG_IMAGE)
        
        if not isinstance(data, io.BytesIO):
            data = io.BytesIO(data)
        imgInst = Image.open(data)
        width, height = imgInst.size
        
        #高至少是宽的三倍才认为是超长图
        if (height <= threshold) or (height < width * 3):
            return data
        else:
            return split_image_by_height(imgInst, threshold)

    #在文章末尾添加分享链接，如果文章末尾添加了网址的QRCODE，则此函数返回生成的图像(imgName, imgContent)，否则返回None
    def AppendShareLinksToArticle(self, soup, url):
        user = self.user
        if not user or not soup:
            return None
            
        FirstLink = True
        qrImg = None
        qrImgName = ''
        bodyTag = soup.find("body")
        if user.evernote and user.evernote_mail:
            href = self.MakeShareLink('evernote', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SAVE_TO_EVERNOTE
            bodyTag.append(ashare)
            FirstLink = False
        if user.wiz and user.wiz_mail:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('wiz', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SAVE_TO_WIZ
            bodyTag.append(ashare)
            FirstLink = False
        if user.pocket:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('pocket', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SAVE_TO_POCKET
            bodyTag.append(ashare)
            FirstLink = False
        if user.instapaper:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('instapaper', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SAVE_TO_INSTAPAPER
            bodyTag.append(ashare)
            FirstLink = False
        if user.xweibo:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('xweibo', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SHARE_ON_XWEIBO
            bodyTag.append(ashare)
            FirstLink = False
        if user.tweibo:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('tweibo', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SHARE_ON_TWEIBO
            bodyTag.append(ashare)
            FirstLink = False
        if user.facebook:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('facebook', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SHARE_ON_FACEBOOK
            bodyTag.append(ashare)
            FirstLink = False
        if user.twitter:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('twitter', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SHARE_ON_TWITTER
            bodyTag.append(ashare)
            FirstLink = False
        if user.tumblr:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('tumblr', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SHARE_ON_TUMBLR
            bodyTag.append(ashare)
            FirstLink = False
        if user.browser:
            if not FirstLink:
                self.AppendSeperator(soup)
            ashare = soup.new_tag('a', href=url)
            ashare.string = OPEN_IN_BROWSER
            bodyTag.append(ashare)
        if user.qrcode:
            import qrcode as qr_code
            if not FirstLink:
                self.AppendSeperator(soup)
            bodyTag.append(soup.new_tag('br'))
            qrImgName = 'img{}.jpg'.format(self.AutoImageIndex)
            imgshare = soup.new_tag('img', src=qrImgName)
            bodyTag.append(imgshare)
            img = qr_code.make(url)
            qrImg = io.BytesIO()
            img.save(qrImg, 'JPEG')
        
        return (qrImgName, qrImg.getvalue()) if qrImg else None
    
    #生成保存内容或分享文章链接的KindleEar调用链接
    def MakeShareLink(self, sharetype, user, url, soup):
        if sharetype in ('evernote', 'wiz'):
            href = "{}/share?act={}&u={}&url=".format(DOMAIN, sharetype, user.name)
        elif sharetype == 'pocket':
            href = '{}/share?act=pocket&u={}&h={}&t={}&url='.format(DOMAIN, user.name, (hashlib.md5(user.pocket_acc_token_hash or '').hexdigest()), 
                                                        soup.html.head.title.string)
        elif sharetype == 'instapaper':
            href = '{}/share?act=instapaper&u={}&n={}&t={}&url='.format(DOMAIN, user.name, user.instapaper_username or '', soup.html.head.title.string)
        elif sharetype == 'xweibo':
            href = 'http://v.t.sina.com.cn/share/share.php?url='
        elif sharetype == 'tweibo':
            href = 'http://v.t.qq.com/share/share.php?url='
        elif sharetype == 'facebook':
            href = 'http://www.facebook.com/share.php?u='
        elif sharetype == 'twitter':
            href = 'http://twitter.com/home?status='
        elif sharetype == 'tumblr':
            href = 'http://www.tumblr.com/share/link?url='
        else:
            href = ''
        if user.share_fuckgfw and sharetype in ('evernote', 'wiz', 'facebook', 'twitter', 'pocket', 'instapaper'):
            href = SHARE_FUCK_GFW_SRV.format(quote_plus(href + url))
        else:
            href += quote_plus(url)
        return href

    #在文章末尾添加'|'分隔符
    def AppendSeperator(self, soup):
        span = soup.new_tag("span")
        span.string = ' | '
        soup.html.body.append(span)

    #登陆网站然后将cookie自动保存在opener内，以便应付一些必须登陆才能下载网页的网站。
    #因为GAE环境的限制，所以如果需要javascript才能登陆的网站就不支持了，
    #需要验证码的网站也无法支持。
    def login(self, opener):
        if not all((self.login_url, self.account, self.password)):
            return
        
        resp = self.FetchArticle(self.login_url, opener)
        if not resp:
            return
        content = resp.text
        #from lib.debug_utils import debug_mail
        #debug_mail(content)
        soup = BeautifulSoup(content, 'lxml')
        form = self.SelectLoginForm(soup)
        
        if not form:
            self.log.warn('Cannot found login form!')
            return
        
        self.log.info('Form selected for login:name({}),id({}),class({})'.format(form.get('name'), form.get('id'), form.get('class')))
        
        method = form.get('method', 'get').upper()
        action = urljoin(self.login_url, form['action']) if form.get('action') else self.login_url
        
        #判断帐号域和密码域
        inputs = list(form.find_all('input', attrs={'type': ['text', 'email', 'password']}))
        fieldName = fieldPwd = None
        if len(inputs) == 2: #只有两个输入域则假定第一个为账号第二个为密码
            fieldName, fieldPwd = inputs[0], inputs[1]
        elif len(inputs) > 2: #可能需要验证码？先不管了，提取出账号密码域尝试一下
            for idx, field in enumerate(inputs[1:], 1):
                if field['type'].lower() == 'password': #同时假定密码域的前一个是账号域
                    fieldName, fieldPwd = inputs[idx - 1], field
                    break
        
        if not fieldName or not fieldPwd:
            self.log.warn('Cant determine fields for account and password in login form!')
            return
            
        #直接返回其他元素（包括隐藏元素）
        name_of_field = lambda x: x.get('name') or x.get('id') #用于搜索的内嵌lambda函数
        fieldsDic = {name_of_field(e): e.get('value', '') for e in form.find_all('input') if name_of_field(e)}
        #填写账号密码
        fieldsDic[name_of_field(fieldName)] = self.account
        fieldsDic[name_of_field(fieldPwd)] = self.password
        
        if method == 'GET':
            parts = urlparse(action)
            qs = parse_qs(parts.query)
            fieldsDic.update(qs)
            newParts = parts[:-2] + (urlencode(fieldsDic), None)
            targetUrl = urlunparse(newParts)
            #self.log.debug('Login url : ' + targetUrl)
            return opener.open(targetUrl)
        else:
            #self.log.info('field_dic:%s' % repr(fieldsDic))
            targetUrl = action
            return opener.open(targetUrl, data=fieldsDic)
    
    #根据用户提供的信息提取登陆表单或猜测哪个Form才是登陆表单
    #一个一个BeautifulSoup的Tag实例
    def SelectLoginForm(self, soup):
        formTag = None
        clue = self.login_form
        if isinstance(clue, int): #通过序号选择表单
            forms = soup.select('form:nth-of-type({})'.format(clue + 1))
            formTag = forms[0] if forms else None
        elif isinstance(clue, str): #通过名字
            if clue.startswith('#'): #id
                formTag = soup.find(lambda f: f.name == 'form' and f.get('id') == clue[1:])
            elif clue.startswith('.'): #class
                formTag = soup.find(lambda f: f.name == 'form' and clue[1:] in f.get('class', ""))
            else: #name & id & class
                formTag = soup.find(lambda f: f.name == 'form' and ((f.get('name') == clue) 
                    or (f.get('id') == clue) or (clue in f.get('class', ""))))
        else: #自动猜测
            forms = list(soup.find_all('form'))
            if len(forms) == 1:
                formTag = forms[0]
            elif len(forms) > 1:
                for f in forms:
                    #根据表单内元素判断，登陆表单一般来说有一个且只有一个密码域
                    if len(f.find_all(lambda e: e.name == 'input' and e.get('type', '').lower() == 'password')) == 1:
                        formTag = f
                        break
                if not formTag: #如果上面最稳妥的方式找不到，再试其他方法
                    for f in forms:
                        #根据表单内密码域的名字判断
                        for e in f.find_all('input'):
                            eName = e.get('name', '').lower()
                            if any(('password' in eName, 'pwd' in eName, 'pass' in eName)):
                                formTag = f
                                break
                        
                        #根据名字或提交地址猜测
                        fName = (f.get('id', '') or ''.join(f.get('class', ""))).lower()
                        action = f.get('action', '').lower()
                        if ('log' in fName) or ('log' in action):
                            formTag = f
                            break
                        
                #if not formTag: #如果无法判断，则假定第二个为登陆表单
                #    formTag = forms[1]
        return formTag
    
    #链接网络，下载网页，为了后续处理方便，这里在保证内容有效的前提下返回一个 requests 模块的 Response 实例
    #使用其实例的 text 属性获取解码后的文本，content 属性获取二进制内容
    def FetchArticle(self, url, opener):
        result = opener.open(url)
        status_code = result.status_code
        if status_code not in (200, 206):
            self.log.warn('Fetch page failed({}):{}.'.format(UrlOpener.CodeMap(status_code), url))
            return None
        else:
            #from lib.debug_utils import debug_mail
            #debug_mail(result.text)
            return result
        

#几个小工具函数
def remove_beyond(tag, next):
    while (tag is not None) and getattr(tag, "name", "") != "body":
        after = getattr(tag, next)
        while after is not None:
            after.extract()
            after = getattr(tag, next)
        tag = tag.parent

