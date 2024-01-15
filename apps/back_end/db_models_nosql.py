#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#datastore数据库结构定义，使用经过修改的datastorm ODM库管理
#datastorm 源 <https://github.com/JavierLuna/datastorm>
#datastorm 文档 <https://datastorm.readthedocs.io/en/latest/>
#cloud datastore 文档 <https://cloud.google.com/datastore/docs/concepts/queries>
#使用的datastorm是自己修改过的，接口尽量和peewee保持一致，并且尽量不要使用peewee的高级特性
#可以使用Key实例的 to_legacy_urlsafe().decode()/from_legacy_urlsafe() 来模拟SQL的外键
#根据以前的经验，经常出现有网友部署时没有成功建立数据库索引，所以现在排序在应用内处理，数据量不大
#Author: cdhigh <https://github.com/cdhigh/KindleEar>

from apps.utils import ke_encrypt, ke_decrypt
from config import DATABASE_ENGINE, DATABASE_HOST, DATABASE_PORT, DATABASE_USERNAME, DATABASE_PASSWORD, DATABASE_NAME

if DATABASE_ENGINE == "datastore":
    from datastorm import DataStorm, fields
    from google.cloud.datastore import Key as DataStoreKey
    dbInstance = DataStorm(project=APP_ID)
else:
    raise Exception("database engine '{}' not supported yet".format(DATABASE_ENGINE))

#调用此函数正式连接到数据库（打开数据库）
def ConnectToDatabase():
    pass

#关闭数据库连接
def CloseDatabase():
    pass

#数据表的共同基类
class MyBaseModel(dbInstance.DSEntity):
    @classmethod
    def get_all(cls, *query):
        return cls.select().where(*query).execute()

    @classmethod
    def get_one(cls, *query):
        return cls.select().where(*query).execute()

    #和peewee一致
    @classmethod
    def get_by_id_or_none(cls, id_):
        return cls.get_by_key(id_)

    #返回Key/Id的字符串表达
    @property
    def key_or_id_string(self):
        return self.key.to_legacy_urlsafe().decode()

    #做外键使用的字符串或ID
    @property
    def reference_key_or_id(self):
        return self.key.to_legacy_urlsafe().decode()

#--------------db models----------------
#对应到每一个”书“，注意，同一个用户的”自定义RSS“会归到同一本书内
class Book(MyBaseModel):
    __kind__ = "Book" #类似SQL的表名

    title = fields.StringField()
    description = fields.StringField()
    users = fields.ListField()   #有哪些账号订阅了这本书
    builtin = fields.BooleanField()
    needs_subscription = fields.BooleanField() #是否需要登陆网页
    separate = fields.BooleanField() #是否单独推送
    
    #====自定义书籍
    language = fields.StringField()
    masthead_file = fields.StringField() # GIF 600*60
    cover_file = fields.StringField()
    keep_image = fields.BooleanField()
    oldest_article = fields.IntField()
    
    #这三个属性只有自定义RSS才有意义
    @property
    def feeds(self):
        myKey = self.key.to_legacy_urlsafe().decode()
        return Feed.select().where(Feed.book == myKey).order(Feed.time).execute()

    @property
    def feedsCount(self):
        #为简单起见，先不使用聚合查询了，就用列表统计
        #如果以后想改，可以参考：<https://cloud.google.com/datastore/docs/aggregation-queries>
        return len(list(self.feeds))
        
    #这个属性对于自定义RSS才有意思，才有Owner，其他的书籍只有订阅者，没有Owner
    #所以只有最多一个Owner
    @property
    def owner(self):
        myKey = self.key.to_legacy_urlsafe().decode()
        return KeUser.get_one(KeUser.own_feeds == myKey)

class KeUser(MyBaseModel): # kindleEar User
    __kind__ = "KeUser"
    name = fields.StringField()
    passwd = fields.StringField()
    expiration_days = fields.IntField() #账号超期设置值，0为永久有效
    secret_key = fields.StringField()
    kindle_email = fields.StringField()
    enable_send = fields.BooleanField()
    send_days = fields.ListField()
    send_time = fields.IntField()
    timezone = fields.IntField()
    book_type = fields.StringField() #mobi,epub
    device = fields.StringField()
    expires = fields.DateTimeField() #超过了此日期后账号自动停止推送
    own_feeds = fields.StringField(default='') #每个用户都有自己的自定义RSS，保存对应Book实例的Key, my_rss_book
    use_title_in_feed = fields.BooleanField() #文章标题优先选择订阅源中的还是网页中的
    title_fmt = fields.StringField() #在元数据标题中添加日期的格式
    author_format = fields.StringField() #修正Kindle 5.9.x固件的bug【将作者显示为日期】
    book_mode = fields.StringField() #书籍模式，'periodical'|'comic'，漫画模式可以直接全屏
    merge_books = fields.BooleanField() #是否合并书籍成一本
    remove_hyperlinks = fields.StringField() #去掉文本或图片上的超链接{'' | 'image' | 'text' | 'all'}
    share_fuckgfw = fields.BooleanField() #归档和分享时是否需要翻墙
    evernote = fields.BooleanField() #是否分享至evernote
    evernote_mail = fields.StringField() #evernote邮件地址
    wiz = fields.BooleanField() #为知笔记
    wiz_mail = fields.StringField()
    pocket = fields.BooleanField() #send to add@getpocket.com
    pocket_access_token = fields.StringField()
    pocket_acc_token_hash = fields.StringField()
    instapaper = fields.BooleanField()
    instapaper_username = fields.StringField()
    instapaper_password = fields.StringField()
    xweibo = fields.BooleanField()
    tweibo = fields.BooleanField()
    facebook = fields.BooleanField() #分享链接到facebook
    twitter = fields.BooleanField()
    tumblr = fields.BooleanField()
    browser = fields.BooleanField()
    qrcode = fields.BooleanField() #是否在文章末尾添加文章网址的QRCODE
    cover = fields.AnyField() #保存各用户的自定义封面图片二进制内容
    css_content = fields.StringField() #added 2019-09-12 保存用户上传的css样式表
    sg_enable = BooleanField(default=False)
    sg_apikey = CharField(default='')

    #自己所属的RSS集合代表的书
    @property
    def my_rss_book(self):
        return Book.get_by_id_or_none(DataStoreKey.from_legacy_urlsafe(self.own_feeds))

    #自己直接所属的RSS列表，返回[Feed]
    @property
    def all_custom_rss(self):
        rssBook = self.my_rss_book
        if rssBook:
            bookKey = rssBook.key.to_legacy_urlsafe().decode()
            return Feed.get_all(Feed.book == bookKey)

    #本用户所有的白名单
    @property
    def white_lists(self):
        myKey = self.key.to_legacy_urlsafe().decode()
        return WhiteList.get_all(WhiteList.user == myKey)
    
    @property
    def url_filters(self):
        myKey = self.key.to_legacy_urlsafe().decode()
        return UrlFilter.get_all(UrlFilter.user == myKey)
    
    #获取此账号对应的书籍的网站登陆信息
    def subscription_info(self, title):
        myKey = self.key.to_legacy_urlsafe().decode()
        infos = SubscriptionInfo.get_all(SubscriptionInfo.user == myKey)
        items = [item for item in infos if item.title == title]
        return items[0] if items else None

    #删除自己订阅的书，白名单，过滤器等，就是完全的清理
    def erase_traces(self):
        myKey = self.key.to_legacy_urlsafe().decode()
        book = self.get_by_key(self.own_feeds)
        if book:
            for feed in list(book.feeds):
                feed.delete()
            book.delete()
        map(lambda x: x.delete(), list(WhiteList.get_all(WhiteList.user == myKey)))
        map(lambda x: x.delete(), list(UrlFilter.get_all(UrlFilter.user == myKey)))
        map(lambda x: x.delete(), list(SubscriptionInfo.get_all(SubscriptionInfo.user == myKey)))
        map(lambda x: x.delete(), list(DeliverLog.get_all(DeliverLog.username == self.name)))
        map(lambda x: x.delete(), list(LastDelivered.get_all(LastDelivered.username == self.name)))
        for book in Book.get_all(): #订阅记录
            subscrUsers = book.users
            if self.name in subscrUsers:
                subscrUsers.remove(name)
                book.users = subscrUsers
                book.save()

#自定义RSS订阅源
class Feed(MyBaseModel):
    __kind__ = "Feed"
    title = fields.StringField()
    url = fields.StringField()
    isfulltext = fields.BooleanField()
    time = fields.DateTimeField() #源被加入的时间，用于排序
    book = fields.StringField(default='') #属于哪本书，保存的是Book的Key的字符串表示

#书籍的推送历史记录
class DeliverLog(MyBaseModel):
    __kind__ = "DeliverLog"
    username = fields.StringField()
    to = fields.StringField()
    size = fields.IntField()
    time = fields.StringField()
    datetime = fields.DateTimeField()
    book = fields.StringField()
    status = fields.StringField()

#记录已经推送的期数/章节等信息，可用来处理连载的漫画/小说等
class LastDelivered(MyBaseModel):
    __kind__ = "LastDelivered"
    username = fields.StringField()
    bookname = fields.StringField()
    num = fields.IntField() #num和record可以任选其一用来记录，或使用两个配合都可以
    record = fields.StringField() #record同时也用做在web上显示
    datetime = fields.DateTimeField()

class WhiteList(MyBaseModel):
    __kind__ = "WhiteList"
    mail = fields.StringField()
    user = fields.StringField(default='') #保存对应KeUser的Key

class UrlFilter(MyBaseModel):
    __kind__ = "UrlFilter"
    url = fields.StringField()
    user = fields.StringField(default='')  #保存对应KeUser的Key

#某些网站需要会员才能阅读
class SubscriptionInfo(MyBaseModel):
    __kind__ = "SubscriptionInfo"
    title = fields.StringField()  #书籍的标题
    account = fields.StringField()
    encrypted_pwd = fields.StringField()
    user = fields.StringField(default='')  #保存对应KeUser的Key
    
    @property
    def password(self):
        userInst = KeUser.get_by_id_or_none(DataStoreKey.from_legacy_urlsafe(self.user))
        return ke_decrypt(self.encrypted_pwd, userInst.secret_key if userInst else '')
        
    @password.setter
    def password(self, pwd):
        userInst = KeUser.get_by_id_or_none(DataStoreKey.from_legacy_urlsafe(self.user))
        self.encrypted_pwd = ke_encrypt(pwd, userInst.secret_key if userInst else '')

#Shared RSS links from other users [for kindleear.appspot.com only]
class SharedRss(MyBaseModel):
    __kind__ = "SharedRss"
    title = fields.StringField()
    url = fields.StringField()
    isfulltext = fields.BooleanField()
    category = fields.StringField()
    creator = fields.StringField()
    created_time = fields.DateTimeField()
    subscribed = fields.IntField() #for sort
    invalid_report_days = fields.IntField() #some one reported it is a invalid link
    last_invalid_report_time = fields.DateTimeField() #a rss will be deleted after some days of reported_invalid
    
    #return all categories in database
    @classmethod
    def categories(self):
        return set([item.category for item in SharedRss.get_all()])
    
#Buffer for category of shared rss [for kindleear.appspot.com only]
class SharedRssCategory(MyBaseModel):
    __kind__ = "SharedRssCategory"
    name = fields.StringField()
    last_updated = fields.DateTimeField() #for sort
