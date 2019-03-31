#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
KindleEar电子书基类，每本投递到kindle的书籍抽象为这里的一个类。
可以继承BaseFeedBook类而实现自己的定制书籍。
cdhigh <https://github.com/cdhigh>
"""
import os, re, urllib, urlparse, imghdr, datetime, hashlib
from urllib2 import *

from bs4 import BeautifulSoup, Comment, NavigableString, CData, Tag
from lib import feedparser
from lib.readability import readability
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from apps.dbModels import LastDelivered

from calibre.utils.img import rescale_image, mobify_image
from PIL import Image
from StringIO import StringIO

from config import *

htmlTemplate = """
<html>
<head>
<meta http-equiv="Content-Type" content="text/html;charset=utf-8">
<title>%s</title>
</head>
<body><img src="%s"/></body>
</html>""".strip()


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

    #下面这两个编码建议设置，如果留空，则使用自动探测解码，稍耗费CPU
    feed_encoding = '' # RSS编码，一般为XML格式，直接打开源码看头部就有编码了
    page_encoding = '' # 页面编码，获取全文信息时的网页编码

    # 题图文件名，格式：gif(600*60)，所有图片文件存放在images/下面，文件名不需要images/前缀
    # 如果不提供此图片，软件使用PIL生成一个，但是因为GAE不能使用ImageFont组件
    # 所以字体很小，而且不支持中文标题，使用中文会出错
    mastheadfile = DEFAULT_MASTHEAD
    
    #封面图片文件，如果值为一个字符串，则对应到images目录下的文件
    #如果需要在线获取封面或自己定制封面（比如加日期之类的），则可以自己写一个回调函数，输入一个参数（类实例），返回图片的二进制数据（支持gif/jpg/png格式）
    #回调函数要求为独立的函数，不能为类方法或实例方法。
    #如果回调函数返回的不是图片或为None，则还是直接使用DEFAULT_COVER
    coverfile = DEFAULT_COVER
    
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

    #如果为True则使用instapaper服务先清理网页，否则直接连URL下载网页内容
    #instapaper的服务很赞，能将一个乱七八糟的网页转换成只有正文内容的网页
    #但是缺点就是不太稳定，经常连接超时，建议设置为False
    #这样你需要自己编程清理网页，建议使用下面的keep_only_tags[]工具
    fulltext_by_instapaper = False

    #如果设置为True则需要提供用户名和密码，并且还要提供登陆URL
    #如果登陆界面比较复杂，有可能你需要重新实现login函数
    needs_subscription = False
    login_url = ''
    account = ''
    password = ''
    #None为自动猜测，字符串则是表单id或class，整数则为html中form序号（从0开始）
    form_4_login = None
    
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
    insta_remove_tags = ['script','object','video','embed','noscript','style','link']
    insta_remove_attrs = ['width','height','onclick','onload','style']
    insta_remove_classes = []
    insta_remove_ids = ['controlbar_container',]

    #---------------add by rexdf-------------
    #下面的积极关键词,有些内容会被readability过滤掉，比如html5的figure，可以通过增加权重保留
    #这个是针对部分html5网站优化的，子类需要修改可以不用继承，因为子类往往针对特定某一网站，可以专门定制
    positive_classes = ['image-block','image-block-caption','image-block-ins']

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
    #注意，如果分节标题是中文的话，增加u前缀，比如
    #(u'8小时最热', 'http://www.qiushibaike.com'),
    feeds = []

    #几个钩子函数，基类在适当的时候会调用，
    #子类可以使用钩子函数进一步定制

    #普通Feed在网页元素拆分分析前调用，全文Feed在FEED拆分前调用
    #网络上大部分的RSS都是普通Feed，只有概要信息
    #content为网页字符串，记得处理后返回字符串
    def preprocess(self, content):
        return content

    #网页title处理，比如去掉网站标识，一长串的SEQ字符串等
    #返回处理后的title
    def processtitle(self, title):
        return re.sub(r'(\n)+', ' ', title)

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
    def __init__(self, log=None, imgindex=0, opts=None, user=None):
        self.log = default_log if log is None else log
        self.compiled_urlfilters = []
        self._imgindex = imgindex
        self.opts = opts
        self.user = user
        self.last_delivered_volume = '' #如果需要在推送书籍的标题中提供当前期号之类的信息，可以使用此属性
        
    @property
    def timeout(self):
        return self.network_timeout if self.network_timeout else CONNECTION_TIMEOUT
        
    @property
    def imgindex(self):
        self._imgindex += 1
        return self._imgindex
        
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
        
    #返回当前任务的用户名
    def UserName(self):
        return self.user.name if self.user else "admin"

    # 返回最近推送的章节标题
    def LastDeliveredVolume(self):
        return self.last_delivered_volume
        
    @classmethod
    def urljoin(self, base, url):
        #urlparse.urljoin()处理有..的链接有点问题，此函数修正此问题。
        join = urlparse.urljoin(base, url)
        url = urlparse.urlsplit(join)
        path = os.path.normpath(url.path)
        if IsRunInLocal: #假定调试环境为windows
            path = path.replace('\\', '/')
        return urlparse.urlunsplit((url.scheme, url.netloc, path, url.query, url.fragment))

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
        tnow = datetime.datetime.utcnow()
        urladded = set()
        
        for feed in self.feeds:
            section, url = feed[0], feed[1]
            isfulltext = feed[2] if len(feed) > 2 else False
            timeout = self.timeout+10 if isfulltext else self.timeout
            opener = URLOpener(self.host, timeout=timeout, headers=self.extra_header)
            result = opener.open(url)
            if result.status_code == 200 and result.content:
                #debug_mail(result.content, 'feed.xml')
                decoder = AutoDecoder(isfeed=True)
                content = self.AutoDecodeContent(result.content, decoder, self.feed_encoding, opener.realurl, result.headers)
                
                feed = feedparser.parse(content)
                
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
                        delta = tnow - updated
                        if self.oldest_article > 365:
                            threshold = self.oldest_article #以秒为单位
                        else:
                            threshold = 86400*self.oldest_article #以天为单位
                        
                        if delta.days*86400+delta.seconds > threshold:
                            self.log.info("Skip old article(%s): %s" % (updated.strftime('%Y-%m-%d %H:%M:%S'), e.link))
                            continue
                    
                    title = e.title if hasattr(e, 'title') else 'Untitled'
                    
                    #支持HTTPS
                    if hasattr(e, 'link'):
                        if url.startswith('https://'):
                            urlfeed = e.link.replace('http://','https://')
                        else:
                            urlfeed = e.link
                            
                        if urlfeed in urladded:
                            continue
                    else:
                        urlfeed = ''
                    
                    desc = None
                    if isfulltext:
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
                            if not urlfeed:
                                continue
                            else:
                                self.log.warn('Fulltext feed item no has desc,link to webpage for article.(%s)' % title)
                    
                    urladded.add(urlfeed)
                    #针对URL里面有unicode字符的处理，否则会出现Bad request
                    #后面参数里面的那一堆“乱码”是要求不处理ASCII的特殊符号，只处理非ASCII字符
                    urlfeed = urllib.quote_plus(urlfeed.encode('utf-8'), r'''~`!@#$%^&*()|\\/,.<>;:"'{}[]?=-_+''')
                    urls.append((section, title, urlfeed, desc))
            else:
                self.log.warn('fetch rss failed(%s):%s' % (URLOpener.CodeMap(result.status_code), url))
                
        return urls

    def Items(self):
        """
        生成器，返回一个元组
        对于HTML：section,url,title,content,brief,thumbnail
        对于图片，mime,url,filename,content,brief,thumbnail
        """
        urls = self.ParseFeedUrls()
        readability = self.readability if self.fulltext_by_readability else self.readability_by_soup
        prevsection = ''
        opener = URLOpener(self.host, timeout=self.timeout, headers=self.extra_header)
        decoder = AutoDecoder(isfeed=False)
        for section, fTitle, url, desc in urls:
            if not desc: #非全文RSS
                if section != prevsection or prevsection == '':
                    decoder.encoding = '' #每个小节都重新检测编码
                    prevsection = section
                    opener = URLOpener(self.host, timeout=self.timeout, headers=self.extra_header)
                    if self.needs_subscription:
                        result = self.login(opener, decoder)
                        #if result:
                        #     debug_mail(result.content, 'login_result.html')
                        #    debug_save_ftp(result.content, 'login_result.html')
                        #else:
                        #    self.log.warn('func login return none!')                        
        
                article = self.fetcharticle(url, opener, decoder)
                if not article:
                    continue
            else:
                article = self.FragToXhtml(desc, fTitle)
            
            #如果是图片，title则是mime
            for title, imgurl, imgfn, content, brief, thumbnail in readability(article, url):
                if title.startswith(r'image/'): #图片
                    yield (title, imgurl, imgfn, content, brief, thumbnail)
                else:
                    if self.user and self.user.use_title_in_feed:
                        title = fTitle
                    elif not title:
                        title = fTitle
                    content = self.postprocess(content)
                    yield (section, url, title, content, brief, thumbnail)

    def fetcharticle(self, url, opener, decoder):
        """链接网页获取一篇文章"""
        if self.fulltext_by_instapaper and not self.fulltext_by_readability:
            url = "http://www.instapaper.com/m?u=%s" % self.url_unescape(url)
        
        return self.fetch(url, opener, decoder)
        
    def login(self, opener, decoder):
        """登陆网站然后将cookie自动保存在opener内，以便应付一些必须登陆才能下载网页的网站。
        因为GAE环境的限制，所以如果需要javascript才能登陆的网站就不支持了，
        需要验证码的网站也无法支持。
        """
        if not all((self.login_url, self.account, self.password)):
            return
        
        content = self.fetch(self.login_url, opener, decoder)
        if not content:
            return
        #debug_mail(content)
        soup = BeautifulSoup(content, 'lxml')
        form = self.SelectLoginForm(soup)
        
        if not form:
            self.log.warn('Cannot found login form!')
            return
        
        self.log.info('Form selected for login:name(%s),id(%s),class(%s)' % (form.get('name'),form.get('id'),form.get('class')))
        
        method = form.get('method', 'get').upper()
        action = self.urljoin(self.login_url, form['action']) if form.get('action') else self.login_url
        
        #判断帐号域和密码域
        inputs = list(form.find_all('input', attrs={'type':['text','email','password']}))
        field_name = field_pwd = None
        if len(inputs) == 2: #只有两个输入域则假定第一个为账号第二个为密码
            field_name, field_pwd = inputs[0], inputs[1]
        elif len(inputs) > 2: #可能需要验证码？先不管了，提取出账号密码域尝试一下
            for idx,field in enumerate(inputs[1:],1):
                if field['type'].lower() == 'password': #同时假定密码域的前一个是账号域
                    field_name, field_pwd = inputs[idx-1], field
                    break
        
        if not field_name or not field_pwd:
            self.log.warn('Cant determine fields for account and password in login form!')
            return
            
        #直接返回其他元素（包括隐藏元素）
        name_of_field = lambda x:x.get('name') or x.get('id')
        input_elems = list(form.find_all('input'))
        fields_dic = {name_of_field(e):e.get('value','') for e in input_elems if name_of_field(e)}
        #填写账号密码
        fields_dic[name_of_field(field_name)] = self.account
        fields_dic[name_of_field(field_pwd)] = self.password
        
        if method == 'GET':
            parts = urlparse.urlparse(action)
            qs = urlparse.parse_qs(parts.query)
            fields_dic.update(qs)
            newParts = parts[:-2] + (urllib.urlencode(fields_dic), None)
            target_url = urlparse.urlunparse(newParts)
            #self.log.debug('Login url : ' + target_url)
            return opener.open(target_url)
        else:
            #self.log.info('field_dic:%s' % repr(fields_dic))
            target_url = action
            return opener.open(target_url, data=fields_dic)
            
    def SelectLoginForm(self, soup):
        "根据用户提供的信息提取登陆表单或猜测哪个Form才是登陆表单"
        form = None
        if isinstance(self.form_4_login, (int,long)): #通过序号选择表单
            forms = soup.select('form:nth-of-type(%d)' % (self.form_4_login+1))
            form = forms[0] if forms else None
        elif isinstance(self.form_4_login, basestring): #通过名字
            if self.form_4_login.startswith('#'): #id
                form = soup.find(lambda f: f.name=='form' and f.get('id')==self.form_4_login[1:])
            elif self.form_4_login.startswith('.'): #class
                form = soup.find(lambda f: f.name=='form' and self.form_4_login[1:] in f.get('class',[]))
            else: #name & id & class
                form = soup.find(lambda f: f.name=='form' and (f.get('name')==self.form_4_login 
                    or f.get('id')==self.form_4_login or self.form_4_login in f.get('class',[])))
        else: #自动猜测
            forms = list(soup.find_all('form'))
            if len(forms) == 1:
                form = forms[0]
            elif len(forms) > 1:
                for f in forms:
                    #根据表单内元素判断，登陆表单一般来说有一个且只有一个密码域
                    if len(f.find_all(lambda e:e.name=='input' and e.get('type','').lower()=='password')) == 1:
                        form = f
                        break
                if not form: #如果上面最稳妥的方式找不到，再试其他方法
                    for f in forms:
                        #根据表单内密码域的名字判断
                        for e in f.find_all('input'):
                            ename = e.get('name','').lower()
                            if 'password' in ename or 'pwd' in ename or 'pass' in ename:
                                form = f
                                break
                        
                        #根据名字或提交地址猜测
                        fname = (f.get('id','') or ''.join(f.get('class',[]))).lower()
                        action = f.get('action','').lower()
                        if ('log' in fname) or ('log' in action):
                            form = f
                            break
                        
                if not form: #如果无法判断，则假定第二个为登陆表单
                    form = forms[1]
        return form
        
    def fetch(self, url, opener, decoder):
        """链接网络，下载网页并解码"""
        result = opener.open(url)
        status_code, content = result.status_code, result.content
        if status_code not in (200, 206) or not content:
            self.log.warn('fetch page failed(%s):%s.' % (URLOpener.CodeMap(status_code), url))
            return None
        
        #debug_mail(content)
        return self.AutoDecodeContent(content, decoder, self.page_encoding, opener.realurl, result.headers)
        
    #自动解码，返回解码后的网页
    #content: 要解码的网页
    #decoder: AutoDecoder实例
    #defaultEncoding: 默认的编码
    #url: 网页的原始url地址（注意可能和之前opener使用的url不同，因为有可能发生了重定向，所以建议使用opener.realurl属性）
    #headers: 网页返回的http响应头
    def AutoDecodeContent(self, content, decoder, defaultEncoding=None, url=None, headers=None):
        if defaultEncoding:
            try:
                return content.decode(defaultEncoding)
            except UnicodeDecodeError:
                return decoder.decode(content, url, headers)
        else:
            return decoder.decode(content, url, headers)
        
    def readability(self, article, url):
        """ 使用readability-lxml处理全文信息
        因为图片文件占内存，为了节省内存，这个函数也做为生成器
        """
        user = self.user
        content = self.preprocess(article)
        if not content:
            return
            
        # 提取正文
        try:
            doc = readability.Document(content,positive_keywords=self.positive_classes)
            summary = doc.summary(html_partial=False)
        except:
            # 如果提取正文出错，可能是图片（一个图片做为一篇文章，没有使用html包装）
            imgtype = imghdr.what(None, content)
            if imgtype: #如果是图片，则使用一个简单的html做为容器
                imgmime = r"image/" + imgtype
                fnimg = "img%d.%s" % (self.imgindex, 'jpg' if imgtype=='jpeg' else imgtype)
                yield (imgmime, url, fnimg, content, None, None)
                tmpHtml = '<html><head><title>Picture</title></head><body><img src="%s" /></body></html>' % fnimg
                yield ('Picture', None, None, tmpHtml, '', None)
            else:
                self.log.warn('article is invalid.[%s]' % url)
            return
        
        title = doc.short_title()
        if not title:
            self.log.warn('article has no title.[%s]' % url)
            return
        
        title = self.processtitle(title)
        
        soup = BeautifulSoup(summary, "lxml")
        
        #如果readability解析失败，则启用备用算法（不够好，但有全天候适应能力）
        body = soup.find('body')
        head = soup.find('head')
        if not body or len(body.contents) == 0:
            from simpleextract import simple_extract
            summary = simple_extract(content)
            soup = BeautifulSoup(summary, "lxml")
            body = soup.find('body')
            if not body:
                self.log.warn('extract article content failed.[%s]' % url)
                return
                
            head = soup.find('head')
            #增加备用算法提示，提取效果不好不要找我，类似免责声明：）
            info = soup.new_tag('p', style='color:#555555;font-size:60%;text-align:right;')
            info.string = 'extracted by alternative algorithm.'
            body.append(info)
            
            self.log.info('use alternative algorithm to extract content.')
            
        if not head:
            head = soup.new_tag('head')
            soup.html.insert(0, head)
            
        if not head.find('title'):
            t = soup.new_tag('title')
            t.string = title
            head.append(t)
            
        #如果没有内容标题则添加
        t = body.find(['h1','h2'])
        if not t:
            t = soup.new_tag('h2')
            t.string = title
            body.insert(0, t)
        else:
            totallen = 0
            for ps in t.previous_siblings:
                totallen += len(string_of_tag(ps))
                if totallen > 40: #此H1/H2在文章中间出现，不是文章标题
                    t = soup.new_tag('h2')
                    t.string = title
                    body.insert(0, t)
                    break
                    
        if self.remove_tags:
            for tag in soup.find_all(self.remove_tags):
                tag.decompose()
        for id_ in self.remove_ids:
            for tag in soup.find_all(attrs={"id":id_}):
                tag.decompose()
        for cls in self.remove_classes:
            for tag in soup.find_all(attrs={"class":cls}):
                tag.decompose()
        for attr in self.remove_attrs:
            for tag in soup.find_all(attrs={attr:True}):
                del tag[attr]
        for cmt in soup.find_all(text=lambda text:isinstance(text, Comment)):
            cmt.extract()

        #删除body的所有属性，以便InsertToc使用正则表达式匹配<body>
        bodyattrs = [attr for attr in body.attrs]
        for attr in bodyattrs:
            del body[attr]

        if self.extra_css:
            sty = soup.new_tag('style', type="text/css")
            sty.string = self.extra_css
            soup.html.head.append(sty)

        self.soupbeforeimage(soup)

        has_imgs = False
        thumbnail = None

        if self.keep_image:
            self.RectifyImageSrcInSoup(soup, url)
            opener = URLOpener(self.host, timeout=self.timeout, headers=self.extra_header)
            for img in soup.find_all('img'):
                imgurl = img['src'] if 'src' in img.attrs else None
                if not imgurl:
                    continue
                    
                imgresult = opener.open(imgurl)
                imgcontent = self.process_image(imgresult.content) if imgresult.status_code == 200 else None
                if imgcontent:
                    if isinstance(imgcontent, (list, tuple)): #一个图片分隔为多个图片
                        imgIndex = self.imgindex
                        lastImg = img
                        imgPartUrl = imgurl
                        for idx, imgPartContent in enumerate(imgcontent):
                            fnImg = "img%d_%d.jpg" % (imgIndex, idx)
                            if idx == 0: #第一个分图
                                img['src'] = fnImg
                            else: #其他部分
                                imgPartUrl += '_'
                                imgNew =  soup.new_tag('img', src=fnImg)
                                lastImg.insert_after(imgNew)
                                lastImg = imgNew
                            
                            #使用第一个图片做为目录缩略图
                            if not has_imgs:
                                has_imgs = True
                                thumbnail = imgPartUrl
                                yield ('image/jpeg', imgPartUrl, fnImg, imgPartContent, None, True)
                            else:
                                yield ('image/jpeg', imgPartUrl, fnImg, imgPartContent, None, None)
                    else: #单个图片
                        if len(imgcontent) < self.img_min_size: #rexdf too small image
                            img.decompose()
                            continue

                        imgtype = imghdr.what(None, imgcontent)
                        if imgtype:
                            imgmime = r"image/" + imgtype
                            fnimg = "img%d.%s" % (self.imgindex, 'jpg' if imgtype=='jpeg' else imgtype)
                            img['src'] = fnimg

                            #使用第一个图片做为目录缩略图
                            if not has_imgs:
                                has_imgs = True
                                thumbnail = imgurl
                                yield (imgmime, imgurl, fnimg, imgcontent, None, True)
                            else:
                                yield (imgmime, imgurl, fnimg, imgcontent, None, None)
                        else:
                            img.decompose()
                else:
                    self.log.warn('fetch img failed(%s):%s' % (URLOpener.CodeMap(imgresult.status_code), imgurl))
                    img.decompose()

            #去掉图像上面的链接，以免误触后打开浏览器
            if user and user.remove_hyperlinks in (u'image', u'all', 'image', 'all'):
                for img in soup.find_all('img'):
                    if img.parent and img.parent.parent and img.parent.name == 'a':
                        img.parent.replace_with(img)
        else:
            for img in soup.find_all('img'):
                img.decompose()
        
        #将HTML5标签转换为div
        for x in soup.find_all(['article', 'aside', 'header', 'footer', 'nav',
            'figcaption', 'figure', 'section', 'time']):
            x.name = 'div'
        
        self.soupprocessex(soup)

        #如果需要，去掉正文中的超链接(使用斜体下划线标识)，以避免误触
        if user and user.remove_hyperlinks in (u'text', u'all', 'text', 'all'):
            for a_ in soup.find_all('a'):
                #a_.unwrap()
                a_.name = 'i'
                a_.attrs.clear()
                #a_.attrs['style'] = 'text-decoration:underline;'

        #插入分享链接，如果有插入qrcode，则返回(imgName, imgContent)
        qrimg = self.AppendShareLinksToArticle(soup, url)
        if qrimg:
            yield ('image/jpeg', url, qrimg[0], qrimg[1], None, None)

        content = unicode(soup)

        #提取文章内容的前面一部分做为摘要，[漫画模式不需要摘要]
        brief = u''
        if GENERATE_TOC_DESC and ((not user) or user.book_mode != 'comic'):
            for h in body.find_all(['h1','h2']): # 去掉h1/h2，避免和标题重复
                h.decompose()
            for s in body.stripped_strings:
                brief += unicode(s) + u' '
                if len(brief) >= TOC_DESC_WORD_LIMIT:
                    brief = brief[:TOC_DESC_WORD_LIMIT]
                    break
        soup = None

        yield (title, None, None, content, brief, thumbnail)

    def readability_by_soup(self, article, url):
        """ 使用BeautifulSoup手动解析网页，提取正文内容
        因为图片文件占内存，为了节省内存，这个函数也做为生成器
        """
        user = self.user
        content = self.preprocess(article)
        soup = BeautifulSoup(content, "lxml")

        try:
            title = soup.html.head.title.string
        except AttributeError:
            self.log.warn('object soup invalid!(%s)' % url)
            return
        if not title:
            self.log.warn('article has no title.[%s]' % url)
            return

        title = self.processtitle(title)
        soup.html.head.title.string = title

        if self.keep_only_tags:
            body = soup.new_tag('body')
            try:
                if isinstance(self.keep_only_tags, dict):
                    keep_only_tags = [self.keep_only_tags]
                else:
                    keep_only_tags = self.keep_only_tags
                for spec in keep_only_tags:
                    for tag in soup.find('body').find_all(**spec):
                        body.insert(len(body.contents), tag)
                soup.find('body').replace_with(body)
            except AttributeError: # soup has no body element
                pass

        for spec in self.remove_tags_after:
            tag = soup.find(**spec)
            remove_beyond(tag, 'next_sibling')

        for spec in self.remove_tags_before:
            tag = soup.find(**spec)
            remove_beyond(tag, 'previous_sibling')

        remove_tags = self.insta_remove_tags + self.remove_tags
        remove_ids = self.insta_remove_ids + self.remove_ids
        remove_classes = self.insta_remove_classes + self.remove_classes
        remove_attrs = self.insta_remove_attrs + self.remove_attrs

        for tag in soup.find_all(remove_tags):
            tag.decompose()
        for id_ in remove_ids:
            for tag in soup.find_all(attrs={"id":id_}):
                tag.decompose()
        for cls in remove_classes:
            for tag in soup.find_all(attrs={"class":cls}):
                tag.decompose()
        for attr in remove_attrs:
            for tag in soup.find_all(attrs={attr:True}):
                del tag[attr]
        for cmt in soup.find_all(text=lambda text:isinstance(text, Comment)):
            cmt.extract()

        if self.extra_css:
            sty = soup.new_tag('style', type="text/css")
            sty.string = self.extra_css
            soup.html.head.append(sty)

        self.soupbeforeimage(soup)

        has_imgs = False
        thumbnail = None

        if self.keep_image:
            self.RectifyImageSrcInSoup(soup, url)
            opener = URLOpener(self.host, timeout=self.timeout, headers=self.extra_header)
            for img in soup.find_all('img'):
                imgurl = img['src'] if 'src' in img.attrs else None
                if not imgurl:
                    continue
                
                imgresult = opener.open(imgurl)
                imgcontent = self.process_image(imgresult.content) if imgresult.status_code == 200 else None
                if imgcontent:
                    if isinstance(imgcontent, list): #一个图片分隔为多个图片
                        imgIndex = self.imgindex
                        lastImg = img
                        imgPartUrl = imgurl
                        for idx, imgPartContent in enumerate(imgcontent):
                            fnImg = "img%d_%d.jpg" % (imgIndex, idx)
                            if idx == 0: #第一个分图
                                img['src'] = fnImg
                            else: #其他部分
                                imgPartUrl += '_'
                                imgNew =  soup.new_tag('img', src=fnImg)
                                lastImg.insert_after(imgNew)
                                lastImg = imgNew
                            
                            #使用第一个图片做为目录缩略图
                            if not has_imgs:
                                has_imgs = True
                                thumbnail = imgPartUrl
                                yield ('image/jpeg', imgPartUrl, fnImg, imgPartContent, None, True)
                            else:
                                yield ('image/jpeg', imgPartUrl, fnImg, imgPartContent, None, None)
                    else: #单个图片
                        if len(imgcontent) < self.img_min_size: #rexdf too small image
                            img.decompose()
                            continue

                        imgtype = imghdr.what(None, imgcontent)
                        if imgtype:
                            imgmime = r"image/" + imgtype
                            fnimg = "img%d.%s" % (self.imgindex, 'jpg' if imgtype=='jpeg' else imgtype)
                            img['src'] = fnimg

                            #使用第一个图片做为目录缩略图
                            if not has_imgs:
                                has_imgs = True
                                thumbnail = imgurl
                                yield (imgmime, imgurl, fnimg, imgcontent, None, True)
                            else:
                                yield (imgmime, imgurl, fnimg, imgcontent, None, None)
                        else:
                            img.decompose()
                else:
                    self.log.warn('fetch img failed(%s):%s' % (URLOpener.CodeMap(imgresult.status_code), imgurl))
                    img.decompose()

            #去掉图像上面的链接，以免误触后打开浏览器
            if user and user.remove_hyperlinks in (u'image', u'all', 'image', 'all'):
                for img in soup.find_all('img'):
                    if img.parent and img.parent.parent and img.parent.name == 'a':
                        img.parent.replace_with(img)
        else:
            for img in soup.find_all('img'):
                img.decompose()

        #如果没有内容标题则添加
        body = soup.html.body
        t = body.find(['h1','h2'])
        if not t:
            t = soup.new_tag('h2')
            t.string = title
            body.insert(0, t)
        else:
            totallen = 0
            for ps in t.previous_siblings:
                totallen += len(string_of_tag(ps))
                if totallen > 40: #此H1/H2在文章中间出现，不是文章标题
                    t = soup.new_tag('h2')
                    t.string = title
                    body.insert(0, t)
                    break

        #删除body的所有属性，以便InsertToc使用正则表达式匹配<body>
        bodyattrs = [attr for attr in body.attrs]
        for attr in bodyattrs:
            del body[attr]
        
        #将HTML5标签转换为div
        for x in soup.find_all(['article', 'aside', 'header', 'footer', 'nav',
            'figcaption', 'figure', 'section', 'time']):
            x.name = 'div'
        
        self.soupprocessex(soup)

        #如果需要，去掉正文中的超链接(使用斜体下划线标识)，以避免误触
        if user and user.remove_hyperlinks in (u'text', u'all', 'text', 'all'):
            for a_ in soup.find_all('a'):
                #a_.unwrap()
                a_.name = 'i'
                a_.attrs.clear()
                #a_.attrs['style'] = 'text-decoration:underline;'

        #插入分享链接，如果插入了qrcode，则返回(imgName, imgContent)
        qrimg = self.AppendShareLinksToArticle(soup, url)
        if qrimg:
            yield ('image/jpeg', url, qrimg[0], qrimg[1], None, None)
        
        content = unicode(soup)

        #提取文章内容的前面一部分做为摘要，[漫画模式不需要摘要]
        brief = u''
        if GENERATE_TOC_DESC and ((not user) or user.book_mode != 'comic'):
            for h in body.find_all(['h1','h2']): # 去掉h1/h2，避免和标题重复
                h.decompose()
            for s in body.stripped_strings:
                brief += unicode(s) + u' '
                if len(brief) >= TOC_DESC_WORD_LIMIT:
                    brief = brief[:TOC_DESC_WORD_LIMIT]
                    break
        soup = None

        yield (title, None, None, content, brief, thumbnail)
    
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
                
            if url and not imgUrl.startswith(('data:', 'http')):
                imgUrl = self.urljoin(url, imgUrl)
                
            if url and self.fetch_img_via_ssl and url.startswith('https://'):
                imgUrl = imgUrl.replace('http://', 'https://')
            
            if self.isfiltered(imgUrl):
                self.log.warn('img filtered : %s' % imgUrl)
                img.decompose()
                continue
            
            img['src'] = imgUrl #将更正的地址写回保存
            
            
    #根据一些配置，对图像进行处理，比如缩小，转灰度图，转格式，图像分隔等
    def process_image(self, data):
        if not data:
            return None
        
        opts = self.opts
        try:
            if not opts or not opts.process_images or not opts.process_images_immediately:
                return data
            elif opts.mobi_keep_original_images:
                return mobify_image(data)
            else:
                #如果图被拆分，则返回一个图像列表，否则返回None
                splitedImages = self.SplitLongImage(data)
                if splitedImages:
                    images = []
                    for image in splitedImages:
                        images.append(rescale_image(image, png2jpg=opts.image_png_to_jpg, graying=opts.graying_image, 
                            reduceto=opts.reduce_image_to))
                    return images
                else:
                    return rescale_image(data, png2jpg=opts.image_png_to_jpg,
                                graying=opts.graying_image,
                                reduceto=opts.reduce_image_to)
        except Exception as e:
            self.log.warn('Process image failed (%s), use original image.' % str(e))
            return data
    
    #如果一个图片太长，则将其分隔成多个图片
    def SplitLongImage(self, data):
        if not THRESHOLD_SPLIT_LONG_IMAGE:
            return None
            
        threshold = max(self.opts.dest.screen_size[1], THRESHOLD_SPLIT_LONG_IMAGE)
        
        if not isinstance(data, StringIO):
            data = StringIO(data)
        img = Image.open(data)
        width, height = img.size
        fmt = img.format
        #info = img.info
        
        #高至少是宽的三倍才认为是超长图
        if height < threshold or height < width * 3:
            return None
            
        imagesData = []
        top = 0
        while top < height:
            bottom = top + threshold
            if bottom > height:
                bottom = height
                    
            part = img.crop((0, top, width, bottom))
            part.load()
            partData = StringIO()
            part.save(partData, fmt) #, **info)
            imagesData.append(partData.getvalue())
            
            #分图和分图重叠20个像素，保证一行字符能显示在其中一个分图中
            top = bottom - 20 if bottom < height else bottom
            
        return imagesData
    
    #在文章末尾添加分享链接，如果文章末尾添加了网址的QRCODE，则此函数返回生成的图像(imgName, imgContent)，否则返回None
    def AppendShareLinksToArticle(self, soup, url):
        user = self.user
        if not user or not soup:
            return None
            
        FirstLink = True
        qrimg = None
        qrimgName = ''
        body = soup.html.body
        if user.evernote and user.evernote_mail:
            href = self.MakeShareLink('evernote', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SAVE_TO_EVERNOTE
            body.append(ashare)
            FirstLink = False
        if user.wiz and user.wiz_mail:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('wiz', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SAVE_TO_WIZ
            body.append(ashare)
            FirstLink = False
        if user.pocket:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('pocket', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SAVE_TO_POCKET
            body.append(ashare)
            FirstLink = False
        if user.instapaper:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('instapaper', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SAVE_TO_INSTAPAPER
            body.append(ashare)
            FirstLink = False
        if user.xweibo:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('xweibo', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SHARE_ON_XWEIBO
            body.append(ashare)
            FirstLink = False
        if user.tweibo:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('tweibo', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SHARE_ON_TWEIBO
            body.append(ashare)
            FirstLink = False
        if user.facebook:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('facebook', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SHARE_ON_FACEBOOK
            body.append(ashare)
            FirstLink = False
        if user.twitter:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('twitter', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SHARE_ON_TWITTER
            body.append(ashare)
            FirstLink = False
        if user.tumblr:
            if not FirstLink:
                self.AppendSeperator(soup)
            href = self.MakeShareLink('tumblr', user, url, soup)
            ashare = soup.new_tag('a', href=href)
            ashare.string = SHARE_ON_TUMBLR
            body.append(ashare)
            FirstLink = False
        if user.browser:
            if not FirstLink:
                self.AppendSeperator(soup)
            ashare = soup.new_tag('a', href=url)
            ashare.string = OPEN_IN_BROWSER
            body.append(ashare)
        if user.qrcode:
            import lib.qrcode as qr_code
            if not FirstLink:
                self.AppendSeperator(soup)
            body.append(soup.new_tag('br'))
            qrimgName = 'img%d.jpg' % self.imgindex
            imgshare = soup.new_tag('img', src=qrimgName)
            body.append(imgshare)
            FirstLink = False
            img = qr_code.make(url)
            qrimg = StringIO()
            img.save(qrimg, 'JPEG')
        
        return (qrimgName, qrimg.getvalue()) if qrimg else None
    
    #生成保存内容或分享文章链接的KindleEar调用链接
    def MakeShareLink(self, sharetype, user, url, soup):
        if sharetype in ('evernote', 'wiz'):
            href = "%s/share?act=%s&u=%s&url=" % (DOMAIN, sharetype, user.name)
        elif sharetype == 'pocket':
            href = '%s/share?act=pocket&u=%s&h=%s&t=%s&url=' % (DOMAIN, user.name, (hashlib.md5(user.pocket_acc_token_hash or '').hexdigest()), 
                                                        soup.html.head.title.string)
        elif sharetype == 'instapaper':
            href = '%s/share?act=instapaper&u=%s&n=%s&t=%s&url=' % (DOMAIN, user.name, user.instapaper_username or '', soup.html.head.title.string)
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
            href = SHARE_FUCK_GFW_SRV % urllib.quote((href + url).encode('utf-8'))
        else:
            href += urllib.quote(url.encode('utf-8'))
        return href

    def AppendSeperator(self, soup):
        " 在文章末尾添加'|'分隔符 "
        span = soup.new_tag('span')
        span.string = ' | '
        soup.html.body.append(span)
        
class WebpageBook(BaseFeedBook):
    fulltext_by_readability = False

    # 直接在网页中获取信息
    def Items(self):
        """
        生成器，返回一个元组
        对于HTML：section,url,title,content,brief,thumbnail
        对于图片，mime,url,filename,content,brief,thumbnail
        如果是图片，仅第一个图片的thumbnail返回True，其余为None
        """
        decoder = AutoDecoder(isfeed=False)
        timeout = self.timeout
        for section, url in self.feeds:
            opener = URLOpener(self.host, timeout=timeout, headers=self.extra_header)
            result = opener.open(url)
            status_code, content = result.status_code, result.content
            if status_code != 200 or not content:
                self.log.warn('fetch article failed(%s):%s.' % (URLOpener.CodeMap(status_code), url))
                continue
            
            content = self.AutoDecodeContent(content, decoder, self.page_encoding, opener.realurl, result.headers)
            
            content =  self.preprocess(content)
            soup = BeautifulSoup(content, "lxml")

            head = soup.find('head')
            if not head:
                head = soup.new_tag('head')
                soup.html.insert(0, head)
            if not head.find('title'):
                t = soup.new_tag('title')
                t.string = section
                head.append(t)
                
            try:
                title = soup.html.head.title.string
            except AttributeError:
                title = section
                #self.log.warn('object soup invalid!(%s)'%url)
                #continue

            title = self.processtitle(title)

            if self.keep_only_tags:
                body = soup.new_tag('body')
                try:
                    if isinstance(self.keep_only_tags, dict):
                        keep_only_tags = [self.keep_only_tags]
                    else:
                        keep_only_tags = self.keep_only_tags
                    for spec in keep_only_tags:
                        for tag in soup.find('body').find_all(**spec):
                            body.insert(len(body.contents), tag)
                    soup.find('body').replace_with(body)
                except AttributeError: # soup has no body element
                    pass

            for spec in self.remove_tags_after:
                tag = soup.find(**spec)
                remove_beyond(tag, 'next_sibling')

            for spec in self.remove_tags_before:
                tag = soup.find(**spec)
                remove_beyond(tag, 'previous_sibling')

            remove_tags = self.insta_remove_tags + self.remove_tags
            remove_ids = self.insta_remove_ids + self.remove_ids
            remove_classes = self.insta_remove_classes + self.remove_classes
            remove_attrs = self.insta_remove_attrs + self.remove_attrs
            for tag in soup.find_all(remove_tags):
                tag.decompose()
            for id_ in remove_ids:
                for tag in soup.find_all(attrs={"id":id_}):
                    tag.decompose()
            for cls in remove_classes:
                for tag in soup.find_all(attrs={"class":cls}):
                    tag.decompose()
            for attr in remove_attrs:
                for tag in soup.find_all(attrs={attr:True}):
                    del tag[attr]
            for cmt in soup.find_all(text=lambda text:isinstance(text, Comment)):
                cmt.extract()

            #删除body的所有属性，以便InsertToc使用正则表达式匹配<body>
            body = soup.html.body
            bodyattrs = [attr for attr in body.attrs]
            for attr in bodyattrs:
                del body[attr]

            if self.extra_css:
                sty = soup.new_tag('style', type="text/css")
                sty.string = self.extra_css
                soup.html.head.append(sty)

            has_imgs = False
            thumbnail = None
            if self.keep_image:
                self.soupbeforeimage(soup)
                self.RectifyImageSrcInSoup(soup, url)
                for img in soup.find_all('img'):
                    imgurl = img['src'] if 'src' in img.attrs else None
                    if not imgurl:
                        continue
                        
                    imgresult = opener.open(imgurl)
                    imgcontent = self.process_image(imgresult.content) if imgresult.status_code==200 else None
                    if imgcontent:
                        if isinstance(imgcontent, list): #一个图片分隔为多个图片
                            imgIndex = self.imgindex
                            lastImg = img
                            imgPartUrl = imgurl
                            for idx, imgPartContent in enumerate(imgcontent):
                                fnImg = "img%d_%d.jpg" % (imgIndex, idx)
                                if idx == 0: #第一个分图
                                    img['src'] = fnImg
                                else: #其他部分
                                    imgPartUrl += '_'
                                    imgNew =  soup.new_tag('img', src=fnImg)
                                    lastImg.insert_after(imgNew)
                                    lastImg = imgNew
                                
                                #使用第一个图片做为目录缩略图
                                if not has_imgs:
                                    has_imgs = True
                                    thumbnail = imgPartUrl
                                    yield ('image/jpeg', imgPartUrl, fnImg, imgPartContent, None, True)
                                else:
                                    yield ('image/jpeg', imgPartUrl, fnImg, imgPartContent, None, None)
                        else: #单个图片
                            if len(imgcontent) < self.img_min_size: #rexdf too small image
                                img.decompose()
                                continue

                            imgtype = imghdr.what(None, imgcontent)
                            if imgtype:
                                imgmime = r"image/" + imgtype
                                fnimg = "img%d.%s" % (self.imgindex, 'jpg' if imgtype=='jpeg' else imgtype)
                                img['src'] = fnimg

                                #使用第一个图片做为目录摘要图
                                if not has_imgs:
                                    has_imgs = True
                                    thumbnail = imgurl
                                    yield (imgmime, imgurl, fnimg, imgcontent, None, True)
                                else:
                                    yield (imgmime, imgurl, fnimg, imgcontent, None, None)
                            else:
                                img.decompose()
                    else:
                        self.log.warn('fetch img failed(%s):%s' % (URLOpener.CodeMap(imgresult.status_code), imgurl))
                        img.decompose()

                #去掉图像上面的链接
                if self.user and self.user.remove_hyperlinks in (u'image', u'all', 'image', 'all'):
                    for img in soup.find_all('img'):
                        if img.parent and img.parent.parent and img.parent.name == 'a':
                            img.parent.replace_with(img)
            else:
                for img in soup.find_all('img'):
                    img.decompose()

            self.soupprocessex(soup)

            #如果需要，去掉正文中的超链接(使用斜体下划线标识)，以避免误触
            if self.user and self.user.remove_hyperlinks in (u'text', u'all', 'text', 'all'):
                for a_ in soup.find_all('a'):
                    #a_.unwrap()
                    a_.name = 'i'
                    a_.attrs.clear()
                    #a_.attrs['style'] = 'text-decoration:underline;'
            
            content = unicode(soup)
            
            #提取文章内容的前面一部分做为摘要，[漫画模式不需要摘要]
            brief = u''
            if GENERATE_TOC_DESC and ((not self.user) or self.user.book_mode != 'comic'):
                for h in body.find_all(['h1','h2']): # 去掉h1/h2，避免和标题重复
                    h.decompose()
                for s in body.stripped_strings:
                    brief += unicode(s) + u' '
                    if len(brief) >= TOC_DESC_WORD_LIMIT:
                        brief = brief[:TOC_DESC_WORD_LIMIT]
                        break
            soup = None
            
            content =  self.postprocess(content)
            yield (section, url, title, content, brief, thumbnail)

class BaseUrlBook(BaseFeedBook):
    """ 提供网页URL，而不是RSS订阅地址，
    此类生成的MOBI使用普通书籍格式，而不是期刊杂志格式
    feeds中的地址为网页的URL，section可以为空。
    """
    fulltext_by_readability = True

    def ParseFeedUrls(self):
        """ return list like [(section,title,url,desc),..] """
        return [(sec,sec,url,'') for sec, url in self.feeds]

class BaseComicBook(BaseFeedBook):
    """ 漫画专用，漫画的主要特征是全部为图片，而且图片默认全屏呈现
    由 insert0003 <https://github.com/insert0003> 贡献代码
    如果要处理连载的话，可以使用 ComicUpdateLog 数据库表来记录和更新
    """

    # 子类填充： (https://www.manhuagui.com", "https://m.manhuagui.com")
    accept_domains = tuple()

    title = u""
    description = u""
    language = ""
    feed_encoding = ""
    page_encoding = ""
    mastheadfile = "mh_default.gif"
    coverfile = "cv_bound.jpg"
    feeds = []  # 子类填充此列表[('name', mainurl),...]
    min_image_size = (150, 150)  # 小于这个尺寸的图片会被删除，用于去除广告图片或按钮图片之类的

    # 子类必须实现此函数，返回 [(bookname, chapter_title, imgList, next_chapter_index),..]
    def ParseFeedUrls(self):
        chapters = []  # 用于返回

        username = self.UserName()
        for item in self.feeds:
            bookname, url = item[0], item[1]
            self.log.info(u"Parsing Feed {} for {}".format(url, bookname))

            last_deliver = (
                LastDelivered.all()
                .filter("username = ", username)
                .filter("bookname = ", bookname)
                .get()
            )
            if not last_deliver:
                self.log.info(
                    u"These is no log in db LastDelivered for name: {}, set to 0".format(
                        bookname
                    )
                )
                next_chapter_index = 0
            else:
                next_chapter_index = last_deliver.num

            chapter_list = self.getChapterList(url)
            chapter_length = len(chapter_list)
            if next_chapter_index < chapter_length:
                chapter_title, chapter_url = chapter_list[next_chapter_index]
                self.log.info(u"Add {}: {}".format(chapter_title, chapter_url))
                imgList = self.getImgList(chapter_url)
                if not imgList:
                    self.log.warn(
                        "can not found image list: %s" % chapter_url
                    )
                    break
                next_chapter_index += 1
                chapters.append(
                    (bookname, chapter_title, imgList, chapter_url, next_chapter_index)
                )
            else:
                self.log.info(
                    u"No new chapter for {} ( total {}, pushed {} )".format(
                        bookname, len(chapter_list), next_chapter_index
                    )
                )
        return chapters

    #获取漫画章节列表
    def getChapterList(self, url):
        return []

    #获取漫画图片列表
    def getImgList(self, url):
        return []
    
    #获取漫画图片内容
    def adjustImgContent(self, content):
        return content

    # 生成器，返回一个图片元组，mime,url,filename,content,brief,thumbnail
    def gen_image_items(self, img_list, referer):
        opener = URLOpener(referer, timeout=self.timeout, headers=self.extra_header)
        decoder = AutoDecoder(isfeed=False)
        min_width, min_height = self.min_image_size
        if self.needs_subscription:
            result = self.login(opener, decoder)
        for i, url in enumerate(img_list):
            result = opener.open(url)
            content = result.content
            if not content:
                raise Exception(
                    "Failed to download %s: code %s" % url, result.status_code
                )

            content = self.adjustImgContent(content)

            imgFilenameList = []

            #先判断是否是图片
            imgType = imghdr.what(None, content)
            if imgType:
                content = self.process_image_comic(content)
                if content:
                    if isinstance(content, (list, tuple)): #一个图片分隔为多个图片
                        imgIndex = self.imgindex
                        for idx, imgPartContent in enumerate(content):
                            imgType = imghdr.what(None, imgPartContent)
                            imgMime = r"image/" + imgType
                            fnImg = "img%d_%d.jpg" % (imgIndex, idx)
                            imgPartUrl = url[:-4]+"_%d.jpg"%idx
                            imgFilenameList.append(fnImg)
                            yield (imgMime, imgPartUrl, fnImg, imgPartContent, None, True)
                    else: #单个图片
                        imgType = imghdr.what(None, content)
                        imgMime = r"image/" + imgType
                        fnImg = "img%d.%s" % (self.imgindex, 'jpg' if imgType=='jpeg' else imgType)
                        imgFilenameList.append(fnImg)
                        yield (imgMime, url, fnImg, content, None, None)
            else: #不是图片，有可能是包含图片的网页，抽取里面的图片
                content = self.AutoDecodeContent(content, decoder, self.page_encoding, opener.realurl, result.headers)
                soup = BeautifulSoup(content, 'lxml')
                self.RectifyImageSrcInSoup(soup, opener.realurl)
                
                #有可能一个网页有多个漫画图片，而且还有干扰项(各种按钮/广告等)，所以先全部保存再判断好了
                #列表格式[(url, content),...]
                imgContentList = []
                for img in soup.find_all('img'):
                    imgUrl = img['src'] if 'src' in img.attrs else None
                    if not imgUrl:
                        continue
                        
                    #为了省时间，如果图片属性中有width/height，则也可以先初步判断是不是漫画图片
                    if 'width' in img.attrs:
                        width = img.attrs['width'].replace('"', '').replace("'", '').replace('px', '').strip()
                        try:
                            if int(width) < min_width:
                                continue
                        except:
                            pass
                            
                    if 'height' in img.attrs:
                        height = img.attrs['height'].replace('"', '').replace("'", '').replace('px', '').strip()
                        try:
                            if int(height) < min_height:
                                continue
                        except:
                            pass
                            
                    imgResult = opener.open(imgUrl)
                    if imgResult.status_code == 200 and imgResult.content:
                        imgContentList.append((imgUrl, imgResult.content))
                
                #判断图片里面哪些是真正的漫画图片
                if not imgContentList:
                    continue
                elif len(imgContentList) == 1:
                    imgUrl, imgContent = imgContentList[0]
                    imgType = imghdr.what(None, imgContent)
                    if imgType:
                        imgContent = self.process_image_comic(imgContent)
                        imgType = imghdr.what(None, imgContent)
                        imgMime = r"image/" + imgType
                        fnImg = "img%d.%s" % (self.imgindex, 'jpg' if imgType=='jpeg' else imgType)
                        imgFilenameList.append(fnImg)
                        yield (imgMime, imgUrl, fnImg, imgContent, None, None)
                else: #多个图片，要分析哪些才是漫画
                    isComics = [True for n in range(len(imgContentList))]
                    for idx, imgItem in enumerate(imgContentList):
                        imgUrl, imgContent = imgItem
                        imgInstance = Image.open(StringIO(imgContent))
                        width, height = imgInstance.size
                        #图片太小则排除
                        if width < min_width or height < min_height:
                            isComics[idx] = False
                        elif width > height * 4: #一般横幅广告图片都是横长条，可以剔除
                            isComics[idx] = False
                    
                    #如果所有的图片都被排除了，则使用所有图片里面尺寸最大的
                    if not any(isComics):
                        imgContentList.sort(key=lambda x: len(x[1]), reverse=True)
                        imgContentList = [imgContentList[0]]
                    else:
                        imgContentList = [item for idx, item in enumerate(imgContentList) if isComics[idx]]
                    
                    #列表中的就是漫画图片
                    for imgUrl, imgContent in imgContentList:
                        imgType = imghdr.what(None, imgContent)
                        if imgType:
                            imgContent = self.process_image_comic(imgContent)
                            imgType = imghdr.what(None, imgContent)
                            imgMime = r"image/" + imgType
                            fnImg = "img%d.%s" % (self.imgindex, 'jpg' if imgType=='jpeg' else imgType)
                            imgFilenameList.append(fnImg)
                            yield (imgMime, imgUrl, fnImg, imgContent, None, None)
            
            #每个图片当做一篇文章，否则全屏模式下图片会挤到同一页
            for imgFilename in imgFilenameList:
                tmpHtml = htmlTemplate % (i, imgFilename)
                yield (imgFilename.split(".")[0], url, str(i), tmpHtml, "", None)

    def Items(self):
        # todo: update last-delivered after send to kindle for built-in
        for (
            bookname,
            chapter_title,
            img_list,
            chapter_url,
            next_chapter_index,
        ) in self.ParseFeedUrls():
            for item in self.gen_image_items(img_list, chapter_url):
                yield item
            self.UpdateLastDelivered(bookname, chapter_title, next_chapter_index)

    # 更新已经推送的序号和标题到数据库
    def UpdateLastDelivered(self, bookname, chapter_title, num):
        userName = self.UserName()
        dbItem = (
            LastDelivered.all()
            .filter("username = ", userName)
            .filter("bookname = ", bookname)
            .get()
        )
        self.last_delivered_volume = chapter_title
        now = datetime.datetime.utcnow() + datetime.timedelta(
            hours=TIMEZONE
        )
        if dbItem:
            dbItem.num = num
            dbItem.record = self.last_delivered_volume
            dbItem.datetime = now
        else:
            dbItem = LastDelivered(
                username=userName,
                bookname=bookname,
                num=num,
                record=self.last_delivered_volume,
                datetime=now,
            )
        dbItem.put()

    #预处理漫画图片
    def process_image_comic(self, data):
        if not data:
            return None
        
        opts = self.opts
        try:
            if not opts or not opts.process_images or not opts.process_images_immediately:
                return data
            else:
                #如果图被拆分，则返回一个图像列表，否则返回None
                splitedImages = self.SplitWideImage(data)
                if splitedImages:
                    images = []
                    for image in splitedImages:
                        images.append(rescale_image(image, png2jpg=opts.image_png_to_jpg, graying=opts.graying_image,
                            reduceto=opts.reduce_image_to))
                    return images
                else:
                    return rescale_image(
                        data,
                        png2jpg=opts.image_png_to_jpg,
                        graying=opts.graying_image,
                        reduceto=opts.reduce_image_to,
                    )
        except:
            self.log.exception("Process comic image failed.")
            return data

        #如果一个图片为横屏，则将其分隔成2个图片
    def SplitWideImage(self, data):
        if not isinstance(data, StringIO):
            data = StringIO(data)

        img = Image.open(data)
        width, height = img.size
        fmt = img.format
        #宽>高才认为是横屏
        if height > width:
            return None

        imagesData = []
        part2 = img.crop((width/2-10, 0, width, height))
        part2.load()
        part2Data = StringIO()
        part2.save(part2Data, fmt)
        imagesData.append(part2Data.getvalue())

        part1 = img.crop((0, 0, width/2+10, height))
        part1.load()
        part1Data = StringIO()
        part1.save(part1Data, fmt)
        imagesData.append(part1Data.getvalue())

        return imagesData

#几个小工具函数
def remove_beyond(tag, next):
    while tag is not None and getattr(tag, 'name', None) != 'body':
        after = getattr(tag, next)
        while after is not None:
            after.extract()
            after = getattr(tag, next)
        tag = tag.parent

#获取BeautifulSoup中的一个tag下面的所有字符串
def string_of_tag(tag, normalize_whitespace=False):
    if not tag:
        return ''
    if isinstance(tag, basestring):
        return tag
    strings = []
    for item in tag.contents:
        if isinstance(item, (NavigableString, CData)):
            strings.append(item.string)
        elif isinstance(item, Tag):
            res = string_of_tag(item)
            if res:
                strings.append(res)
    ans = u''.join(strings)
    if normalize_whitespace:
        ans = re.sub(r'\s+', ' ', ans)
    return ans

#将抓取的网页发到自己邮箱进行调试
def debug_mail(content, name='page.html'):
    from google.appengine.api import mail
    mail.send_mail(SRC_EMAIL, SRC_EMAIL, "KindleEar Debug", "KindlerEar",
    attachments=[(name, content),])

#抓取网页，发送到自己邮箱，用于调试目的
def debug_fetch(url, name='page.html'):
    if not name:
        name = 'page.html'
    opener = URLOpener()
    result = opener.open(url)
    if result.status_code == 200 and result.content:
        debug_mail(result.content, name)

#本地调试使用，在本地创建一个FTP服务器后，将调试文件通过FTP保存到本地
#因为只是调试使用，所以就没有那么复杂的处理了，要提前保证目标目录存在
def debug_save_ftp(content, name='page.html', root='', server='127.0.0.1', port=21, username='', password=''):
    import ftplib
    ftp = ftplib.FTP()
    ftp.set_debuglevel(0)  #打开调试级别2，显示详细信息; 0为关闭调试信息
    ftp.connect(server, port, 60)  #FTP主机 端口 超时时间
    ftp.login(username, password)  #登录，如果匿名登录则用空串代替即可
    
    if root:
        rootList = root.replace('\\', '/').split('/')
        for dirName in rootList:
            if dirName:
                ftp.cwd(dirName)
    
    #为简单起见，就不删除FTP服务器的同名文件，取而代之的就是将当前时间附加到文件名后
    name = name.replace('.', datetime.datetime.now().strftime('_%H_%M_%S.'))
    ftp.storbinary('STOR %s' % name, StringIO(content))
    ftp.set_debuglevel(0)
    ftp.quit()
