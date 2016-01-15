#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Author:
# cdhigh <https://github.com/cdhigh>
#Contributors:
# rexdf <https://github.com/rexdf>

from google.appengine.ext import db
from google.appengine.api import memcache
from apps.utils import ke_encrypt,ke_decrypt

#--------------db models----------------
class Book(db.Model):
    title = db.StringProperty(required=True)
    description = db.StringProperty()
    users = db.StringListProperty()
    builtin = db.BooleanProperty()
    needs_subscription = db.BooleanProperty() #是否需要登陆网页
    separate = db.BooleanProperty() #是否单独推送
    
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
    secret_key = db.StringProperty()
    kindle_email = db.StringProperty()
    enable_send = db.BooleanProperty()
    send_days = db.StringListProperty()
    send_time = db.IntegerProperty()
    timezone = db.IntegerProperty()
    book_type = db.StringProperty()
    device = db.StringProperty()
    expires = db.DateTimeProperty()
    ownfeeds = db.ReferenceProperty(Book) # 每个用户都有自己的自定义RSS
    use_title_in_feed = db.BooleanProperty() # 文章标题优先选择订阅源中的还是网页中的
    titlefmt = db.StringProperty() #在元数据标题中添加日期的格式
    merge_books = db.BooleanProperty() #是否合并书籍成一本
    
    share_fuckgfw = db.BooleanProperty() #归档和分享时是否需要翻墙
    evernote = db.BooleanProperty() #是否分享至evernote
    evernote_mail = db.StringProperty() #evernote邮件地址
    wiz = db.BooleanProperty() #为知笔记
    wiz_mail = db.StringProperty()
    xpocket = db.BooleanProperty(default=False) #send to add@getpocket.com
    xpocket_access_token = db.StringProperty(default='')
    xpocket_acc_token_hash = db.StringProperty(default='')
    xweibo = db.BooleanProperty()
    tweibo = db.BooleanProperty()
    facebook = db.BooleanProperty() #分享链接到facebook
    twitter = db.BooleanProperty()
    tumblr = db.BooleanProperty()
    browser = db.BooleanProperty()
    
    @property
    def whitelist(self):
        return WhiteList.all().filter('user = ', self.key())
    
    @property
    def urlfilter(self):
        return UrlFilter.all().filter('user = ', self.key())
    
    def subscription_info(self, title):
        "获取此账号对应的书籍的网站登陆信息"
        return SubscriptionInfo.all().filter('user = ', self.key()).filter('title = ', title).get()
        
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
    
class SubscriptionInfo(db.Model):
    title = db.StringProperty()
    account = db.StringProperty()
    encrypted_pwd = db.StringProperty()
    user = db.ReferenceProperty(KeUser)
    
    @property
    def password(self):
        return ke_decrypt(self.encrypted_pwd, self.user.secret_key)
        
    @password.setter
    def password(self, pwd):
        self.encrypted_pwd = ke_encrypt(pwd, self.user.secret_key)
        