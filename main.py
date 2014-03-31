#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#中文讨论贴：http://www.hi-pda.com/forum/viewthread.php?tid=1213082

__Version__ = "1.11.0"
__Author__ = "cdhigh"

import os, datetime, logging, __builtin__, hashlib, time
from collections import OrderedDict, defaultdict
import gettext
import re

# for debug
# 本地启动调试服务器：python.exe dev_appserver.py c:\kindleear
IsRunInLocal = (os.environ.get('SERVER_SOFTWARE', '').startswith('Development'))
log = logging.getLogger()
__builtin__.__dict__['default_log'] = log
__builtin__.__dict__['IsRunInLocal'] = IsRunInLocal

supported_languages = ['en','zh-cn','tr-tr'] #不支持的语种则使用第一个语言
#gettext.install('lang', 'i18n', unicode=True) #for calibre startup

import web
import jinja2
from bs4 import BeautifulSoup
from google.appengine.api import mail
from google.appengine.ext import db
from google.appengine.api import taskqueue
from google.appengine.api import memcache
from google.appengine.runtime.apiproxy_errors import (OverQuotaError,
                                                DeadlineExceededError)
from google.appengine.api.mail_errors import (InvalidSenderError,
                                           InvalidAttachmentTypeError)

from config import *
from lib.makeoeb import *
from lib.memcachestore import MemcacheStore
from books import BookClasses, BookClass
from books.base import BaseFeedBook, UrlEncoding, BaseUrlBook

#reload(sys)
#sys.setdefaultencoding('utf-8')

log.setLevel(logging.INFO if IsRunInLocal else logging.WARN)

def local_time(fmt="%Y-%m-%d %H:%M", tz=TIMEZONE):
    return (datetime.datetime.utcnow()+datetime.timedelta(hours=tz)).strftime(fmt)

def hide_email(email):
    """ 隐藏真实email地址，使用星号代替部分字符 """
    if not email or '@' not in email:
        return email
    email = email.split('@')
    if len(email[0]) < 4:
        return email[0][0] + '**@' + email[-1]
    to = email[0][0:2] + ''.join(['*' for s in email[0][2:-1]]) + email[0][-1]
    return to + '@' + email[-1]
    
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
        return Feed.all().filter('book = ', self.key()).order('time')
        
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
    merge_books = db.BooleanProperty() #是否合并书籍成一本
    
    share_fuckgfw = db.BooleanProperty() #归档和分享时是否需要翻墙
    evernote = db.BooleanProperty() #是否分享至evernote
    evernote_mail = db.StringProperty() #evernote邮件地址
    wiz = db.BooleanProperty() #为知笔记
    wiz_mail = db.StringProperty()
    xweibo = db.BooleanProperty()
    tweibo = db.BooleanProperty()
    facebook = db.BooleanProperty() #分享链接到facebook
    twitter = db.BooleanProperty()
    tumblr = db.BooleanProperty()
    broswer = db.BooleanProperty()
    
    @property
    def whitelist(self):
        return WhiteList.all().filter('user = ', self.key())
    
    @property
    def urlfilter(self):
        return UrlFilter.all().filter('user = ', self.key())
    
class Feed(db.Model):
    book = db.ReferenceProperty(Book)
    title = db.StringProperty()
    url = db.StringProperty()
    isfulltext = db.BooleanProperty()
    time = db.DateTimeProperty() #源被加入的时间，用于排序
    
class DeliverLog(db.Model):
    username = db.StringProperty()
    to = db.StringProperty()
    size = db.IntegerProperty()
    time = db.StringProperty()
    datetime = db.DateTimeProperty()
    book = db.StringProperty()
    status = db.StringProperty()

class WhiteList(db.Model):
    mail = db.StringProperty()
    user = db.ReferenceProperty(KeUser)

class UrlFilter(db.Model):
    url = db.StringProperty()
    user = db.ReferenceProperty(KeUser)
    
for book in BookClasses():  #添加内置书籍
    if memcache.get(book.title): #使用memcache加速
        continue
    b = Book.all().filter("title = ", book.title).get()
    if not b:
        b = Book(title=book.title,description=book.description,builtin=True)
        b.put()
        memcache.add(book.title, book.description, 86400)

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
            raise web.seeother(r'/login')
    
    @classmethod
    def getcurrentuser(self):
        self.login_required()
        u = KeUser.all().filter("name = ", session.username).get()
        if not u:
            raise web.seeother(r'/login')
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
        if booktype:
            if filewithtime:
                filename = "%s(%s).%s"%(basename,lctime,booktype)
            else:
                filename = "%s.%s"%(basename,booktype)
        else:
            filename = basename
            
        for i in range(SENDMAIL_RETRY_CNT+1):
            try:
                mail.send_mail(SRC_EMAIL, to, "KindleEar %s" % lctime, "Deliver from KindlerEar",
                    attachments=[(filename, attachment),])
            except OverQuotaError as e:
                default_log.warn('overquota when sendmail to %s:%s' % (to, str(e)))
                self.deliverlog(name, to, title, len(attachment), tz=tz, status='over quota')
                break
            except InvalidSenderError as e:
                default_log.warn('UNAUTHORIZED_SENDER when sendmail to %s:%s' % (to, str(e)))
                self.deliverlog(name, to, title, len(attachment), tz=tz, status='wrong SRC_EMAIL')
                break
            except InvalidAttachmentTypeError as e: #继续发送一次
                if SENDMAIL_ALL_POSTFIX:
                    filename = filename.replace('.', '_')
                    title = title.replace('.', '_')
                else:
                    default_log.warn('InvalidAttachmentTypeError when sendmail to %s:%s' % (to, str(e)))
                    self.deliverlog(name, to, title, len(attachment), tz=tz, status='invalid postfix')
                    break
            except DeadlineExceededError as e:
                if i < SENDMAIL_RETRY_CNT:
                    default_log.warn('timeout when sendmail to %s:%s, retry!' % (to, str(e)))
                    time.sleep(5)
                else:
                    default_log.warn('timeout when sendmail to %s:%s, abort!' % (to, str(e)))
                    self.deliverlog(name, to, title, len(attachment), tz=tz, status='timeout')
                    break
            except Exception as e:
                default_log.warn('sendmail to %s failed:%s.<%s>' % (to, str(e), type(e)))
                self.deliverlog(name, to, title, len(attachment), tz=tz, status='send failed')
                break
            else:
                self.deliverlog(name, to, title, len(attachment), tz=tz)
                break
    
    @classmethod
    def SendHtmlMail(self, name, to, title, html, attachments, tz=TIMEZONE):
        for i in range(SENDMAIL_RETRY_CNT+1):
            try:
                if attachments:
                    mail.send_mail(SRC_EMAIL, to, title, "Deliver from KindlerEar, refers to html part.",
                        html=html, attachments=attachments)
                else:
                    mail.send_mail(SRC_EMAIL, to, title, "Deliver from KindlerEar, refers to html part.",
                        html=html)
            except OverQuotaError as e:
                default_log.warn('overquota when sendmail to %s:%s' % (to, str(e)))
                self.deliverlog(name, to, title, 0, tz=tz, status='over quota')
                break
            except InvalidSenderError as e:
                default_log.warn('UNAUTHORIZED_SENDER when sendmail to %s:%s' % (to, str(e)))
                self.deliverlog(name, to, title, 0, tz=tz, status='wrong SRC_EMAIL')
                break
            except InvalidAttachmentTypeError as e:
                default_log.warn('InvalidAttachmentTypeError when sendmail to %s:%s' % (to, str(e)))
                self.deliverlog(name, to, title, 0, tz=tz, status='invalid postfix')
                break
            except DeadlineExceededError as e:
                if i < SENDMAIL_RETRY_CNT:
                    default_log.warn('timeout when sendmail to %s:%s, retry!' % (to, str(e)))
                    time.sleep(5)
                else:
                    default_log.warn('timeout when sendmail to %s:%s, abort!' % (to, str(e)))
                    self.deliverlog(name, to, title, 0, tz=tz, status='timeout')
                    break
            except Exception as e:
                default_log.warn('sendmail to %s failed:%s.<%s>' % (to, str(e), type(e)))
                self.deliverlog(name, to, title, 0, tz=tz, status='send failed')
                break
            else:
                if attachments:
                    size = len(html) + sum([len(c) for f,c in attachments])
                else:
                    size = len(html)
                self.deliverlog(name, to, title, size, tz=tz)
                break
    
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
            user.merge_books = bool(web.input().get('mergebooks'))
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

class AdvWhiteList(BaseHandler):
    """ 设置邮件白名单 """
    def GET(self):
        user = self.getcurrentuser()
        return self.render('advwhitelist.html',"White List",current='advsetting',
            user=user,advcurr='whitelist')
        
    def POST(self):
        user = self.getcurrentuser()
        
        wlist = web.input().get('wlist')
        if wlist:
            WhiteList(mail=wlist,user=user).put()
        raise web.seeother('')
        
class AdvShare(BaseHandler):
    """ 设置归档和分享配置项 """
    def GET(self):
        user = self.getcurrentuser()
        current = 'advsetting'
        advcurr = 'share'
        savetoevernote = SAVE_TO_EVERNOTE
        savetowiz = SAVE_TO_WIZ
        shareonxweibo = SHARE_ON_XWEIBO
        shareontweibo = SHARE_ON_TWEIBO
        shareonfacebook = SHARE_ON_FACEBOOK
        shareontwitter = SHARE_ON_TWITTER
        shareontumblr = SHARE_ON_TUMBLR
        openinbroswer = OPEN_IN_BROSWER
        args = locals()
        args.pop('self')
        return self.render('advshare.html',"Share",**args)
        
    def POST(self):
        user = self.getcurrentuser()
        
        fuckgfw = bool(web.input().get('fuckgfw'))
        evernote = bool(web.input().get('evernote'))
        evernote_mail = web.input().get('evernote_mail', '')
        if not evernote_mail:
            evernote = False
        wiz = bool(web.input().get('wiz'))
        wiz_mail = web.input().get('wiz_mail', '')
        if not wiz_mail:
            wiz = False
        xweibo = bool(web.input().get('xweibo'))
        tweibo = bool(web.input().get('tweibo'))
        facebook = bool(web.input().get('facebook'))
        twitter = bool(web.input().get('twitter'))
        tumblr = bool(web.input().get('tumblr'))
        broswer = bool(web.input().get('broswer'))
        
        user.share_fuckgfw = fuckgfw
        user.evernote = evernote
        user.evernote_mail = evernote_mail
        user.wiz = wiz
        user.wiz_mail = wiz_mail
        user.xweibo = xweibo
        user.tweibo = tweibo
        user.facebook = facebook
        user.twitter = twitter
        user.tumblr = tumblr
        user.broswer = broswer
        user.put()
        
        raise web.seeother('')
        
class AdvUrlFilter(BaseHandler):
    """ 设置URL过滤器 """
    def GET(self):
        user = self.getcurrentuser()
        return self.render('advurlfilter.html',"Url Filter",current='advsetting',
            user=user,advcurr='urlfilter')
        
    def POST(self):
        user = self.getcurrentuser()
        
        url = web.input().get('url')
        if url:
            UrlFilter(url=url,user=user).put()
        raise web.seeother('')
        
class AdvDel(BaseHandler):
    #删除白名单或URL过滤器项目
    def GET(self):
        user = self.getcurrentuser()
        delurlid = web.input().get('delurlid')
        delwlist = web.input().get('delwlist')
        if delurlid and delurlid.isdigit():
            flt = UrlFilter.get_by_id(int(delurlid))
            if flt:
                flt.delete()
            raise web.seeother('/advurlfilter')
        if delwlist and delwlist.isdigit():
            wlist = WhiteList.get_by_id(int(delwlist))
            if wlist:
                wlist.delete()
            raise web.seeother('/advwhitelist')
        
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
                        send_time=7,timezone=TIMEZONE,book_type="mobi",
                        ownfeeds=myfeeds,merge_books=False)
                    au.expires = datetime.datetime.utcnow()+datetime.timedelta(days=180)
                    au.put()
                    users = KeUser.all() if user.name == 'admin' else None
                    tips = _("Add a account success!")
            return self.render('admin.html',"Admin",
                current='admin', user=user, users=users,actips=tips)
        else:
            return self.GET()
       
class Login(BaseHandler):
    def CheckAdminAccount(self):
        #判断管理员账号是否存在
        #如果管理员账号不存在，创建一个，并返回False，否则返回True
        u = KeUser.all().filter("name = ", 'admin').get()
        if not u:            
            myfeeds = Book(title=MY_FEEDS_TITLE,description=MY_FEEDS_DESC,
                    builtin=False,keep_image=True,oldest_article=7)
            myfeeds.put()
            au = KeUser(name='admin',passwd=hashlib.md5('admin').hexdigest(),
                kindle_email='',enable_send=False,send_time=8,timezone=TIMEZONE,
                book_type="mobi",expires=None,ownfeeds=myfeeds,merge_books=False)
            au.put()
            return False
        else:
            return True
            
    def GET(self):
        # 第一次登陆时如果没有管理员帐号，
        # 则增加一个管理员帐号admin，密码admin，后续可以修改密码
        tips = ''
        if not self.CheckAdminAccount():
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
        
        self.CheckAdminAccount() #确认管理员账号是否存在
        
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
                
            #修正从1.6.15之前的版本升级过来后自定义RSS丢失的问题
            for fd in Feed.all():
                if not fd.time:
                    fd.time = datetime.datetime.utcnow()
                    fd.put()
            
            #1.7新增各用户独立的白名单和URL过滤器，这些处理是为了兼容以前的版本
            if name == 'admin':
                for wl in WhiteList.all():
                    if not wl.user:
                        wl.user = u
                        wl.put()
                for uf in UrlFilter.all():
                    if not uf.user:
                        uf.user = u
                        uf.put()
                        
            raise web.seeother(r'/my')
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
        Feed(title=title,url=url,book=user.ownfeeds,isfulltext=isfulltext,
            time=datetime.datetime.utcnow()).put()
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
        param = {"u":usr.name, "id":bookid}
        
        if usr.merge_books:
            self.queue2push[usr.name].append(str(bookid))
        else:
            taskqueue.add(url='/worker',queue_name="deliverqueue1",method='GET',
                params=param)
        
    def flushqueue(self):
        for name in self.queue2push:
            param = {'u':name, 'id':','.join(self.queue2push[name])}
            taskqueue.add(url='/worker',queue_name="deliverqueue1",method='GET',
                params=param)
        self.queue2push = defaultdict(list)
        
    def GET(self):
        username = web.input().get('u')
        id = web.input().get('id') #for debug
        
        self.queue2push = defaultdict(list)
        
        books = Book.all()
        if username: #现在投递，不判断时间和星期
            sent = []
            books2push = Book.get_by_id(int(id)) if id and id.isdigit() else None
            books2push = [books2push] if books2push else books
            for book in books2push:
                if not id and username not in book.users:
                    continue
                user = KeUser.all().filter("name = ", username).get()
                if user and user.kindle_email:
                    self.queueit(user, book.key().id())
                    sent.append(book.title)
            self.flushqueue()
            if len(sent):
                tips = _("Book(s) (%s) put to queue!") % u', '.join(sent)
            else:
                tips = _("No book to deliver!")
            return self.render('autoback.html', "Delivering",tips=tips)
        
        #定时cron调用
        sentcnt = 0
        for book in books:
            if not book.users: #没有用户订阅此书
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
        self.flushqueue()
        return "Put <strong>%d</strong> books to queue!" % sentcnt
    
class Worker(BaseHandler):
    """ 实际下载文章和生成电子书并且发送邮件 """
    def GET(self):
        username = web.input().get("u")
        bookid = web.input().get("id")
        
        user = KeUser.all().filter("name = ", username).get()
        if not user:
            return "User not exist!<br />"
        
        to = user.kindle_email
        booktype = user.book_type
        titlefmt = user.titlefmt
        tz = user.timezone
        
        bookid = bookid.split(',') if ',' in bookid else [bookid]
        bks = []
        for id in bookid:
            try:
                bks.append(Book.get_by_id(int(id)))
            except:
                continue
                #return "id of book is invalid or book not exist!<br />"
        
        if len(bks) == 0:
            return "No have book to push!"
        elif len(bks) == 1:
            book4meta = BookClass(bks[0].title) if bks[0].builtin else bks[0]
        else: #多本书合并推送时使用“自定义RSS”的元属性
            book4meta = user.ownfeeds
        
        if not book4meta:
            return "No have book to push.<br />"
            
        opts = oeb = None
        
        # 创建 OEB
        global log
        opts = getOpts()
        oeb = CreateOeb(log, None, opts)
        title = "%s %s" % (book4meta.title, local_time(titlefmt, tz)) if titlefmt else book4meta.title
        
        setMetaData(oeb, title, book4meta.language, local_time("%Y-%m-%d",tz), 'KindleEar')
        oeb.container = ServerContainer(log)
        
        #guide
        if len(bks)==1 and bks[0].builtin:
            mhfile = book4meta.mastheadfile
            coverfile = book4meta.coverfile
        else:
            mhfile = DEFAULT_MASTHEAD
            coverfile = DEFAULT_COVER
        
        if mhfile:
            id_, href = oeb.manifest.generate('masthead', mhfile) # size:600*60
            oeb.manifest.add(id_, href, MimeFromFilename(mhfile))
            oeb.guide.add('masthead', 'Masthead Image', href)
        
        if coverfile:
            id_, href = oeb.manifest.generate('cover', coverfile)
            item = oeb.manifest.add(id_, href, MimeFromFilename(coverfile))
            oeb.guide.add('cover', 'Cover', href)
            oeb.metadata.add('cover', id_)
        
        itemcnt,imgindex = 0,0
        sections = OrderedDict()
        toc_thumbnails = {} #map img-url -> manifest-href
        for bk in bks:
            if bk.builtin:
                book = BookClass(bk.title)
                if not book:
                    log.warn('not exist book <%s>' % bk.title)
                    continue
                book = book(imgindex=imgindex)
                book.url_filters = [flt.url for flt in user.urlfilter]
            else: # 自定义RSS
                if bk.feedscount == 0:
                    continue  #return "the book has no feed!<br />"
                book = BaseFeedBook(imgindex=imgindex)
                book.title = bk.title
                book.description = bk.description
                book.language = bk.language
                book.keep_image = bk.keep_image
                book.oldest_article = bk.oldest_article
                book.fulltext_by_readability = True
                feeds = bk.feeds
                book.feeds = [(feed.title, feed.url, feed.isfulltext) for feed in feeds]
                book.url_filters = [flt.url for flt in user.urlfilter]            
            
            # 对于html文件，变量名字自文档,thumbnail为文章第一个img的url
            # 对于图片文件，section为图片mime,url为原始链接,title为文件名,content为二进制内容,thumbail仅当article的第第一个img为True
            for sec_or_media, url, title, content, brief, thumbnail in book.Items(opts,user):
                if not sec_or_media or not title or not content:
                    continue
                
                if sec_or_media.startswith(r'image/'):
                    id_, href = oeb.manifest.generate(id='img', href=title)
                    item = oeb.manifest.add(id_, href, sec_or_media, data=content)
                    if thumbnail:
                        toc_thumbnails[url] = href
                    imgindex += 1
                else:
                    #id, href = oeb.manifest.generate(id='feed', href='feed%d.html'%itemcnt)
                    #item = oeb.manifest.add(id, href, 'application/xhtml+xml', data=content)
                    #oeb.spine.add(item, True)
                    sections.setdefault(sec_or_media, [])
                    sections[sec_or_media].append((title, '', brief, thumbnail, content))
                    itemcnt += 1
                    
        if itemcnt > 0:
            #-------------------add by rexdf-----------
            body_pat=r'(?<=<body>).*?(?=</body>)'
            body_ex = re.compile(body_pat,re.M|re.S)
            num_articles=1
            num_sections=0

            ncx_toc = []
            #html_toc_2 secondary toc
            html_toc_2 = []
            name_section_list = []
            for sec in sections.keys():
                htmlcontent = ['<html><head><title>%s</title><style type="text/css">.pagebreak{page-break-before: always;}</style></head><body>' % (sec)]
                secondary_toc_list = []
                first_flag=False
                sec_toc_thumbnail = None
                for title, a, brief, thumbnail, content in sections[sec]:
                    if first_flag:
                        htmlcontent.append("<div id='%d' class='pagebreak'></div>" % (num_articles)) #insert anchor && pagebreak
                    else:
                        htmlcontent.append("<div id='%d'></div>" % (num_articles)) #insert anchor && pagebreak
                        first_flag=True
                        if thumbnail:
                            sec_toc_thumbnail = thumbnail
                    body_obj = re.search(body_ex, content)
                    if body_obj:
                        htmlcontent.append(body_obj.group()) #insect article
                        secondary_toc_list.append((title, num_articles, brief, thumbnail))
                        num_articles += 1
                    else:
                        htmlcontent.pop()
                htmlcontent.append('</body></html>')

                #add section.html to maninfest and spine
                #We'd better not use id as variable. It's a python builtin function.
                id_, href = oeb.manifest.generate(id='feed', href='feed%d.html'%num_sections)
                item = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=''.join(htmlcontent))
                oeb.spine.add(item, True)
                ncx_toc.append(('section',sec,href,'',sec_toc_thumbnail)) #Sections name && href && no brief

                #generate the secondary toc
                if GENERATE_HTML_TOC:
                    html_toc_ = ['<html><head><title>toc</title></head><body><h2>%s</h2><ol>' % (sec)]
                for title, anchor, brief, thumbnail in secondary_toc_list:
                    if GENERATE_HTML_TOC:
                        html_toc_.append('&nbsp;&nbsp;&nbsp;&nbsp;<li><a href="%s#%d">%s</a></li><br />'%(href, anchor, title))
                    ncx_toc.append(('article',title, '%s#%d'%(href,anchor), brief, thumbnail)) # article name & article href && article brief
                if GENERATE_HTML_TOC:
                    html_toc_.append('</ol></body></html>')
                    html_toc_2.append(html_toc_)
                    name_section_list.append(sec)

                num_sections += 1

            if GENERATE_HTML_TOC:
                #Generate HTML TOC for Calibre mostly
                ##html_toc_1 top level toc
                html_toc_1 = [u'<html><head><title>Table Of Contents</title></head><body><h2>%s</h2><ul>'%(TABLE_OF_CONTENTS)]
                html_toc_1_ = []
                #We need index but not reversed()
                for a in xrange(len(html_toc_2)-1,-1,-1):
                    #Generate Secondary HTML TOC
                    id_, href = oeb.manifest.generate(id='section', href='toc_%d.html' % (a))
                    item = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=" ".join(html_toc_2[a]))
                    oeb.spine.insert(0, item, True)
                    html_toc_1_.append('&nbsp;&nbsp;&nbsp;&nbsp;<li><a href="%s">%s</a></li><br />'%(href,name_section_list[a]))
                html_toc_2 = []
                for a in reversed(html_toc_1_):
                    html_toc_1.append(a)
                html_toc_1_ = []
                html_toc_1.append('</ul></body></html>')
                #Generate Top HTML TOC
                id_, href = oeb.manifest.generate(id='toc', href='toc.html')
                item = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=''.join(html_toc_1))
                oeb.guide.add('toc', 'Table of Contents', href)
                oeb.spine.insert(0, item, True)

            #Generate NCX TOC for Kindle
            po=1 
            toc=oeb.toc.add(unicode(oeb.metadata.title[0]), oeb.spine[0].href, id='periodical', klass='periodical', play_order=po)
            po += 1
            for ncx in ncx_toc:
                if ncx[0] == 'section':
                    sectoc = toc.add(unicode(ncx[1]), ncx[2], klass='section', play_order=po, id='Main-section-%d'%po, toc_thumbnail=toc_thumbnails[ncx[4]] if GENERATE_TOC_THUMBNAIL and ncx[4] else None)
                else:
                    sectoc.add(unicode(ncx[1]), ncx[2], description=ncx[3] if ncx[3] else None, klass='article', play_order=po, id='article-%d'%po, toc_thumbnail=toc_thumbnails[ncx[4]] if GENERATE_TOC_THUMBNAIL and ncx[4] else None)
                po += 1
            #----------------end----------------

            oIO = byteStringIO()
            o = EPUBOutput() if booktype == "epub" else MOBIOutput()
            o.convert(oeb, oIO, opts, log)
            self.SendToKindle(username, to, book4meta.title, booktype, str(oIO.getvalue()), tz)
            rs = "%s(%s).%s Sent!"%(book4meta.title, local_time(tz=tz), booktype)
            log.info(rs)
            return rs
        else:
            self.deliverlog(username, to, book4meta.title, 0, status='nonews',tz=tz)
            rs = "No new feeds."
            log.info(rs)
            return rs

class Url2Book(BaseHandler):
    """ 抓取指定链接，转换成附件推送 """
    def GET(self):
        username = web.input().get("u")
        urls = web.input().get("urls")
        subject = web.input().get("subject")
        to = web.input().get("to")
        language = web.input().get("lng")
        keepimage = bool(web.input().get("keepimage") == '1')
        booktype = web.input().get("type", "mobi")
        tz = int(web.input().get("tz", TIMEZONE))
        if not all((username,urls,subject,to,language,booktype,tz)):
            return "Some parameter missing!<br />"
        
        global log
        
        if booktype == 'Download': #直接下载电子书并推送
            from lib.filedownload import Download
            for url in urls.split('|'):
                dlinfo, filename, content = Download(url)
                #如果标题已经给定了文件名，则使用标题文件名
                if '.' in subject and (1 < len(subject.split('.')[-1]) < 5):
                    filename = subject
                    
                if content:
                    self.SendToKindle(username, to, filename, '', content, tz)
                else:
                    if not dlinfo:
                        dlinfo = 'download failed'
                    self.deliverlog(username, to, filename, 0, status=dlinfo,tz=tz)
                log.info("%s Sent!" % filename)
            return "%s Sent!" % filename
            
        user = KeUser.all().filter("name = ", username).get()
        if not user or not user.kindle_email:
            return "User not exist!<br />"
            
        book = BaseUrlBook()
        book.title = book.description = subject
        book.language = language
        book.keep_image = keepimage
        book.network_timeout = 60
        book.feeds = [(subject,url) for url in urls.split('|')]
        book.url_filters = [flt.url for flt in user.urlfilter]
        
        opts = oeb = None
        
        # 创建 OEB
        opts = getOpts()
        oeb = CreateOeb(log, None, opts)
        oeb.container = ServerContainer(log)
        
        if len(book.feeds) > 1:
            setMetaData(oeb, subject, language, local_time(tz=tz))
            id, href = oeb.manifest.generate('masthead', DEFAULT_MASTHEAD)
            oeb.manifest.add(id, href, MimeFromFilename(DEFAULT_MASTHEAD))
            oeb.guide.add('masthead', 'Masthead Image', href)
        else:
            setMetaData(oeb, subject, language, local_time(tz=tz), pubtype='book:book:KindleEar')
        
        id, href = oeb.manifest.generate('cover', DEFAULT_COVER)
        item = oeb.manifest.add(id, href, MimeFromFilename(DEFAULT_COVER))
        oeb.guide.add('cover', 'Cover', href)
        oeb.metadata.add('cover', id)
        
        # 对于html文件，变量名字自文档
        # 对于图片文件，section为图片mime,url为原始链接,title为文件名,content为二进制内容
        itemcnt,hasimage = 0,False
        sections = {subject:[]}
        for sec_or_media, url, title, content, brief in book.Items(opts,user):
            if sec_or_media.startswith(r'image/'):
                id, href = oeb.manifest.generate(id='img', href=title)
                item = oeb.manifest.add(id, href, sec_or_media, data=content)
                itemcnt += 1
                hasimage = True
            else:
                id, href = oeb.manifest.generate(id='page', href='page.html')
                item = oeb.manifest.add(id, href, 'application/xhtml+xml', data=content)
                oeb.spine.add(item, False)
                if len(book.feeds) > 1:
                    sections[subject].append((title,item,brief))
                else:
                    oeb.toc.add(title, href)
                itemcnt += 1
            
        if itemcnt > 0:
            if len(book.feeds) > 1:
                InsertToc(oeb, sections)
            elif not hasimage: #单文章没有图片则去掉封面
                href = oeb.guide['cover'].href
                oeb.guide.remove('cover')
                item = oeb.manifest.hrefs[href]
                oeb.manifest.remove(item)
                oeb.metadata.clear('cover')
                
            oIO = byteStringIO()
            o = EPUBOutput() if booktype == "epub" else MOBIOutput()
            o.convert(oeb, oIO, opts, log)
            self.SendToKindle(username, to, book.title, booktype, str(oIO.getvalue()), tz)
            rs = "%s(%s).%s Sent!"%(book.title, local_time(tz=tz), booktype)
            log.info(rs)
            return rs
        else:
            self.deliverlog(username, to, book.title, 0, status='fetch failed',tz=tz)
            rs = "[Url2Book]Fetch url failed."
            log.info(rs)
            return rs

class Share(BaseHandler):
    """ 保存到evernote或分享到社交媒体 """
    
    SHARE_IMAGE_EMBEDDED = True
    
    def GET(self):
        import urlparse,urllib
        action = web.input().get('act')
        username = web.input().get("u")
        url = web.input().get("url")
        if not username or not url or not action:
            return "Some parameter is missing or wrong!<br />"
        
        user = KeUser.all().filter("name = ", username).get()
        if not user or not user.kindle_email:
            return "User not exist!<br />"
        
        global log
        
        url = urllib.unquote(url)
        
        #因为知乎好文章比较多，特殊处理一下知乎
        if urlparse.urlsplit(url)[1].endswith('zhihu.com'):
            url = 'http://forwarder.ap01.aws.af.cm/?k=xzSlE&t=60&u=%s'%urllib.quote(url)
            
        if action in ('evernote','wiz'): #保存至evernote/wiz
            if action=='evernote' and (not user.evernote or not user.evernote_mail):
                log.warn('No have evernote mail yet.')
                return "No have evernote mail yet."
            elif action=='wiz' and (not user.wiz or not user.wiz_mail):
                log.warn('No have wiz mail yet.')
                return "No have wiz mail yet."
                
            book = BaseUrlBook()
            book.title = book.description = action
            book.language = user.ownfeeds.language
            book.keep_image = user.ownfeeds.keep_image
            book.network_timeout = 60
            book.feeds = [(action,url)]
            book.url_filters = [flt.url for flt in user.urlfilter]
            
            attachments = [] #(filename, attachment),]
            html = ''
            title = action
            
            # 对于html文件，变量名字自文档
            # 对于图片文件，section为图片mime,url为原始链接,title为文件名,content为二进制内容
            for sec_or_media, url, title, content, brief in book.Items():
                if sec_or_media.startswith(r'image/'):
                    if self.SHARE_IMAGE_EMBEDDED:
                        attachments.append(mail.Attachment(title,
                            content,content_id='<%s>'%title))
                    else:
                        attachments.append((title,content))
                else:
                    soup = BeautifulSoup(content, 'lxml')
                    
                    #插入源链接
                    p = soup.new_tag('p', style='font-size:80%;color:grey;')
                    a = soup.new_tag('a', href=url)
                    a.string = url
                    p.string = 'origin : '
                    p.append(a)
                    soup.html.body.insert(0,p)
                    
                    if self.SHARE_IMAGE_EMBEDDED:
                        #内嵌图片标识
                        for img in soup.find_all('img', attrs={'src':True}):
                            img['src'] = 'cid:' + img['src']
                    else:
                        #标注图片位置
                        for img in soup.find_all('img', attrs={'src':True}):
                            p = soup.new_tag('p')
                            p.string = 'Image : ' + img['src']
                            img.insert_after(p)
                        
                    try:
                        title = unicode(soup.html.head.title.string)
                    except:
                        pass
                    
                    html = unicode(soup)
                    
            to = user.wiz_mail if action=='wiz' else user.evernote_mail
            if html:
                self.SendHtmlMail(username,to,title,html,attachments,user.timezone)
                info = '"%s" saved to %s (%s).' % (title,action,hide_email(to))
                log.info(info)
                web.header('Content-type', "text/html; charset=utf-8")
                info = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
                    <title>%s</title></head><body><p style="text-align:center;font-size:1.5em;">%s</p></body></html>""" % (title, info)
                return info.encode('utf-8')
            else:
                self.deliverlog(username,to,title,0,status='fetch failed',tz=user.timezone)
                log.info("[Share]Fetch url failed.")
                return "[Share]Fetch url failed."
        else:
            return "Unknown parameter 'action'!"
        
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
                    if bk.description != book.description:
                        bk.description = book.description
                        bk.put()
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
  "/advwhitelist","AdvWhiteList",
  "/advshare","AdvShare",
  "/advurlfilter","AdvUrlFilter",
  "/admin","Admin",
  "/deliver", "Deliver",
  "/worker", "Worker",
  "/url2book", "Url2Book",
  "/share", "Share",
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