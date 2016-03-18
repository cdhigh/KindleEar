#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
KindleEar电子书基类，每本投递到kindle的书籍抽象为这里的一个类。
可以继承BaseFeedBook类而实现自己的定制书籍。
"""
import os, re, urllib, urlparse, imghdr, datetime
from urllib2 import *

from bs4 import BeautifulSoup, Comment, NavigableString, CData, Tag
from lib import feedparser
from lib.readability import readability
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder

from calibre.utils.img import rescale_image, mobify_image

from config import *

class BaseFeedBook:
    """ base class of Book """
    title                 = ''
    __author__            = ''
    description           = ''
    max_articles_per_feed = 30
    #下载多长时间之内的文章，小于等于365则单位为天，大于365则单位为秒，0为不限制
    oldest_article        = 7
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
    #一旦设置此属性，则网页上设置的星期推送对此书无效
    #'Monday','Tuesday',...,'Sunday'，大小写敏感
    #比如设置为['Friday']
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
    # 比如：keep_only_tags = [dict(name='div', attrs={'id':'article'}),]
    # 这个优先级最高，先处理了这个标签再处理其他标签。
    keep_only_tags = []

    # 顾名思义，删除特定标签前/后的所有内容，格式和keep_only_tags相同
    remove_tags_after = []
    remove_tags_before = []

    # 内置的几个必须删除的标签，不建议子类修改
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
    remove_tags = [] # 完全清理此标签
    remove_ids = [] # 清除标签的id属性为列表中内容的标签
    remove_classes = [] # 清除标签的class属性为列表中内容的标签
    remove_attrs = [] # 清除所有标签的特定属性，不清除标签内容

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
    def __init__(self, log=None, imgindex=0):
        self.log = default_log if log is None else log
        self.compiled_urlfilters = []
        self._imgindex = imgindex

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

    @classmethod
    def urljoin(self, base, url):
        #urlparse.urljoin()处理有..的链接有点问题，此函数修正此问题。
        join = urlparse.urljoin(base,url)
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
            opener = URLOpener(self.host, timeout=timeout)
            result = opener.open(url)
            if result.status_code == 200 and result.content:
                #debug_mail(result.content, 'feed.xml')
                
                if self.feed_encoding:
                    try:
                        content = result.content.decode(self.feed_encoding)
                    except UnicodeDecodeError:
                        content = AutoDecoder(True).decode(result.content,opener.realurl,result.headers)
                else:
                    content = AutoDecoder(True).decode(result.content,opener.realurl,result.headers)
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
                            self.log.info("Skip old article(%s): %s" % (updated.strftime('%Y-%m-%d %H:%M:%S'),e.link))
                            continue
                            
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
                                self.log.warn('fulltext feed item no has desc,link to webpage for article.(%s)'%e.title)
                    urls.append((section, e.title, urlfeed, desc))
                    urladded.add(urlfeed)
            else:
                self.log.warn('fetch rss failed(%s):%s'%(URLOpener.CodeMap(result.status_code), url))
                
        return urls

    def Items(self, opts=None, user=None):
        """
        生成器，返回一个元组
        对于HTML：section,url,title,content,brief,thumbnail
        对于图片，mime,url,filename,content,brief,thumbnail
        """
        urls = self.ParseFeedUrls()
        readability = self.readability if self.fulltext_by_readability else self.readability_by_soup
        prevsection = ''
        opener = URLOpener(self.host, timeout=self.timeout)
        decoder = AutoDecoder(False)
        for section, ftitle, url, desc in urls:
            if not desc: #非全文RSS
                if section != prevsection or prevsection == '':
                    decoder.encoding = '' #每个小节都重新检测编码
                    prevsection = section
                    opener = URLOpener(self.host, timeout=self.timeout)
                    if self.needs_subscription:
                        self.login(opener, decoder)
        
                article = self.fetcharticle(url, opener, decoder)
                if not article:
                    continue
            else:
                article = self.FragToXhtml(desc, ftitle)
            
            #如果是图片，title则是mime
            for title, imgurl, imgfn, content, brief, thumbnail in readability(article,url,opts,user):
                if title.startswith(r'image/'): #图片
                    yield (title, imgurl, imgfn, content, brief, thumbnail)
                else:
                    if user and user.use_title_in_feed:
                        title = ftitle
                    elif not title:
                        title = ftitle
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
            #self.log.debug('field_dic:%s' % repr(fields_dic))
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
                        if 'login' in identify or 'login' in action:
                            form = f
                            break
                        
                if not form: #如果无法判断，则假定第二个为登陆表单
                    form = forms[1]
        return form
        
    def fetch(self, url, opener, decoder):
        """链接网络，下载网页并解码"""
        result = opener.open(url)
        status_code, content = result.status_code, result.content
        if status_code not in (200,206) or not content:
            self.log.warn('fetch page failed(%s):%s.' % (URLOpener.CodeMap(status_code), url))
            return None
        
        #debug_mail(content)
        
        if self.page_encoding:
            try:
                return content.decode(self.page_encoding)
            except UnicodeDecodeError:
                return decoder.decode(content,opener.realurl,result.headers)
        else:
            return decoder.decode(content,opener.realurl,result.headers)

    def readability(self, article, url, opts=None, user=None):
        """ 使用readability-lxml处理全文信息
        因为图片文件占内存，为了节省内存，这个函数也做为生成器
        """
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
                tmphtml = '<html><head><title>Picture</title></head><body><img src="%s" /></body></html>' % fnimg
                yield ('Picture', None, None, tmphtml, '', None)
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
        if len(body.contents) == 0:
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
        for id in self.remove_ids:
            for tag in soup.find_all(attrs={"id":id}):
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
            opener = URLOpener(self.host, timeout=self.timeout)
            for img in soup.find_all('img'):
                #现在使用延迟加载图片技术的网站越来越多了，这里处理一下
                #注意：如果data-src之类的属性保存的不是真实url就没辙了
                imgurl = img['src'] if 'src' in img.attrs else ''
                if not imgurl:
                    for attr in img.attrs:
                        if attr != 'src' and 'src' in attr: #很多网站使用data-src
                            imgurl = img[attr]
                            break
                if not imgurl:
                    img.decompose()
                    continue
                if not imgurl.startswith('data:'):
                    if not imgurl.startswith('http'):
                        imgurl = self.urljoin(url, imgurl)
                    if self.fetch_img_via_ssl and url.startswith('https://'):
                        imgurl = imgurl.replace('http://', 'https://')
                    if self.isfiltered(imgurl):
                        self.log.warn('img filtered : %s' % imgurl)
                        img.decompose()
                        continue
                imgresult = opener.open(imgurl)
                imgcontent = self.process_image(imgresult.content,opts) if imgresult.status_code==200 else None
                if imgcontent:
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
            for img in soup.find_all('img'):
                if img.parent and img.parent.parent and \
                    img.parent.name == 'a':
                    img.parent.replace_with(img)
        else:
            for img in soup.find_all('img'):
                img.decompose()
        
        #将HTML5标签转换为div
        for x in soup.find_all(['article', 'aside', 'header', 'footer', 'nav',
            'figcaption', 'figure', 'section', 'time']):
            x.name = 'div'
        
        self.soupprocessex(soup)

        #插入分享链接
        if user:
            self.AppendShareLinksToArticle(soup, user, url)

        content = unicode(soup)

        #提取文章内容的前面一部分做为摘要
        brief = u''
        if GENERATE_TOC_DESC:
            for h in body.find_all(['h1','h2']): # 去掉h1/h2，避免和标题重复
                h.decompose()
            for s in body.stripped_strings:
                brief += unicode(s) + u' '
                if len(brief) >= TOC_DESC_WORD_LIMIT:
                    brief = brief[:TOC_DESC_WORD_LIMIT]
                    break
        soup = None

        yield (title, None, None, content, brief, thumbnail)

    def readability_by_soup(self, article, url, opts=None, user=None):
        """ 使用BeautifulSoup手动解析网页，提取正文内容
        因为图片文件占内存，为了节省内存，这个函数也做为生成器
        """
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
        for id in remove_ids:
            for tag in soup.find_all(attrs={"id":id}):
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
            opener = URLOpener(self.host, timeout=self.timeout)
            for img in soup.find_all('img'):
                #现在使用延迟加载图片技术的网站越来越多了，这里处理一下
                #注意：如果data-src之类的属性保存的不是真实url就没辙了
                imgurl = img['src'] if 'src' in img.attrs else ''
                if not imgurl:
                    for attr in img.attrs:
                        if attr != 'src' and 'src' in attr: #很多网站使用data-src
                            imgurl = img[attr]
                            break
                if not imgurl:
                    img.decompose()
                    continue
                if not imgurl.startswith('data:'):
                    if not imgurl.startswith('http'):
                        imgurl = self.urljoin(url, imgurl)
                    if self.fetch_img_via_ssl and url.startswith('https://'):
                        imgurl = imgurl.replace('http://', 'https://')
                    if self.isfiltered(imgurl):
                        self.log.warn('img filtered:%s' % imgurl)
                        img.decompose()
                        continue
                imgresult = opener.open(imgurl)
                imgcontent = self.process_image(imgresult.content,opts) if imgresult.status_code==200 else None
                if imgcontent:
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
            for img in soup.find_all('img'):
                if img.parent and img.parent.parent and \
                    img.parent.name == 'a':
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

        #插入分享链接
        if user:
            self.AppendShareLinksToArticle(soup, user, url)

        content = unicode(soup)

        #提取文章内容的前面一部分做为摘要
        brief = u''
        if GENERATE_TOC_DESC:
            for h in body.find_all(['h1','h2']): # 去掉h1/h2，避免和标题重复
                h.decompose()
            for s in body.stripped_strings:
                brief += unicode(s) + u' '
                if len(brief) >= TOC_DESC_WORD_LIMIT:
                    brief = brief[:TOC_DESC_WORD_LIMIT]
                    break
        soup = None

        yield (title, None, None, content, brief, thumbnail)

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

    def AppendShareLinksToArticle(self, soup, user, url):
        #在文章末尾添加分享链接
        if not user or not soup:
            return
        FirstLink = True
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

    def MakeShareLink(self, sharetype, user, url, soup):
        " 生成保存内容或分享文章链接的KindleEar调用链接 "
        if sharetype in ('evernote','wiz'):
            href = "%s/share?act=%s&u=%s&url=" % (DOMAIN, sharetype, user.name)
        elif sharetype == 'pocket':
            href = '%s/share?act=pocket&u=%s&h=%s&t=%s&url=' % (DOMAIN, user.name, (user.pocket_acc_token_hash or ''), soup.html.head.title.string)
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
    def Items(self, opts=None, user=None):
        """
        生成器，返回一个元组
        对于HTML：section,url,title,content,brief,thumbnail
        对于图片，mime,url,filename,content,brief,thumbnail
        如果是图片，仅第一个图片的thumbnail返回True，其余为None
        """
        decoder = AutoDecoder(False)
        timeout = self.timeout
        for section, url in self.feeds:
            opener = URLOpener(self.host, timeout=timeout)
            result = opener.open(url)
            status_code, content = result.status_code, result.content
            if status_code != 200 or not content:
                self.log.warn('fetch article failed(%s):%s.' % (URLOpener.CodeMap(status_code), url))
                continue

            if self.page_encoding:
                try:
                    content = content.decode(self.page_encoding)
                except UnicodeDecodeError:
                    content = decoder.decode(content,opener.realurl,result.headers)
            else:
                content = decoder.decode(content,opener.realurl,result.headers)

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
            for id in remove_ids:
                for tag in soup.find_all(attrs={"id":id}):
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
                for img in soup.find_all('img'):
                    #现在使用延迟加载图片技术的网站越来越多了，这里处理一下
                    #注意：如果data-src之类的属性保存的不是真实url就没辙了
                    imgurl = img['src'] if 'src' in img.attrs else ''
                    if not imgurl:
                        for attr in img.attrs:
                            if attr != 'src' and 'src' in attr: #很多网站使用data-src
                                imgurl = img[attr]
                                break
                    if not imgurl:
                        img.decompose()
                        continue
                    if not imgurl.startswith('data:'):
                        if not imgurl.startswith('http'):
                            imgurl = self.urljoin(url, imgurl)
                        if self.fetch_img_via_ssl and url.startswith('https://'):
                            imgurl = imgurl.replace('http://', 'https://')
                        if self.isfiltered(imgurl):
                            self.log.warn('img filtered:%s' % imgurl)
                            img.decompose()
                            continue
                    imgresult = opener.open(imgurl)
                    imgcontent = self.process_image(imgresult.content,opts) if imgresult.status_code==200 else None
                    if imgcontent:
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
                for img in soup.find_all('img'):
                    if img.parent and img.parent.parent and \
                        img.parent.name == 'a':
                        img.parent.replace_with(img)

            else:
                for img in soup.find_all('img'):
                    img.decompose()

            self.soupprocessex(soup)
            content = unicode(soup)

            #提取文章内容的前面一部分做为摘要
            brief = u''
            if GENERATE_TOC_DESC:
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


#几个小工具函数
def remove_beyond(tag, next):
    while tag is not None and getattr(tag, 'name', None) != 'body':
        after = getattr(tag, next)
        while after is not None:
            after.extract()
            after = getattr(tag, next)
        tag = tag.parent

def string_of_tag(tag, normalize_whitespace=False):
    """ 获取BeautifulSoup中的一个tag下面的所有字符串 """
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

def debug_mail(content, name='page.html'):
    "将抓取的网页发到自己邮箱进行调试"
    from google.appengine.api import mail
    mail.send_mail(SRC_EMAIL, SRC_EMAIL, "KindleEar Debug", "KindlerEar",
    attachments=[(name, content),])
    