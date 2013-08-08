#!/usr/bin/env python
# -*- coding:utf-8 -*-

__Version__ = "1.6"
__Author__ = "Arroz"

import os, datetime, logging, re, random, __builtin__, hashlib
from collections import OrderedDict
import gettext

# for debug
IsRunInLocal = (os.environ.get('SERVER_SOFTWARE', '').startswith('Development'))
log = logging.getLogger()
__builtin__.__dict__['default_log'] = log
__builtin__.__dict__['IsRunInLocal'] = IsRunInLocal

gettext.install('lang', 'i18n', unicode=True)

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
from books.base import BaseFeedBook

#reload(sys)
#sys.setdefaultencoding('utf-8')

log.setLevel(logging.INFO if IsRunInLocal else logging.WARN)

def local_time(fmt = "%Y-%m-%d %H:%M", tz=TIMEZONE):
    return (datetime.datetime.utcnow()+datetime.timedelta(hours=tz)).strftime(fmt)

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
    
    #这两个属性只有自定义RSS才有意义
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
    
class KeUser(db.Model): # kindleEar User
    name = db.StringProperty(required=True)
    passwd = db.StringProperty(required=True)
    kindle_email = db.StringProperty()
    enable_send = db.BooleanProperty()
    send_time = db.IntegerProperty()
    timezone = db.IntegerProperty()
    book_type = db.StringProperty()
    expires = db.DateTimeProperty()
    ownfeeds = db.ReferenceProperty(Book) # 每个用户都有自己的自定义RSS
    
class Feed(db.Model):
    book = db.ReferenceProperty(Book)
    title = db.StringProperty()
    url = db.StringProperty()
    isfulltext = db.BooleanProperty()
    
class DeliverLog(db.Model):
    username = db.StringProperty()
    #email = db.StringProperty()
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

def StoreBookToDb():
    for book in BookClasses():  #添加内置书籍
        if memcache.get(book.title): #使用memcache加速
            continue
        b = Book.all().filter("title = ", book.title).get()
        if not b:
            b = Book(title=book.title,description=book.description,builtin=True)
            b.put()
            memcache.add(book.title, book.description, 86400)

StoreBookToDb()

class BaseHandler:
    " URL请求处理类的基类，实现一些共同的工具函数 "
    @classmethod
    def logined(self):
        return True if session.login == 1 else False
    
    @classmethod
    def login_required(self, username=None):
        if (session.login == 0) or (username and username != session.username):
            raise web.seeother(r'/')
    
    @classmethod
    def getcurrentuser(self):
        self.login_required()
        u = KeUser.all().filter("name = ", session.username).get()
        if not u:
            raise web.seeother(r'/')
        return u
        
    def browerlang(self):
        lang = web.ctx.env.get('HTTP_ACCEPT_LANGUAGE', "zh-cn")
        return "zh-cn" if lang.startswith("zh") else "en"
    
    def set_lang(self):
        set_lang(session.lang if session.lang else self.browerlang())
        
    @classmethod
    def deliverlog(self, emails, book, size, status='ok', tz=TIMEZONE):
        if not isinstance(emails, list):
            emails = [emails,]
        for email in emails:
            user = KeUser.all().filter("kindle_email = ", email).get()
            name = user.name if user else ''
            timezone = user.timezone if user else tz
            try:
                dl = DeliverLog(username=name, to=email, size=size,
                   time=local_time(tz=timezone), datetime=datetime.datetime.utcnow(),
                   book=book, status=status)
                dl.put()
            except Exception as e:
                self.log.warn('DeliverLog failed to save:%s',str(e))
    
    @classmethod        
    def SendToKindle(self, emails, title, booktype, attachment, tz=TIMEZONE, filewithtime=True):
        if not isinstance(emails, list):
            emails = [emails,]
            
        if PINYIN_FILENAME: # 将中文文件名转换为拼音
            from calibre.ebooks.unihandecode.unidecoder import Unidecoder
            decoder = Unidecoder()
            basename = decoder.decode(title)
        else:
            basename = title
        
        for email in emails:
            user = KeUser.all().filter("kindle_email = ", email).get()
            tz = user.timezone if user else TIMEZONE
            if filewithtime:
                filename = "%s(%s).%s"%(basename,local_time('%Y-%m-%d_%H-%M',tz=tz),booktype)
            else:
                filename = "%s.%s"%(basename,booktype)
            try:
                mail.send_mail(SrcEmail, email, "KindleEar", "Deliver from KindlerEar",
                    attachments=[(filename, attachment),])
            except OverQuotaError as e:
                self.log.warn('overquota when sendmail to %s:%s', (email, str(e)))
                self.deliverlog(email, title, len(attachment), tz=tz, status='over quota')
            except Exception as e:
                default_log.warn('sendmail to %s failed:%s', (email, str(e)))
                self.deliverlog(email, title, len(attachment), tz=tz, status='send failed')
            else:
                self.deliverlog(email, title, len(attachment), tz=tz)
     
class Home(BaseHandler):
    def GET(self):
        self.set_lang()
        return jjenv.get_template('home.html').render(nickname=session.username,
            title="Home",version=__Version__)

class Setting(BaseHandler):
    def GET(self, success=False):
        user = self.getcurrentuser()
        self.set_lang()
        return jjenv.get_template('setting.html').render(nickname=session.username,
            title="Setting",current='setting',user=user,mail_sender=SrcEmail,success=success)
    
    def POST(self):
        user = self.getcurrentuser()
        user.kindle_email = web.input().get('kindle_email')
        user.timezone = int(web.input().get('timezone'))
        user.send_time = int(web.input().get('send_time'))
        user.enable_send = bool(web.input().get('enable_send'))
        user.book_type = web.input().get('book_type')
        user.put()
        
        myfeeds = user.ownfeeds
        myfeeds.language = web.input().get("lng")
        myfeeds.title = web.input().get("rt")
        myfeeds.keep_image = bool(web.input().get("keepimage"))
        myfeeds.users = [user.name] if web.input().get("enablerss") else []
        myfeeds.put()
        
        raise web.seeother('')

class AdvSetting(BaseHandler):
    def GET(self):
        user = self.getcurrentuser()
        self.set_lang()
        delurlid = web.input().get('delurlid')
        delwlist = web.input().get('delwlist')
        if delurlid:
            try:
                delurlid = int(delurlid)
            except:
                pass
            else:
                flt = UrlFilter.get_by_id(delurlid)
                if flt:
                    flt.delete()
        if delwlist:
            try:
                delwlist = int(delwlist)
            except:
                pass
            else:
                wlist = WhiteList.get_by_id(delwlist)
                if wlist:
                    wlist.delete()
        return jjenv.get_template('advsetting.html').render(nickname=session.username,
            title="Advanced Setting",current='advsetting',user=user,
            urlfilters=UrlFilter.all(),whitelists=WhiteList.all())
        
    def POST(self):
        user = self.getcurrentuser()
        url = web.input().get('url')
        if url:
            UrlFilter(url=url).put()
        wlist = web.input().get('wlist')
        if wlist:
            WhiteList(mail=wlist).put()
        raise web.seeother('/advsetting')
        
class Admin(BaseHandler):
    # 账户管理页面
    def GET(self):
        user = self.getcurrentuser()
        self.set_lang()
        users=KeUser.all() if user.name == 'admin' else None
        return jjenv.get_template('admin.html').render(nickname=session.username,
            title="Admin", current='admin', user=user, users=users)
    
    def POST(self):
        self.set_lang()
        u,up1,up2 = web.input().get('u'),web.input().get('up1'),web.input().get('up2')
        op,p1,p2 = web.input().get('op'), web.input().get('p1'), web.input().get('p2')
        user = self.getcurrentuser()
        users=KeUser.all() if user.name == 'admin' else None
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
                    tips = _("The new passwords are different!")
                else:
                    tips = _("Change password success!")
                    user.passwd = newpwd
                    user.put()
            return jjenv.get_template('admin.html').render(nickname=session.username,
                title="Admin",current='admin',user=user,users=users,chpwdtips=tips)
        elif u is not None and up1 is not None and up2 is not None: #添加账户
            if user.name != 'admin':
                raise web.seeother(r'/')
            elif not u:
                tips = _("Username is empty!")
            elif up1 != up2:
                tips = _("The new passwords are different!")
            elif KeUser.all().filter("name = ", u).get():
                tips = _("Already exist the username!")
            else:
                try:
                    pwd = hashlib.md5(up1).hexdigest()
                except:
                    tips = _("The password includes non-ascii chars!")
                else:
                    myfeeds = Book(title=MY_FEEDS_TITLE,description=MY_FEEDS_DESC,
                        builtin=False,keep_image=True)
                    myfeeds.put()
                    au = KeUser(name=u,passwd=pwd,kindle_email='',enable_send=False,
                        send_time=7,timezone=TIMEZONE,book_type="mobi",ownfeeds = myfeeds)
                    au.expires = datetime.datetime.utcnow()+datetime.timedelta(days=180)
                    au.put()
                    tips = _("Add a account success!")
            return jjenv.get_template('admin.html').render(nickname=session.username,
                title="Admin",current='admin',user=user,users=users,actips=tips)
        else:
            return self.GET()
       
class Login(BaseHandler):
    def GET(self):
        self.set_lang()
        # 第一次登陆时如果没有管理员帐号，
        # 则增加一个管理员帐号admin，密码admin，后续可以修改密码
        tips = ''
        u = KeUser.all().filter("name = ", 'admin').get()
        if not u:
            myfeeds = Book(title=MY_FEEDS_TITLE,description=MY_FEEDS_DESC,
                    builtin=False,keep_image=True)
            myfeeds.put()
            au = KeUser(name='admin',passwd=hashlib.md5('admin').hexdigest())
            au.kindle_email = ''
            au.enable_send = False
            au.send_time = 8
            au.timezone = TIMEZONE
            au.book_type = "mobi"
            au.expires = None
            au.ownfeeds = myfeeds
            au.put()
            tips = _("Please use admin/admin to login at first time.")
        else:
            tips = _("Please input username and password.")
        
        if session.login == 1:
            web.seeother(r'/')
        else:
            return jjenv.get_template("login.html").render(nickname='',title='Login',tips=tips)
        
    def POST(self):
        self.set_lang()
        name, passwd = web.input().get('u'), web.input().get('p')
        if name.strip() == '':
            tips = _("Username is empty!")
            return jjenv.get_template("login.html").render(nickname='',
                title='Login',tips=tips)
        elif len(name) > 25:
            tips = _("The len of username reached the limit of 25 chars!")
            return jjenv.get_template("login.html").render(nickname='',
                title='Login',tips=tips,username=name)
        elif '<' in name or '>' in name or '&' in name:
            tips = _("The username includes unsafe chars!")
            return jjenv.get_template("login.html").render(nickname='',
                title='Login',tips=tips)
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
            tips = _("The username no exist or password is wrong!")
            session.login = 0
            session.username = ''
            session.kill()
            return jjenv.get_template("login.html").render(nickname='',
                title='Login',tips=tips,username=name)
            
class Logout(BaseHandler):
    def GET(self):
        session.login = 0
        session.username = ''
        session.kill()
        raise web.seeother(r'/')

class AdminMgrPwd(BaseHandler):
    # 管理员修改其他账户的密码
    def GET(self, name):
        self.login_required('admin')
        self.set_lang()
        tips = _("Please input new password to confirm!")
        return jjenv.get_template("adminmgrpwd.html").render(nickname=session.username,
            title='Change password',tips=tips,username=name)
        
    def POST(self):
        self.login_required('admin')
        self.set_lang()
        name, p1, p2 = web.input().get('u'),web.input().get('p1'),web.input().get('p2')
        if name:
            u = KeUser.all().filter("name = ", name).get()
            if not u:
                tips = _("The username '%s' not exist!") % name
            elif p1 != p2:
                tips = _("The new passwords are different!")
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
            
        return jjenv.get_template("adminmgrpwd.html").render(nickname=session.username,
            title='Change password',tips=tips,username=name)

class DelAccount(BaseHandler):
    def GET(self, name):
        self.login_required()
        self.set_lang()
        if session.username == 'admin' or (name and name == session.username):
            tips = _("Please confirm to delete the account!")
            return jjenv.get_template("delaccount.html").render(nickname=session.username,
                title='Delete account',tips=tips,username=name)
        else:
            raise web.seeother(r'/')
    
    def POST(self):
        self.login_required()
        self.set_lang()
        name = web.input().get('u')
        if name and (session.username == 'admin' or session.username == name):
            u = KeUser.all().filter("name = ", name).get()
            if not u:
                tips = _("The username '%s' not exist!") % name
            else:
                if u.ownfeeds:
                    u.ownfeeds.delete()
                u.delete()
                
                # 要删掉数据库中订阅记录
                for book in Book.all():
                    if book.users and name in book.users:
                        book.users.remove(name)
                        book.put()
                
                if session.username == name:
                    raise web.seeother('/logout')
                else:
                    tips = _("Delete success!")
        else:
            tips = _("The username is empty or you dont have right to delete it!")
        return jjenv.get_template("delaccount.html").render(nickname=session.username,
            title='Delete account',tips=tips,username=name)

class MySubscription(BaseHandler):
    # 管理我的订阅和杂志列表
    def GET(self, tips=None):
        user = self.getcurrentuser()
        self.set_lang()
        myfeeds = user.ownfeeds.feeds if user.ownfeeds else None
        return jjenv.get_template("my.html").render(nickname=session.username,current='my',
                title='My subscription',books=Book.all().filter("builtin = ",True),
                myfeeds=myfeeds,tips=tips)
    
    def POST(self): # 添加自定义RSS
        user = self.getcurrentuser()
        title = web.input().get('t')
        url = web.input().get('url')
        isfulltext = bool(web.input().get('fulltext'))
        if not title or not url:
            return self.GET(_("Title or url is empty!"))
        
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
        
class Renew(BaseHandler):
    def GET(self, name):
        self.login_required()
        if (name and name != 'admin'
            and (session.username == 'admin' or name == session.username)):
            user = KeUser.all().filter("name = ", name).get()
            if user:
                user.expires = datetime.datetime.utcnow()+datetime.timedelta(days=180)
                user.put()
            raise web.seeother(r'/setting')
        else:
            raise web.seeother(r'/')
        
class Deliver(BaseHandler):
    def GET(self):
        username = web.input().get('u')
        books = Book.all()
        sent = []
        if username: # 现在投递
            self.set_lang()
            for book in books:
                if username not in book.users:
                    continue
                user = KeUser.all().filter("name = ", username).get()
                if user and user.kindle_email:
                    taskqueue.add(url='/worker',queue_name="deliverqueue1",method='GET',
                        params={"id":book.key().id(), "type":user.book_type, 'emails':user.kindle_email})
                    sent.append(book.title)
            if len(sent):
                tips = _("Book(s) (%s) put to queue!") % u', '.join(sent)
            else:
                tips = _("No book(s) to deliver!")
            return jjenv.get_template("autoback.html").render(nickname=session.username,
                title='Delivering',tips=tips)
        
        #定时cron调用
        for book in books:
            if not book.users: # 没有用户订阅此书
                continue
            
            mobiemails, epubemails = [], []
            for u in book.users:
                user = KeUser.all().filter("enable_send = ",True).filter("name = ", u).get()
                if user:
                    h = int(local_time("%H", user.timezone)) + 1
                    h = h - 24 if h > 24 else h
                    if user.send_time == h and user.kindle_email:
                        if book.builtin:
                            bkcls = BookClass(book.title)
                            if not bkcls:
                                continue
                            if bkcls.deliver_days: #按星期推送
                                day = local_time('%A', user.timezone)
                                days = bkcls.deliver_days if isinstance(bkcls.deliver_days,list) else [bkcls.deliver_days]
                                if day in days:
                                    lstemails = epubemails if user.book_type=='epub' else mobiemails
                                    lstemails.append(user.kindle_email)
                            else:
                                lstemails = epubemails if user.book_type=='epub' else mobiemails
                                lstemails.append(user.kindle_email)
                        else:
                            lstemails = epubemails if user.book_type=='epub' else mobiemails
                            lstemails.append(user.kindle_email)
                        sent.append(book.title)
            if mobiemails:
                emails = ','.join(mobiemails)
                taskqueue.add(url='/worker',queue_name="deliverqueue1",method='GET',
                    params={"id":book.key().id(), "type":"mobi", 'emails': emails})
            if epubemails:
                emails = ','.join(epubemails)
                taskqueue.add(url='/worker', queue_name="deliverqueue1",method='GET',
                    params={"id":book.key().id(), "type":"epub", 'emails': emails})
        tips = u', '.join(sent)
        return jjenv.get_template("autoback.html").render(nickname=session.username,
                title='Delivering',tips=_("Book(s) (%s) put to queue!") % tips)
        
class Worker(BaseHandler):
    def GET(self):
        bookid = web.input().get("id")
        emails = web.input().get("emails")
        booktype = web.input().get("type", "mobi")
        if not bookid or not emails:
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
        else: # 自定义RSS
            if bk.feedscount == 0:
                return "the book has no feed!<br />"
            book = BaseFeedBook()
            book.title = bk.title
            book.description = bk.description
            book.language = bk.language
            book.keep_image = bk.keep_image
            book.fulltext_by_readability = True
            feeds = bk.feeds
            book.feeds = [(feed.title, feed.url, feed.isfulltext) for feed in feeds]
            book.url_filters = [flt.url for flt in UrlFilter.all()]
        
        emails = emails.split(',')
        
        opts = oeb = None
        
        # 创建 OEB
        global log
        opts = getOpts()
        oeb = CreateOeb(log, None, opts)
        setMetaData(oeb, book.title, book.language, local_time(), SrcEmail)
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
        for sec_or_media, url, title, content, brief in book.Items():
            if not sec_or_media or not title or not content:
                continue
            
            if sec_or_media.startswith(r'image/'):
                id, href = oeb.manifest.generate(id='img', href=title)
                item = oeb.manifest.add(id, href, sec_or_media, data=content)
            else:
                id, href = oeb.manifest.generate(id='feed', href='feed%d.htm'%itemcnt)
                item = oeb.manifest.add(id, href, 'text/html', data=content)
                oeb.spine.add(item, True)
                sections.setdefault(sec_or_media, [])
                sections[sec_or_media].append((title, item, brief))
                itemcnt += 1
                
        if itemcnt > 0: # 建立TOC，杂志模式需要为两层目录结构
            for sec in sections.keys():
                sectoc = oeb.toc.add(sec, sections[sec][0][1].href)
                for title, a, brief in sections[sec]:
                    sectoc.add(title, a.href, description=brief if brief else None)
            
            oIO = byteStringIO()
            o = EPUBOutput() if booktype == "epub" else MOBIOutput()
            o.convert(oeb, oIO, opts, log)
            self.SendToKindle(emails, book.title, booktype, str(oIO.getvalue()))
            rs = "%s(%s).%s Sent!"%(book.title,local_time(),booktype)
            log.info(rs)
            return rs
        else:
            self.deliverlog(emails, book.title, 0, status='nonews')
            rs = "No new feeds."
            log.info(rs)
            return rs
        
class Mylogs(BaseHandler):
    def GET(self):
        user = self.getcurrentuser()
        self.set_lang()
        logs = DeliverLog.all().filter("username = ", 'admin').order('-time').fetch(limit=10)
        return jjenv.get_template("logs.html").render(nickname=session.username,
            title='Deliver log', current='logs', logs=logs)
    
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
        for user in KeUser.all():
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
        if lang not in ('zh-cn', 'en'):
            return "language invalid!"
        session.lang = lang
        self.set_lang()
        raise web.seeother(r'/')
        
class Test(BaseHandler):
    def GET(self):
        s = ''
        for d in os.environ:
            s += "<pre><p>" + str(d).rjust(28) + " | " + str(os.environ[d]) + "</p></pre>"
        return s

class DbViewer(BaseHandler):
    def GET(self):
        self.login_required()
        return jjenv.get_template("dbviewer.html").render(nickname=session.username,
            title='DbViewer',books=Book.all(),users=KeUser.all(),feeds=Feed.all().order('book'))
        
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
  "/renew/(.*)", "Renew",
  "/deliver", "Deliver",
  "/worker", "Worker",
  "/logs", "Mylogs",
  "/removelogs", "RemoveLogs",
  "/setlang/(.*)", "SetLang",
  "/test", "Test",
  "/dbviewer","DbViewer",
)

def set_lang(lang):
    """ 设置网页显示语言 """
    tr = gettext.translation('lang', 'i18n', languages=[lang])
    tr.install(True)
    jjenv.install_gettext_translations(tr)
    
app = web.application(urls, globals())
store = MemcacheStore(memcache)
session = web.session.Session(app, store, initializer={'username':'','login':0,"lang":''})
jjenv = jinja2.Environment(loader=jinja2.FileSystemLoader('templates'),
                            extensions=["jinja2.ext.do",'jinja2.ext.i18n'])
jjenv.filters['filesizeformat'] = fix_filesizeformat

app = app.wsgifunc()

web.config.debug = IsRunInLocal
