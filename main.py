#!/usr/bin/env python
# -*- coding:utf-8 -*-

__Version__ = "1.6.8"
__Author__ = "Arroz"

import os, datetime, logging, __builtin__, hashlib
from collections import OrderedDict, defaultdict
import gettext

# for debug
IsRunInLocal = (os.environ.get('SERVER_SOFTWARE', '').startswith('Development'))
log = logging.getLogger()
__builtin__.__dict__['default_log'] = log
__builtin__.__dict__['IsRunInLocal'] = IsRunInLocal

supported_languages = ['en','zh-cn','tr-tr'] #不支持的语种则使用第一个语言
#gettext.install('lang', 'i18n', unicode=True) #for calibre startup

import web
import jinja2
from google.appengine.api import mail
from google.appengine.ext import db
from google.appengine.api import taskqueue
from google.appengine.api import memcache
from google.appengine.runtime.apiproxy_errors import OverQuotaError

from config import *

from lib.makeoeb import *
from lib.memcachestore import MemcacheStore
from books import BookClasses, BookClass
from books.base import BaseFeedBook, UrlEncoding

#reload(sys)
#sys.setdefaultencoding('utf-8')

log.setLevel(logging.INFO if IsRunInLocal else logging.WARN)

def local_time(fmt="%Y-%m-%d %H:%M", tz=TIMEZONE):
    return (datetime.datetime.utcnow()+datetime.timedelta(hours=tz)).strftime(fmt)

def set_lang(lang):
    """ 设置网页显示语言 """
    tr = gettext.translation('lang', 'i18n', languages=[lang])
    tr.install(True)
    jjenv.install_gettext_translations(tr)

#--------------db models----------------
class Book(db.Model):
    title = db.StringProperty(required=True)
    description = db.StringProperty()
    users = db.StringListProperty()
    builtin = db.BooleanProperty() # 内置书籍不可修改
    #====自定义书籍
    language = db.StringProperty()
    mastheadfile = db.StringProperty() # GIF 600*60
    coverfile = db.StringProperty()
    keep_image = db.BooleanProperty()
    oldest_article = db.IntegerProperty()
    
    #这三个属性只有自定义RSS才有意义
    @property
    def feeds(self):
        return Feed.all().filter('book = ', self.key())
    @property
    def feedscount(self):
        mkey = '%d.feedscount'%self.key().id()
        mfc = memcache.get(mkey)
        if mfc is not None:
            return mfc
        else:
            fc = self.feeds.count()
            memcache.add(mkey, fc, 86400)
            return fc
    @property
    def owner(self):
        return KeUser.all().filter('ownfeeds = ', self.key())
    
class KeUser(db.Model): # kindleEar User
    name = db.StringProperty(required=True)
    passwd = db.StringProperty(required=True)
    kindle_email = db.StringProperty()
    enable_send = db.BooleanProperty()
    send_days = db.StringListProperty()
    send_time = db.IntegerProperty()
    timezone = db.IntegerProperty()
    book_type = db.StringProperty()
    expires = db.DateTimeProperty()
    ownfeeds = db.ReferenceProperty(Book) # 每个用户都有自己的自定义RSS
    titlefmt = db.StringProperty() #在元数据标题中添加日期的格式
    
class Feed(db.Model):
    book = db.ReferenceProperty(Book)
    title = db.StringProperty()
    url = db.StringProperty()
    isfulltext = db.BooleanProperty()
    
class DeliverLog(db.Model):
    username = db.StringProperty()
    to = db.StringProperty()
    size = db.IntegerProperty()
    time = db.StringProperty()
    datetime = db.DateTimeProperty()
    book = db.StringProperty()
    status = db.StringProperty()
    
class UrlFilter(db.Model):
    url = db.StringProperty()

class WhiteList(db.Model):
    mail = db.StringProperty()
    
#def StoreBookToDb():
for book in BookClasses():  #添加内置书籍
    if memcache.get(book.title): #使用memcache加速
        continue
    b = Book.all().filter("title = ", book.title).get()
    if not b:
        b = Book(title=book.title,description=book.description,builtin=True)
        b.put()
        memcache.add(book.title, book.description, 86400)

#StoreBookToDb()

class BaseHandler:
    " URL请求处理类的基类，实现一些共同的工具函数 "
    def __init__(self):
        if not session.get('lang'):
            session.lang = self.browerlang()
        set_lang(session.lang)
        
    @classmethod
    def logined(self):
        return True if session.get('login') == 1 else False
    
    @classmethod
    def login_required(self, username=None):
        if (session.get('login') != 1) or (username and username != session.get('username')):
            raise web.seeother(r'/')
    
    @classmethod
    def getcurrentuser(self):
        self.login_required()
        u = KeUser.all().filter("name = ", session.username).get()
        if not u:
            raise web.seeother(r'/')
        return u
        
    def browerlang(self):
        lang = web.ctx.env.get('HTTP_ACCEPT_LANGUAGE', "en")
        #分析浏览器支持那些语种，为了效率考虑就不用全功能的分析语种和排序了
        #此字符串类似：zh-cn,en;q=0.8,ko;q=0.5,zh-tw;q=0.3
        langs = lang.lower().replace(';',',').replace('_', '-').split(',')
        langs = [c.strip() for c in langs if '=' not in c]
        baselangs = {c.split('-')[0] for c in langs if '-' in c}
        langs.extend(baselangs)
        
        for c in langs: #浏览器直接支持的语种
            if c in supported_languages:
                return c
        for c in langs: #同一语种的其他可选语言
            for sl in supported_languages:
                if sl.startswith(c):
                    return sl
        return supported_languages[0]
        
    @classmethod
    def deliverlog(self, name, to, book, size, status='ok', tz=TIMEZONE):
        try:
            dl = DeliverLog(username=name, to=to, size=size,
               time=local_time(tz=tz), datetime=datetime.datetime.utcnow(),
               book=book, status=status)
            dl.put()
        except Exception as e:
            default_log.warn('DeliverLog failed to save:%s',str(e))
    
    @classmethod
    def SendToKindle(self, name, to, title, booktype, attachment, tz=TIMEZONE, filewithtime=True):
        if PINYIN_FILENAME: # 将中文文件名转换为拼音
            from calibre.ebooks.unihandecode.unidecoder import Unidecoder
            decoder = Unidecoder()
            basename = decoder.decode(title)
        else:
            basename = title
        
        lctime = local_time('%Y-%m-%d_%H-%M',tz)
        if filewithtime:
            filename = "%s(%s).%s"%(basename,lctime,booktype)
        else:
            filename = "%s.%s"%(basename,booktype)
        try:
            mail.send_mail(SRC_EMAIL, to, "KindleEar %s" % lctime, "Deliver from KindlerEar",
                attachments=[(filename, attachment),])
        except OverQuotaError as e:
            default_log.warn('overquota when sendmail to %s:%s' % (to, str(e)))
            self.deliverlog(name, to, title, len(attachment), tz=tz, status='over quota')
        except Exception as e:
            default_log.warn('sendmail to %s failed:%s' % (to, str(e)))
            self.deliverlog(name, to, title, len(attachment), tz=tz, status='send failed')
        else:
            self.deliverlog(name, to, title, len(attachment), tz=tz)
    
    def render(self, templatefile, title='KindleEar', **kwargs):
        kwargs.setdefault('nickname', session.get('username'))
        kwargs.setdefault('lang', session.get('lang', 'en'))
        kwargs.setdefault('version', __Version__)
        return jjenv.get_template(templatefile).render(title=title, **kwargs)
        
class Home(BaseHandler):
    def GET(self):
        return self.render('home.html',"Home")
        
class Setting(BaseHandler):
    def GET(self, tips=None):
        user = self.getcurrentuser()
        return self.render('setting.html',"Setting",
            current='setting',user=user,mail_sender=SRC_EMAIL,tips=tips)
        
    def POST(self):
        user = self.getcurrentuser()
        kemail = web.input().get('kindleemail')
        mytitle = web.input().get("rt")
        if not kemail:
            tips = _("Kindle E-mail is requied!")
        elif not mytitle:
            tips = _("Title is requied!")
        else:
            user.kindle_email = kemail
            user.timezone = int(web.input().get('timezone', TIMEZONE))
            user.send_time = int(web.input().get('sendtime'))
            user.enable_send = bool(web.input().get('enablesend'))
            user.book_type = web.input().get('booktype')
            user.titlefmt = web.input().get('titlefmt')
            alldays = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
            user.send_days = [day for day in alldays if web.input().get(day)]
            user.put()
            
            myfeeds = user.ownfeeds
            myfeeds.language = web.input().get("lng")
            myfeeds.title = mytitle
            myfeeds.keep_image = bool(web.input().get("keepimage"))
            myfeeds.oldest_article = int(web.input().get('oldest', 7))
            myfeeds.users = [user.name] if web.input().get("enablerss") else []
            myfeeds.put()
            tips = _("Settings Saved!")
        
        return self.GET(tips)

class AdvSetting(BaseHandler):
    def GET(self):
        user = self.getcurrentuser()
        return self.render('advsetting.html',"Advanced Setting",current='advsetting',
            user=user,urlfilters=UrlFilter.all(),whitelists=WhiteList.all())
        
    def POST(self):
        user = self.getcurrentuser()
        url = web.input().get('url')
        if url:
            UrlFilter(url=url).put()
        wlist = web.input().get('wlist')
        if wlist:
            WhiteList(mail=wlist).put()
        raise web.seeother('')
        
class AdvDel(BaseHandler):
    def GET(self):
        user = self.getcurrentuser()
        delurlid = web.input().get('delurlid')
        delwlist = web.input().get('delwlist')
        if delurlid and delurlid.isdigit():
            flt = UrlFilter.get_by_id(int(delurlid))
            if flt:
                flt.delete()
        if delwlist and delwlist.isdigit():
            wlist = WhiteList.get_by_id(int(delwlist))
            if wlist:
                wlist.delete()
        raise web.seeother('/advsetting')
        
class Admin(BaseHandler):
    # 账户管理页面
    def GET(self):
        user = self.getcurrentuser()
        users = KeUser.all() if user.name == 'admin' else None
        return self.render('admin.html',"Admin",
            current='admin', user=user, users=users)
        
    def POST(self):
        u,up1,up2 = web.input().get('u'),web.input().get('up1'),web.input().get('up2')
        op,p1,p2 = web.input().get('op'), web.input().get('p1'), web.input().get('p2')
        user = self.getcurrentuser()
        users = KeUser.all() if user.name == 'admin' else None
        if op is not None and p1 is not None and p2 is not None: #修改密码
            try:
                pwd = hashlib.md5(op).hexdigest()
                newpwd = hashlib.md5(p1).hexdigest()
            except:
                tips = _("The password includes non-ascii chars!")
            else:
                if user.passwd != pwd:
                    tips = _("Old password is wrong!")
                elif p1 != p2:
                    tips = _("The two new passwords are dismatch!")
                else:
                    tips = _("Change password success!")
                    user.passwd = newpwd
                    user.put()
            return self.render('admin.html',"Admin",
                current='admin', user=user, users=users,chpwdtips=tips)
        elif u is not None and up1 is not None and up2 is not None: #添加账户
            if user.name != 'admin':
                raise web.seeother(r'/')
            elif not u:
                tips = _("Username is empty!")
            elif up1 != up2:
                tips = _("The two new passwords are dismatch!")
            elif KeUser.all().filter("name = ", u).get():
                tips = _("Already exist the username!")
            else:
                try:
                    pwd = hashlib.md5(up1).hexdigest()
                except:
                    tips = _("The password includes non-ascii chars!")
                else:
                    myfeeds = Book(title=MY_FEEDS_TITLE,description=MY_FEEDS_DESC,
                        builtin=False,keep_image=True,oldest_article=7)
                    myfeeds.put()
                    au = KeUser(name=u,passwd=pwd,kindle_email='',enable_send=False,
                        send_time=7,timezone=TIMEZONE,book_type="mobi",ownfeeds=myfeeds)
                    au.expires = datetime.datetime.utcnow()+datetime.timedelta(days=180)
                    au.put()
                    users = KeUser.all() if user.name == 'admin' else None
                    tips = _("Add a account success!")
            return self.render('admin.html',"Admin",
                current='admin', user=user, users=users,actips=tips)
        else:
            return self.GET()
       
class Login(BaseHandler):
    def GET(self):
        # 第一次登陆时如果没有管理员帐号，
        # 则增加一个管理员帐号admin，密码admin，后续可以修改密码
        tips = ''
        u = KeUser.all().filter("name = ", 'admin').get()
        if not u:
            myfeeds = Book(title=MY_FEEDS_TITLE,description=MY_FEEDS_DESC,
                    builtin=False,keep_image=True,oldest_article=7)
            myfeeds.put()
            au = KeUser(name='admin',passwd=hashlib.md5('admin').hexdigest(),
                kindle_email='',enable_send=False,send_time=8,timezone=TIMEZONE,
                book_type="mobi",expires=None,ownfeeds=myfeeds)
            au.put()
            tips = _("Please use admin/admin to login at first time.")
        else:
            tips = _("Please input username and password.")
        
        if session.get('login') == 1:
            web.seeother(r'/')
        else:
            return self.render('login.html',"Login",tips=tips)
        
    def POST(self):
        name, passwd = web.input().get('u'), web.input().get('p')
        if name.strip() == '':
            tips = _("Username is empty!")
            return self.render('login.html',"Login",nickname='',tips=tips)
        elif len(name) > 25:
            tips = _("The len of username reached the limit of 25 chars!")
            return self.render('login.html',"Login",nickname='',tips=tips,username=name)
        elif '<' in name or '>' in name or '&' in name:
            tips = _("The username includes unsafe chars!")
            return self.render('login.html',"Login",nickname='',tips=tips)
        try:
            pwdhash = hashlib.md5(passwd).hexdigest()
        except:
            u = None
        else:
            u = KeUser.all().filter("name = ", name).filter("passwd = ", pwdhash).get()
        if u:
            session.login = 1
            session.username = name
            if u.expires: #用户登陆后自动续期
                u.expires = datetime.datetime.utcnow()+datetime.timedelta(days=180)
                u.put()
            raise web.seeother(r'/')
        else:
            tips = _("The username not exist or password is wrong!")
            session.login = 0
            session.username = ''
            session.kill()
            return self.render('login.html',"Login",nickname='',tips=tips,username=name)
            
class Logout(BaseHandler):
    def GET(self):
        session.login = 0
        session.username = ''
        session.lang = ''
        session.kill()
        raise web.seeother(r'/')

class AdminMgrPwd(BaseHandler):
    # 管理员修改其他账户的密码
    def GET(self, name):
        self.login_required('admin')
        tips = _("Please input new password to confirm!")
        return self.render('adminmgrpwd.html', "Change password",
            tips=tips,username=name)
        
    def POST(self, _n=None):
        self.login_required('admin')
        name, p1, p2 = web.input().get('u'),web.input().get('p1'),web.input().get('p2')
        if name:
            u = KeUser.all().filter("name = ", name).get()
            if not u:
                tips = _("The username '%s' not exist!") % name
            elif p1 != p2:
                tips = _("The two new passwords are dismatch!")
            else:
                try:
                    pwd = hashlib.md5(p1).hexdigest()
                except:
                    tips = _("The password includes non-ascii chars!")
                else:
                    u.passwd = pwd
                    u.put()
                    tips = _("Change password success!")
        else:
            tips = _("Username is empty!")
        
        return self.render('adminmgrpwd.html', "Change password",
            tips=tips, username=name)
        
class DelAccount(BaseHandler):
    def GET(self, name):
        self.login_required()
        if session.username == 'admin' or (name and name == session.username):
            tips = _("Please confirm to delete the account!")
            return self.render('delaccount.html', "Delete account",
                tips=tips,username=name)
        else:
            raise web.seeother(r'/')
    
    def POST(self, _n=None):
        self.login_required()
        name = web.input().get('u')
        if name and (session.username == 'admin' or session.username == name):
            u = KeUser.all().filter("name = ", name).get()
            if not u:
                tips = _("The username '%s' not exist!") % name
            else:
                if u.ownfeeds:
                    for feed in u.ownfeeds.feeds:
                        feed.delete()
                    u.ownfeeds.delete()
                u.delete()
                
                # 删掉订阅记录
                for book in Book.all():
                    if book.users and name in book.users:
                        book.users.remove(name)
                        book.put()
                
                if session.username == name:
                    raise web.seeother('/logout')
                else:
                    raise web.seeother('/admin')
        else:
            tips = _("The username is empty or you dont have right to delete it!")
        return self.render('delaccount.html', "Delete account",
                tips=tips, username=name)

class MySubscription(BaseHandler):
    # 管理我的订阅和杂志列表
    def GET(self, tips=None):
        user = self.getcurrentuser()
        myfeeds = user.ownfeeds.feeds if user.ownfeeds else None
        return self.render('my.html', "My subscription",current='my',
            books=Book.all().filter("builtin = ",True),myfeeds=myfeeds,tips=tips)
    
    def POST(self): # 添加自定义RSS
        user = self.getcurrentuser()
        title = web.input().get('t')
        url = web.input().get('url')
        isfulltext = bool(web.input().get('fulltext'))
        if not title or not url:
            return self.GET(_("Title or url is empty!"))
        
        if not url.lower().startswith('http'): #http and https
            url = 'http://' + url
        assert user.ownfeeds
        Feed(title=title,url=url,book=user.ownfeeds,isfulltext=isfulltext).put()
        memcache.delete('%d.feedscount'%user.ownfeeds.key().id())
        raise web.seeother('/my')
        
class Subscribe(BaseHandler):
    def GET(self, id):
        self.login_required()
        if not id:
            return "the id is empty!<br />"
        try:
            id = int(id)
        except:
            return "the id is invalid!<br />"
        
        bk = Book.get_by_id(id)
        if not bk:
            return "the book(%d) not exist!<br />" % id
        
        if session.username not in bk.users:
            bk.users.append(session.username)
            bk.put()
        raise web.seeother('/my')
        
class Unsubscribe(BaseHandler):
    def GET(self, id):
        self.login_required()
        if not id:
            return "the id is empty!<br />"
        try:
            id = int(id)
        except:
            return "the id is invalid!<br />"
            
        bk = Book.get_by_id(id)
        if not bk:
            return "the book(%d) not exist!<br />" % id
        
        if session.username in bk.users:
            bk.users.remove(session.username)
            bk.put()
        raise web.seeother('/my')

class DelFeed(BaseHandler):
    def GET(self, id):
        user = self.getcurrentuser()
        if not id:
            return "the id is empty!<br />"
        try:
            id = int(id)
        except:
            return "the id is invalid!<br />"
        
        feed = Feed.get_by_id(id)
        if feed:
            feed.delete()
        
        raise web.seeother('/my')
                
class Deliver(BaseHandler):
    """ 判断需要推送哪些书籍 """
    def queueit(self, usr, bookid):
        param = {"u":usr.name, "id":bookid, "type":usr.book_type,
            'to':usr.kindle_email,"tz":usr.timezone}
        if usr.titlefmt: param["titlefmt"] = usr.titlefmt
        taskqueue.add(url='/worker',queue_name="deliverqueue1",method='GET',
             params=param)
    
    def GET(self):
        username = web.input().get('u')
        books = Book.all()
        if username: # 现在投递，不判断时间和星期
            sent = []
            for book in books:
                if username not in book.users:
                    continue
                user = KeUser.all().filter("name = ", username).get()
                if user and user.kindle_email:
                    self.queueit(user, book.key().id())
                    sent.append(book.title)
            if len(sent):
                tips = _("Book(s) (%s) put to queue!") % u', '.join(sent)
            else:
                tips = _("No book(s) to deliver!")
            return self.render('autoback.html', "Delivering",tips=tips)
            
        #定时cron调用
        sentcnt = 0
        for book in books:
            if not book.users: # 没有用户订阅此书
                continue
            
            bkcls = None
            if book.builtin:
                bkcls = BookClass(book.title)
                if not bkcls:
                    continue
            
            #确定此书是否需要下载
            for u in book.users:
                user = KeUser.all().filter("enable_send = ",True).filter("name = ", u).get()
                if not user or not user.kindle_email:
                    continue
                    
                #先判断当天是否需要推送
                day = local_time('%A', user.timezone)
                usrdays = user.send_days
                if bkcls and bkcls.deliver_days: #按星期推送
                    days = bkcls.deliver_days
                    if not isinstance(days, list):
                        days = [days]
                    if day not in days:
                        continue
                elif usrdays and day not in usrdays: #为空也表示每日推送
                    continue
                    
                #时间判断
                h = int(local_time("%H", user.timezone)) + 1
                if h >= 24:
                    h -= 24
                if bkcls and bkcls.deliver_times:
                    times = bkcls.deliver_times
                    if not isinstance(times, list):
                        times = [times]
                    if h not in times:
                        continue
                elif user.send_time != h:
                    continue
                
                #到了这里才是需要推送的
                self.queueit(user, book.key().id())
                sentcnt += 1
        return "Put <strong>%d</strong> books to queue!" % sentcnt
        
class Worker(BaseHandler):
    """ 实际下载文章和生成电子书并且发送邮件 """
    def GET(self):
        username = web.input().get("u")
        bookid = web.input().get("id")
        to = web.input().get("to")
        booktype = web.input().get("type", "mobi")
        titlefmt = web.input().get("titlefmt")
        tz = int(web.input().get("tz", TIMEZONE))
        if not bookid or not to:
            return "No book to send!<br />"
        try:
            bookid = int(bookid)
        except:
            return "id of book is invalid!<br />"
            
        bk = Book.get_by_id(bookid)
        if not bk:
            return "Title of feeds not exist!<br />"
        
        if bk.builtin:
            book = BookClass(bk.title)
            if not book:
                return "the builtin book not exist!<br />"
            book = book()
            book.url_filters = [flt.url for flt in UrlFilter.all()]
        else: # 自定义RSS
            if bk.feedscount == 0:
                return "the book has no feed!<br />"
            book = BaseFeedBook()
            book.title = bk.title
            book.description = bk.description
            book.language = bk.language
            book.keep_image = bk.keep_image
            book.oldest_article = bk.oldest_article
            book.fulltext_by_readability = True
            feeds = bk.feeds
            book.feeds = [(feed.title, feed.url, feed.isfulltext) for feed in feeds]
            book.url_filters = [flt.url for flt in UrlFilter.all()]
        
        opts = oeb = None
        
        # 创建 OEB
        global log
        opts = getOpts()
        oeb = CreateOeb(log, None, opts)
        title = "%s %s" % (book.title, local_time(titlefmt, tz)) if titlefmt else book.title
        
        setMetaData(oeb, title, book.language, local_time(tz=tz), 'KindleEar')
        oeb.container = ServerContainer(log)
        
        #guide
        mhfile = book.mastheadfile
        if mhfile:
            id, href = oeb.manifest.generate('masthead', mhfile) # size:600*60
            oeb.manifest.add(id, href, MimeFromFilename(mhfile))
            oeb.guide.add('masthead', 'Masthead Image', href)
        
        coverfile = book.coverfile
        if coverfile:
            id, href = oeb.manifest.generate('cover', coverfile)
            item = oeb.manifest.add(id, href, MimeFromFilename(coverfile))
            oeb.guide.add('cover', 'Cover', href)
            oeb.metadata.add('cover', id)
        
        itemcnt = 0
        sections = OrderedDict()
        # 对于html文件，变量名字自文档
        # 对于图片文件，section为图片mime,url为原始链接,title为文件名,content为二进制内容
        for sec_or_media, url, title, content, brief in book.Items(opts):
            if not sec_or_media or not title or not content:
                continue
            
            if sec_or_media.startswith(r'image/'):
                id, href = oeb.manifest.generate(id='img', href=title)
                item = oeb.manifest.add(id, href, sec_or_media, data=content)
            else:
                id, href = oeb.manifest.generate(id='feed', href='feed%d.html'%itemcnt)
                item = oeb.manifest.add(id, href, 'application/xhtml+xml', data=content)
                oeb.spine.add(item, True)
                sections.setdefault(sec_or_media, [])
                sections[sec_or_media].append((title, item, brief))
                itemcnt += 1
                
        if itemcnt > 0: # 建立TOC，杂志模式需要为两层目录结构
            stoc = ['<html><head><title>Table Of Contents</title></head><body><h2>Table Of Contents</h2>']
            for sec in sections.keys():
                stoc.append('<h3><a href="%s">%s</a></h3>'%(sections[sec][0][1].href,sec))
                sectoc = oeb.toc.add(sec, sections[sec][0][1].href)
                for title, a, brief in sections[sec]:
                    stoc.append('&nbsp;&nbsp;&nbsp;&nbsp;<a href="%s">%s</a><br />'%(a.href,title))
                    sectoc.add(title, a.href, description=brief if brief else None)
            stoc.append('</body></html>')
            id, href = oeb.manifest.generate(id='toc', href='toc.html')
            item = oeb.manifest.add(id, href, 'application/xhtml+xml', data=''.join(stoc))
            oeb.guide.add('toc', 'Table of Contents', href)
            oeb.spine.add(item, True)
            
            oIO = byteStringIO()
            o = EPUBOutput() if booktype == "epub" else MOBIOutput()
            o.convert(oeb, oIO, opts, log)
            self.SendToKindle(username, to, book.title, booktype, str(oIO.getvalue()), tz)
            rs = "%s(%s).%s Sent!"%(book.title, local_time(tz=tz), booktype)
            log.info(rs)
            return rs
        else:
            self.deliverlog(username, to, book.title, 0, status='nonews',tz=tz)
            rs = "No new feeds."
            log.info(rs)
            return rs
        
class Mylogs(BaseHandler):
    def GET(self):
        user = self.getcurrentuser()
        mylogs = DeliverLog.all().filter("username = ", user.name).order('-time').fetch(limit=10)
        logs = {}
        if user.name == 'admin':
            for u in KeUser.all().filter("name != ", 'admin'):
                ul = DeliverLog.all().filter("username = ", u.name).order('-time').fetch(limit=5)
                if ul:
                    logs[u.name] =  ul
        return self.render('logs.html', "Deliver log", current='logs',
            mylogs=mylogs, logs=logs)
        
class RemoveLogs(BaseHandler):
    def GET(self):
        #如果删除了内置书籍py文件，则在数据库中也清除，有最长一天的滞后问题不大
        for bk in Book.all().filter('builtin = ', True):
            found = False
            for book in BookClasses():
                if book.title == bk.title:
                    found = True
                    break
            if not found:
                for fd in bk.feeds:
                    fd.delete()
                bk.delete()
        
        # 停止过期用户的推送
        for user in KeUser.all().filter('enable_send = ', True):
            if user.expires and (user.expires < datetime.datetime.utcnow()):
                user.enable_send = False
                user.put()
        
        query = DeliverLog.all()
        query.filter('datetime < ', datetime.datetime.utcnow() - datetime.timedelta(days=25))
        logs = query.fetch(1000)
        c = len(logs)
        db.delete(logs)
        
        return "%s lines log removed.<br />" % c
    
class SetLang(BaseHandler):
    def GET(self, lang):
        lang = lang.lower()
        if lang not in supported_languages:
            return "language invalid!"
        session.lang = lang
        raise web.seeother(r'/')
        
class Test(BaseHandler):
    def GET(self):
        s = ''
        for d in os.environ:
            s += "<pre><p>" + str(d).rjust(28) + " | " + str(os.environ[d]) + "</p></pre>"
        return s

class DbViewer(BaseHandler):
    def GET(self):
        self.login_required('admin')
        #可以修改UrlEncoding，如果chardet自动检测的编码错误的话
        action = web.input().get('action')
        if action == 'modurlenc':
            id = int(web.input().get('id', 0))
            feedenc = web.input().get('feedenc')
            pageenc = web.input().get('pageenc')
            urlenc = UrlEncoding.get_by_id(id)
            if urlenc:
                if feedenc: urlenc.feedenc = feedenc
                if pageenc: urlenc.pageenc = pageenc
                urlenc.put()
        elif action == 'delurlenc':
            id = int(web.input().get('id', 0))
            urlenc = UrlEncoding.get_by_id(id)
            if urlenc:
                urlenc.delete()
        return self.render('dbviewer.html', "DbViewer",
            books=Book.all(),users=KeUser.all(),
            feeds=Feed.all().order('book'),urlencs=UrlEncoding.all())
        
def fix_filesizeformat(value, binary=False):
    " bugfix for do_filesizeformat of jinja2 "
    bytes = float(value)
    base = binary and 1024 or 1000
    prefixes = [
        (binary and 'KiB' or 'kB'),(binary and 'MiB' or 'MB'),
        (binary and 'GiB' or 'GB'),(binary and 'TiB' or 'TB'),
        (binary and 'PiB' or 'PB'),(binary and 'EiB' or 'EB'),
        (binary and 'ZiB' or 'ZB'),(binary and 'YiB' or 'YB'),]
    if bytes < base:
        return '1 Byte' if bytes == 1 else '%d Bytes' % bytes
    else:
        for i, prefix in enumerate(prefixes):
            unit = base ** (i + 2)
            if bytes < unit:
                return '%.1f %s' % ((base * bytes / unit), prefix)
        return '%.1f %s' % ((base * bytes / unit), prefix)        

urls = (
  r"/", "Home",
  "/login", "Login",
  "/logout", "Logout",
  "/mgrpwd/(.*)", "AdminMgrPwd",
  "/delaccount/(.*)", "DelAccount",
  "/my", "MySubscription",
  "/subscribe/(.*)", "Subscribe",
  "/unsubscribe/(.*)", "Unsubscribe",
  "/delfeed/(.*)", "DelFeed",
  "/setting", "Setting",
  '/advsetting', 'AdvSetting',
  "/admin","Admin",
  "/deliver", "Deliver",
  "/worker", "Worker",
  "/logs", "Mylogs",
  "/removelogs", "RemoveLogs",
  "/lang/(.*)", "SetLang",
  "/advdel", "AdvDel",
  "/test", "Test",
  "/dbviewer","DbViewer",
)

application = web.application(urls, globals())
store = MemcacheStore(memcache)
session = web.session.Session(application, store, initializer={'username':'','login':0,"lang":''})
jjenv = jinja2.Environment(loader=jinja2.FileSystemLoader('templates'),
                            extensions=["jinja2.ext.do",'jinja2.ext.i18n'])
jjenv.filters['filesizeformat'] = fix_filesizeformat
app = application.wsgifunc()

web.config.debug = IsRunInLocal