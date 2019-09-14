#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Author:
# cdhigh <https://github.com/cdhigh>
#Contributors:
# rexdf <https://github.com/rexdf>
from operator import attrgetter
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api.datastore_errors import NeedIndexError
from apps.utils import ke_encrypt,ke_decrypt

#--------------db models----------------
#对应到每一个”书“，注意，同一个用户的”自定义RSS“会归到同一本书内
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
        try:
            return Feed.all().filter('book = ', self.key()).order('time')
        except NeedIndexError: #很多人不会部署，经常出现没有建立索引的情况，干脆碰到这种情况直接消耗CPU时间自己排序得了
            return sorted(Feed.all().filter("book = ", self.key()), key=attrgetter('time'))
            
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
    book_type = db.StringProperty() #mobi,epub
    device = db.StringProperty()
    expires = db.DateTimeProperty() #超过了此日期后账号自动停止推送
    ownfeeds = db.ReferenceProperty(Book) # 每个用户都有自己的自定义RSS
    use_title_in_feed = db.BooleanProperty() # 文章标题优先选择订阅源中的还是网页中的
    titlefmt = db.StringProperty() #在元数据标题中添加日期的格式
    merge_books = db.BooleanProperty() #是否合并书籍成一本
    
    share_fuckgfw = db.BooleanProperty() #归档和分享时是否需要翻墙
    evernote = db.BooleanProperty() #是否分享至evernote
    evernote_mail = db.StringProperty() #evernote邮件地址
    wiz = db.BooleanProperty() #为知笔记
    wiz_mail = db.StringProperty()
    pocket = db.BooleanProperty(default=False) #send to add@getpocket.com
    pocket_access_token = db.StringProperty(default='')
    pocket_acc_token_hash = db.StringProperty(default='')
    instapaper = db.BooleanProperty()
    instapaper_username = db.StringProperty()
    instapaper_password = db.StringProperty()
    xweibo = db.BooleanProperty()
    tweibo = db.BooleanProperty()
    facebook = db.BooleanProperty() #分享链接到facebook
    twitter = db.BooleanProperty()
    tumblr = db.BooleanProperty()
    browser = db.BooleanProperty()
    qrcode = db.BooleanProperty() #是否在文章末尾添加文章网址的QRCODE
    cover = db.BlobProperty() #保存各用户的自定义封面图片二进制内容
    css_content = db.TextProperty() #added 2019-09-12 保存用户上传的css样式表
    
    book_mode = db.StringProperty() #added 2017-08-31 书籍模式，'periodical'|'comic'，漫画模式可以直接全屏
    expiration_days = db.IntegerProperty() #added 2018-01-07 账号超期设置值，0为永久有效
    remove_hyperlinks = db.StringProperty() #added 2018-05-02 去掉文本或图片上的超链接{'' | 'image' | 'text' | 'all'}

    sgenable = db.BooleanProperty() #是否使用SendGrid
    sgapikey = db.StringProperty() #SendGrid API Key
    
    @property
    def whitelist(self):
        return WhiteList.all().filter('user = ', self.key())
    
    @property
    def urlfilter(self):
        return UrlFilter.all().filter('user = ', self.key())
    
    #获取此账号对应的书籍的网站登陆信息
    def subscription_info(self, title):
        return SubscriptionInfo.all().filter('user = ', self.key()).filter('title = ', title).get()

#自定义RSS订阅源
class Feed(db.Model):
    book = db.ReferenceProperty(Book)
    title = db.StringProperty()
    url = db.StringProperty()
    isfulltext = db.BooleanProperty()
    time = db.DateTimeProperty() #源被加入的时间，用于排序

#书籍的推送历史记录
class DeliverLog(db.Model):
    username = db.StringProperty()
    to = db.StringProperty()
    size = db.IntegerProperty()
    time = db.StringProperty()
    datetime = db.DateTimeProperty()
    book = db.StringProperty()
    status = db.StringProperty()

#added 2017-09-01 记录已经推送的期数/章节等信息，可用来处理连载的漫画/小说等
class LastDelivered(db.Model):
    username = db.StringProperty()
    bookname = db.StringProperty()
    num = db.IntegerProperty(default=0) #num和record可以任选其一用来记录，或使用两个配合都可以
    record = db.StringProperty(default='') #record同时也用做在web上显示
    datetime = db.DateTimeProperty()
    
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

#Shared RSS links from other users [for kindleear.appspot.com only]
class SharedRss(db.Model):
    title = db.StringProperty()
    url = db.StringProperty()
    isfulltext = db.BooleanProperty()
    category = db.StringProperty()
    creator = db.StringProperty()
    created_time = db.DateTimeProperty()
    subscribed = db.IntegerProperty(default=0) #for sort
    invalid_report_days = db.IntegerProperty(default=0) #some one reported it is a invalid link
    last_invalid_report_time = db.DateTimeProperty() #a rss will be deleted after some days of reported_invalid
    
    #return all categories in database
    @classmethod
    def categories(self):
        return [item.category for item in db.GqlQuery('SELECT DISTINCT category FROM SharedRss')]
    
#Buffer for category of shared rss [for kindleear.appspot.com only]
class SharedRssCategory(db.Model):
    name = db.StringProperty()
    last_updated = db.DateTimeProperty() #for sort
