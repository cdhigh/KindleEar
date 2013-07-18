#!/usr/bin/env python
# -*- coding:utf-8 -*-

__Version__ = "1.3.4"
__Author__ = "Arroz"

import os, datetime, logging, re, random, __builtin__, hashlib
from collections import OrderedDict

# for debug
IsRunInLocal = (os.environ.get('SERVER_NAME', None)=="localhost")
log = logging.getLogger()
__builtin__.__dict__['default_log'] = log
__builtin__.__dict__['IsRunInLocal'] = IsRunInLocal

import web
import jinja2
from google.appengine.api import mail
from google.appengine.ext import db
from google.appengine.api import taskqueue
from google.appengine.api import memcache

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
    feed_encoding = db.StringProperty()
    page_encoding = db.StringProperty()
    mastheadfile = db.StringProperty() # GIF 600*60
    coverfile = db.StringProperty()
    keep_image = db.BooleanProperty()
    
    def feeds(self):
        return Feed.all().filter('book = ', self.key())

class KeUser(db.Model): # kindleEar User
    name = db.StringProperty(required=True)
    passwd = db.StringProperty(required=True)
    kindle_email = db.StringProperty()
    enable_send = db.BooleanProperty()
    send_time = db.IntegerProperty()
    timezone = db.IntegerProperty()
    book_type = db.StringProperty()
    last_delivered = db.DateTimeProperty()
    expires = db.DateTimeProperty()
    ownfeeds = db.ReferenceProperty(Book) # 每个用户都有自己的自定义RSS
        
class Feed(db.Model):
    book = db.ReferenceProperty(Book)
    title = db.StringProperty()
    url = db.StringProperty()
    
class DeliverLog(db.Model):
    username = db.StringProperty()
    #email = db.StringProperty()
    to = db.StringProperty()
    size = db.IntegerProperty()
    time = db.StringProperty()
    datetime = db.DateTimeProperty()
    book = db.StringProperty()
    status = db.StringProperty()
    
def StoreBookToDb():
    for book in BookClasses():  #添加内置书籍
        b = Book.all().filter("title = ", book.title).get()
        if not b:
            b = Book(title=book.title,description=book.description,builtin=True)
            b.put()
    
    for bk in Book.all().filter('builtin = ', True): #clean
        found = False
        for book in BookClasses():
            if book.title == bk.title:
                found = True
                break
        if not found:
            bk.delete()

StoreBookToDb()

class BaseHandler:
    " URL请求处理类的基类，实现一些共同的工具函数 "
    @classmethod
    def logined(self):
        return True if session.login == 1 else False
    
    def login_required(self, username=None):
        if (session.login == 0) or (username and username != session.username):
            raise web.seeother(r'/')
    
    def getcurrentuser(self):
        self.login_required()
        u = KeUser.all().filter("name = ", session.username).get()
        if not u:
            raise web.seeother(r'/')
        return u
    
    def deliverlog(self, emails, book, size, status='ok', tz=TIMEZONE):
        if not isinstance(emails, list):
            emails = [emails,]
        for email in emails:
            user = KeUser.all().filter("kindle_email = ", email).get()
            name = user.name if user else ''
            timezone = user.timezone if user else tz
            dl = DeliverLog(username=name, to=email, size=size,
               time=local_time(tz=timezone), datetime=datetime.datetime.utcnow(),
               book=book, status=status)
            dl.put()
            
    def SendToKindle(self, emails, title, booktype, attachment, tz=TIMEZONE):
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
            filename = "%s(%s).%s"%(basename,local_time('%Y-%m-%d_%H-%M',tz=tz),booktype)
            mail.send_mail(SrcEmail, email, "KindleEar", "Deliver from KindlerEar",
                attachments=[(filename, attachment),])
            self.deliverlog(email, title, len(attachment), tz=tz)
        
class Home(BaseHandler):
    def GET(self):
        return jjenv.get_template('home.html').render(nickname=session.username,
            title="Home",version=__Version__)

class Setting(BaseHandler):
    def GET(self, success=False):
        user = self.getcurrentuser()
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
        
        ownfeeds = user.ownfeeds
        ownfeeds.language = web.input().get("lng")
        ownfeeds.title = web.input().get("rt")
        ownfeeds.keep_image = bool(web.input().get("keepimage"))
        ownfeeds.users = [user.name] if web.input().get("enablerss") else []
        ownfeeds.put()
        
        raise web.seeother('')
        
class Admin(BaseHandler):
    # 账户管理页面
    def GET(self):
        user = self.getcurrentuser()
        users=KeUser.all() if user.name == 'admin' else None
        return jjenv.get_template('admin.html').render(nickname=session.username,
            title="Admin", current='admin', user=user, users=users)
    
    def POST(self):
        u,up1,up2 = web.input().get('u'),web.input().get('up1'),web.input().get('up2')
        op,p1,p2 = web.input().get('op'), web.input().get('p1'), web.input().get('p2')
        user = self.getcurrentuser()
        users=KeUser.all() if user.name == 'admin' else None
        if op is not None and p1 is not None and p2 is not None: #修改密码
            if user.passwd != hashlib.md5(op).hexdigest():
                tips = u"原密码错误！"
            elif p1 != p2:
                tips = u"两次输入的新密码不匹配！"
            else:
                tips = u"密码修改成功！"
                user.passwd = hashlib.md5(p1).hexdigest()
                user.put()
            return jjenv.get_template('admin.html').render(nickname=session.username,
                title="Admin",current='admin',user=user,users=users,chpwdtips=tips)
        elif u is not None and up1 is not None and up2 is not None: #添加账户
            if user.name != 'admin':
                raise web.seeother(r'/')
            elif not u:
                tips = u"用户名为空！"
            elif up1 != up2:
                tips = u"两次输入的密码不匹配！"
            elif KeUser.all().filter("name = ", u).get():
                tips = u"用户名已经存在！"
            else:
                ownfeeds = Book(title=OWNFEEDS_TITLE,description=OWNFEEDS_DESC,
                    builtin=False,keep_image=True)
                ownfeeds.put()
                au = KeUser(name=u,passwd=hashlib.md5(up1).hexdigest())
                au.kindle_email = ''
                au.enable_send = False
                au.send_time = 7
                au.timezone = TIMEZONE
                au.book_type = "mobi"
                au.expires = datetime.datetime.utcnow()+datetime.timedelta(days=180)
                au.ownfeeds = ownfeeds
                au.put()
                
                tips = u"添加用户账号成功！ "
            return jjenv.get_template('admin.html').render(nickname=session.username,
                title="Admin",current='admin',user=user,users=users,actips=tips)
        else:
            return self.GET()
       
class Login(BaseHandler):
    def GET(self):
        # 第一次登陆时如果没有管理员帐号，
        # 则增加一个管理员帐号admin，密码admin，后续可以修改密码
        tips = ''
        u = KeUser.all().filter("name = ", 'admin').get()
        if not u:
            ownfeeds = Book(title=OWNFEEDS_TITLE,description=OWNFEEDS_DESC,
                    builtin=False,keep_image=True)
            ownfeeds.put()
            au = KeUser(name='admin',passwd=hashlib.md5('admin').hexdigest())
            au.kindle_email = ''
            au.enable_send = False
            au.send_time = 8
            au.timezone = TIMEZONE
            au.book_type = "mobi"
            au.expires = None
            au.ownfeeds = ownfeeds
            au.put()
            tips = u"初次登陆请使用用户名'admin'/密码'admin'登陆。 "
        else:
            tips = u"请输入正确的用户名和密码登陆进入系统。 "
        
        if session.login == 1:
            web.seeother(r'/')
        else:
            return jjenv.get_template("login.html").render(nickname='',title='Login',tips=tips)
        
    def POST(self):
        name, passwd = web.input().get('u'), web.input().get('p')
        if name.strip() == '':
            tips = u"用户名为空！ "
            return jjenv.get_template("login.html").render(nickname='',
                title='Login',tips=tips)
        elif len(name) > 25:
            tips = u"用户名限制为25个字符！ "
            return jjenv.get_template("login.html").render(nickname='',
                title='Login',tips=tips,username=name)
        elif '<' in name or '>' in name or '&' in name:
            tips = u"用户名包含非法字符！ "
            return jjenv.get_template("login.html").render(nickname='',
                title='Login',tips=tips)
        
        pwdhash = hashlib.md5(passwd).hexdigest()
        u = KeUser.all().filter("name = ", name).filter("passwd = ", pwdhash).get()
        if u:
            session.login = 1
            session.username = name
            if u.expires: #用户登陆后自动续期
                u.expires = datetime.datetime.utcnow()+datetime.timedelta(days=180)
                u.put()
            raise web.seeother(r'/')
        else:
            tips = u"用户名不存在或密码错误！ "
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
    def GET(self):
        self.login_required('admin')
        name = web.input().get('u')
        tips = u"请输入新的密码并确认！ "
        return jjenv.get_template("adminmgrpwd.html").render(nickname=session.username,
            title='Change password',tips=tips,username=name)
        
    def POST(self):
        self.login_required('admin')
        name, p1, p2 = web.input().get('u'),web.input().get('p1'),web.input().get('p2')
        if name:
            u = KeUser.all().filter("name = ", name).get()
            if not u:
                tips = u"用户名'%s'不存在！" % name
            elif p1 != p2:
                tips = u"两次输入的密码不相符！ "
            else:
                u.passwd = hashlib.md5(p1).hexdigest()
                u.put()
                tips = u"密码修改成功！ "
        else:
            tips = u"用户名不能为空！ "
            
        return jjenv.get_template("adminmgrpwd.html").render(nickname=session.username,
            title='Change password',tips=tips,username=name)

class DelAccount(BaseHandler):
    def GET(self):
        self.login_required()
        name = web.input().get('u')
        
        if session.username == 'admin' or (name and name == session.username):
            tips = u"请确认是否要删除此账号！ "
            return jjenv.get_template("delaccount.html").render(nickname=session.username,
                title='Delete account',tips=tips,username=name)
        else:
            raise web.seeother(r'/')
    
    def POST(self):
        self.login_required()
        name = web.input().get('u')
        if name and (session.username == 'admin' or session.username == name):
            u = KeUser.all().filter("name = ", name).get()
            if not u:
                tips = u"用户名'%s'不存在！" % name
            else:
                ownfeeds = u.ownfeeds
                if ownfeeds:
                    ownfeeds.delete()
                u.delete()
                
                # 要删掉数据库中订阅记录
                for book in Book.all():
                    if book.users and name in book.users:
                        book.users.remove(name)
                        book.put()
                
                if session.username == name:
                    raise web.seeother('/logout')
                else:
                    tips = u"删除成功！"
        else:
            tips = u"用户名为空或你没有权限删除此账号！"
        return jjenv.get_template("delaccount.html").render(nickname=session.username,
            title='Delete account',tips=tips,username=name)

class MySubscription(BaseHandler):
    # 管理我的订阅和杂志列表
    def GET(self, tips=None):
        user = self.getcurrentuser()
        ownfeeds = user.ownfeeds.feeds() if user and user.ownfeeds else None
        return jjenv.get_template("my.html").render(nickname=session.username,current='my',
                title='My subscription',books=Book.all().filter("builtin = ",True),
                ownfeeds=ownfeeds,tips=tips)
    
    def POST(self): # 添加自定义RSS
        user = self.getcurrentuser()
        title = web.input().get('t')
        url = web.input().get('url')
        if not title or not url:
            return self.GET(u"标题和URL都不能为空！")
        
        assert user.ownfeeds
        Feed(title=title,url=url,book=user.ownfeeds).put()
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
        
        bk = Book.all().ancestor(db.Key.from_path("Book", id)).get()
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
            
        bk = Book.all().ancestor(db.Key.from_path("Book", id)).get()
        #bk = Book.all().filter("title = ", title).get()
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
        
        feed = Feed.all().ancestor(db.Key.from_path("Feed", id)).get()
        if feed:
            feed.delete()
        
        raise web.seeother('/my')
        
class Renew(BaseHandler):
    def GET(self):
        self.login_required()
        name = web.input().get('u')
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
        sentcnt = 0
        books = Book.all()
        if username: # 现在投递
            for book in books:
                if username not in book.users:
                    continue
                user = KeUser.all().filter("name = ", username).get()
                if user and user.kindle_email:
                    taskqueue.add(url='/worker',queue_name="deliverqueue1",method='GET',
                        params={"id":book.key().id(), "type":user.book_type, 'emails':user.kindle_email})
                    sentcnt += 1
            return jjenv.get_template("autoback.html").render(nickname=session.username,
                title='Delivering',tips=u"%d本书籍已放入推送队列！"%sentcnt)
        
        #定时cron调用
        for book in books:
            if not book.users: # 没有用户订阅此书
                continue
            
            mobiemails = []
            epubemails = []
            for u in book.users:
                user = KeUser.all().filter("enable_send = ",True).filter("name = ", u).get()
                if user:
                    h = int(local_time("%H", user.timezone)) + 1
                    h = h - 24 if h > 24 else h
                    if user.send_time == h and user.kindle_email:
                        if user.book_type == "epub":
                            epubemails.append(user.kindle_email)
                        else:
                            mobiemails.append(user.kindle_email)
                        sentcnt += 1
            if mobiemails:
                emails = ','.join(mobiemails)
                taskqueue.add(url='/worker',queue_name="deliverqueue1",method='GET',
                    params={"id":book.key().id(), "type":"mobi", 'emails': emails})
            if epubemails:
                emails = ','.join(epubemails)
                taskqueue.add(url='/worker', queue_name="deliverqueue1",method='GET',
                    params={"id":book.key().id(), "type":"epub", 'emails': emails})
        return jjenv.get_template("autoback.html").render(nickname=session.username,
                title='Delivering',tips=u"%d本书已经放入推送队列！"%sentcnt)
        
class Worker(BaseHandler):
    def GET(self):
        id = web.input().get("id")
        emails = web.input().get("emails")
        booktype = web.input().get("type", "mobi")
        if not id or not emails:
            return "No book to send!<br />"
        try:
            id = int(id)
        except:
            return "id of book is invalid!<br />"
            
        bk = Book.all().ancestor(db.Key.from_path("Book", id)).get()
        if not bk:
            return "Title of feeds not exist!<br />"
        
        if bk.builtin:
            book = BookClass(bk.title)
            if not book:
                return "the builtin book not exist!<br />"
            book = book()
        else: # 自定义RSS
            feeds = bk.feeds()
            if feeds.count() == 0:
                return "the book has no feed!<br />"
            book = BaseFeedBook()
            book.title = bk.title
            book.description = bk.description
            book.language = bk.language
            #book.feed_encoding = bk.feed_encoding
            #book.page_encoding = bk.page_encoding
            book.mastheadfile = bk.mastheadfile
            book.coverfile = bk.coverfile
            book.keep_image = bk.keep_image
            book.fulltext_by_readability = True
            for feed in feeds:
                book.feeds.append((feed.title, feed.url))
        
        emails = emails.split(',')
        
        opts = oeb = None
        
        # 创建 OEB
        global log
        opts = getOpts()
        oeb = CreateOeb(log, None, opts)
        setMetaData(oeb, book.title, book.language, local_time(), SrcEmail)
        oeb.container = ServerContainer(log)
        
        #guide
        mhfile = book.mastheadfile if book.mastheadfile else DEFAULT_MASTHEAD
        if mhfile:
            id, href = oeb.manifest.generate('masthead', mhfile) # size:600*60
            oeb.manifest.add(id, href, 'image/gif')
            oeb.guide.add('masthead', 'Masthead Image', href)
        
        coverfile = book.coverfile if book.coverfile else DEFAULT_COVER
        if coverfile:
            id, href = oeb.manifest.generate('cover', coverfile)
            item = oeb.manifest.add(id, href, MimeFromFilename(coverfile))
            oeb.guide.add('cover', 'Cover', href)
            oeb.metadata.add('cover', id)
        
        itemcnt = 0
        sections = OrderedDict()
        # 对于html文件，变量名字自文档
        # 对于图片文件，section为图片mime,url为原始链接,title为文件名,content为二进制内容
        for section, url, title, content in book.Items():
            if not section or not title or not content:
                continue
            
            if section.startswith(r'image/'):
                id, href = oeb.manifest.generate(id='img', href=title)
                item = oeb.manifest.add(id, href, section, data=content)
            else:
                id, href = oeb.manifest.generate(id='feed', href='feed%d.htm'%itemcnt)
                item = oeb.manifest.add(id, href, 'text/html', data=content)
                oeb.spine.add(item, True)
                sections.setdefault(section, [])
                sections[section].append((title, item))
                itemcnt += 1
                
        if itemcnt > 0: # 建立TOC，杂志模式需要为两层目录结构
            for sec in sections.keys():
                sectoc = oeb.toc.add(sec, sections[sec][0][1].href)
                for title, a in sections[sec]:
                    sectoc.add(title, a.href)
            
            oIO = byteStringIO()
            o = EPUBOutput() if booktype == "epub" else MOBIOutput()
            o.convert(oeb, oIO, opts, log)
            self.SendToKindle(emails, book.title, booktype, str(oIO.getvalue()))
            return "%s(%s).%s Sent!<br />"%(book.title,local_time(),booktype)
        else:
            self.deliverlog(emails, book.title, 0, status='nonews')
            return "No new feeds.<br />"
        
class Mylogs(BaseHandler):
    def GET(self):
        user = self.getcurrentuser()
        logs = DeliverLog.all().filter("username = ", 'admin').order('-time').fetch(limit=10)
        return jjenv.get_template("logs.html").render(nickname=session.username,
            title='Deliver log', current='logs', logs=logs)
    
class RemoveLogs(BaseHandler):
    def GET(self):
        query = DeliverLog.all()
        query.filter('datetime < ', datetime.datetime.utcnow() - datetime.timedelta(days=25))
        logs = query.fetch(1000)
        c = len(logs)
        db.delete(logs)
        
        for user in KeUser.all():
            if user.expires and (user.expires < datetime.datetime.utcnow()):
                user.enable_send = False
                user.put()
        
        return "%s lines log removed.<br />" % c

#class FeedBack(BaseHandler):
#    def GET(self):
#        return jjenv.get_template("feedback.html").render(nickname=session.username,
#            title='Feedback',current='feedback')

class Test(BaseHandler):
    def GET(self):
        s = ''
        for d in os.environ:
            s += "<pre><p>" + str(d).rjust(28) + " | " + str(os.environ[d]) + "</p></pre>"
        return s

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
  "/mgrpwd", "AdminMgrPwd",
  "/delaccount", "DelAccount",
  "/my", "MySubscription",
  "/subscribe/(.*)", "Subscribe",
  "/unsubscribe/(.*)", "Unsubscribe",
  "/delfeed/(.*)", "DelFeed",
  "/setting", "Setting",
  "/admin","Admin",
  "/renew", "Renew",
  "/deliver", "Deliver",
  "/worker", "Worker",
  "/logs", "Mylogs",
  "/removelogs", "RemoveLogs",
  "/test", "Test",
  #"/feedback", "FeedBack",
)

app = web.application(urls, globals())
store = MemcacheStore(memcache)
session = web.session.Session(app, store, initializer={'username':'','login':0})
jjenv = jinja2.Environment(loader=jinja2.FileSystemLoader('templates'),
                            extensions=["jinja2.ext.do",])
jjenv.filters['filesizeformat'] = fix_filesizeformat

app = app.wsgifunc()
