#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#关系数据库行结构定义，使用peewee ORM
#根据以前的经验，经常出现有网友部署时没有成功建立数据库索引，所以现在排序在应用内处理，数据量不大
#Author: cdhigh <https://github.com/cdhigh>
import os, sys, json
if __name__ == '__main__': #调试使用，调试时为了单独执行此文件
    thisDir = os.path.dirname(os.path.abspath(__file__))
    appDir = os.path.normpath(os.path.join(thisDir, "..", ".."))
    sys.path.insert(0, appDir)
    sys.path.insert(0, os.path.join(appDir, 'lib'))
from apps.utils import ke_encrypt, ke_decrypt
from peewee import *
from playhouse.db_url import connect
from config import DATABASE_ENGINE, DATABASE_HOST, DATABASE_PORT, DATABASE_USERNAME, DATABASE_PASSWORD, DATABASE_NAME

#用于在数据库结构升级后的兼容设计，数据库结构和前一版本不兼容则需要升级此版本号
__DB_VERSION__ = 1

if '://' in DATABASE_NAME:
    dbInstance = connect(DATABASE_NAME)
elif DATABASE_ENGINE == "sqlite":
    thisDir = os.path.dirname(os.path.abspath(__file__))
    dbName = os.path.normpath(os.path.join(thisDir, "..", "..", DATABASE_NAME))
    dbInstance = SqliteDatabase(dbName, check_same_thread=False)
elif DATABASE_ENGINE == "mysql":
    dbInstance = MySQLDatabase(DATABASE_NAME, user=DATABASE_USERNAME, password=DATABASE_PASSWORD,
                         host=DATABASE_HOST, port=DATABASE_PORT)
elif DATABASE_ENGINE == "postgresql":
    dbInstance = PostgresqlDatabase(DATABASE_NAME, user=DATABASE_USERNAME, password=DATABASE_PASSWORD,
                         host=DATABASE_HOST, port=DATABASE_PORT)
elif DATABASE_ENGINE == "cockroachdb":
    dbInstance = CockroachDatabase(DATABASE_NAME, user=DATABASE_USERNAME, password=DATABASE_PASSWORD,
                         host=DATABASE_HOST, port=DATABASE_PORT)
else:
    raise Exception("database engine '{}' not supported yet".format(DATABASE_ENGINE))

#调用此函数正式连接到数据库（打开数据库）
def ConnectToDatabase():
    global dbInstance
    dbInstance.connect(reuse_if_open=True)

#关闭数据库连接
def CloseDatabase():
    global dbInstance
    if not dbInstance.is_closed():
        dbInstance.close()

#自定义字段，在本应用用来保存列表
class ListField(TextField):
    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        if value is not None:
            return json.loads(value)

def listfield_default():
    return []

#数据表的共同基类
class MyBaseModel(Model):
    class Meta:
        database = dbInstance
    
    @classmethod
    def get_all(cls, *query):
        if query:
            return cls.select().where(*query).execute()
        else:
            return cls.select().execute()

    @classmethod
    def get_one(cls, *query):
        return cls.get_or_none(*query)

    #如果取不到，返回None
    @classmethod
    def get_by_id_or_none(cls, id_):
        try:
            return cls.get_by_id(int(id_))
        except:
            return None

    #返回Key/Id的字符串表达
    @property
    def key_or_id_string(self):
        return str(self.id)

    #做外键使用的字符串或ID
    @property
    def reference_key_or_id(self):
        return self

#--------------db models----------------
class Book(MyBaseModel):
    title = CharField(unique=True)
    description = CharField()
    users = ListField(default=listfield_default) #有哪些账号订阅了这本书
    builtin = BooleanField()
    needs_subscription = BooleanField() #是否需要登陆网页
    separate = BooleanField() #是否单独推送
    
    #====自定义书籍
    language = CharField(default='')
    masthead_file = CharField(default='') # GIF 600*60
    cover_file = CharField(default='')
    keep_image = BooleanField(default=True)
    oldest_article = IntegerField(default=7)

    #feeds, owner 属性为KeUser自动添加的
    
class KeUser(MyBaseModel): # kindleEar User
    name = CharField(unique=True)
    passwd = CharField()
    expiration_days = IntegerField(default=0) #账号超期设置值，0为永久有效
    secret_key = CharField(default='')
    kindle_email = CharField(default='')
    enable_send = BooleanField(default=False)
    send_days = ListField(default=listfield_default)
    send_time = IntegerField(default=0)
    timezone = IntegerField(default=0)
    book_type = CharField(default='epub') #mobi,epub
    device = CharField(default='')
    expires = DateTimeField(null=True) #超过了此日期后账号自动停止推送
    own_feeds = ForeignKeyField(Book, backref='owner') # 每个用户都有自己的自定义RSS，也给Book增加一个owner,my_rss_book
    use_title_in_feed = BooleanField(default=True) # 文章标题优先选择订阅源中的还是网页中的
    title_fmt = CharField(default='') #在元数据标题中添加日期的格式
    author_format = CharField(default='') #修正Kindle 5.9.x固件的bug【将作者显示为日期】
    book_mode = CharField(default='') #书籍模式，'periodical'|'comic'，漫画模式可以直接全屏
    merge_books = BooleanField(default=True) #是否合并书籍成一本
    remove_hyperlinks = CharField(default='') #去掉文本或图片上的超链接{'' | 'image' | 'text' | 'all'}
    
    share_fuckgfw = BooleanField(default=False) #归档和分享时是否需要翻墙
    evernote = BooleanField(default=False) #是否分享至evernote
    evernote_mail = CharField(default='') #evernote邮件地址
    wiz = BooleanField(default=False) #为知笔记
    wiz_mail = CharField(default='')
    pocket = BooleanField(default=False) #send to add@getpocket.com
    pocket_access_token = CharField(default='')
    pocket_acc_token_hash = CharField(default='')
    instapaper = BooleanField(default=False)
    instapaper_username = CharField(default='')
    instapaper_password = CharField(default='')
    xweibo = BooleanField(default=False)
    tweibo = BooleanField(default=False)
    facebook = BooleanField(default=False) #分享链接到facebook
    twitter = BooleanField(default=False)
    tumblr = BooleanField(default=False)
    browser = BooleanField(default=False)
    qrcode = BooleanField(default=False) #是否在文章末尾添加文章网址的QRCODE
    cover = BlobField(null=True) #保存各用户的自定义封面图片二进制内容
    css_content = TextField(default='') #保存用户上传的css样式表
    sg_enable = BooleanField(default=False)
    sg_apikey = CharField(default='')
    
    #white_list, url_filter, subscr_infos 都是反向引用
    
    #自己所属的RSS集合代表的书
    @property
    def my_rss_book(self):
        return self.own_feeds

    #自己直接所属的RSS列表，返回[Feed]
    @property
    def all_custom_rss(self):
        return self.own_feeds.feeds

    #删除自己订阅的书，白名单，过滤器等，就是完全的清理
    def erase_traces(self):
        if self.own_feeds:
            map(lambda x: x.delete(), list(self.own_feeds.feeds))
            self.own_feeds.delete()
        map(lambda x: x.delete(), list(u.white_lists))
        map(lambda x: x.delete(), list(u.url_filters))
        map(lambda x: x.delete(), list(u.subscr_infos))
        DeliverLog.delete().where(DeliverLog.username == self.name).execute() #推送记录
        LastDelivered.delete().where(LastDelivered.username == self.name).execute()
        for book in Book.get_all(): #订阅记录
            subscrUsers = book.users
            if self.name in subscrUsers:
                subscrUsers.remove(name)
                book.users = subscrUsers
                book.save()
            
#自定义RSS订阅源
class Feed(MyBaseModel):
    title = CharField()
    url = CharField()
    isfulltext = BooleanField()
    time = DateTimeField() #源被加入的时间，用于排序
    book = ForeignKeyField(Book, backref='feeds') #属于哪本书，同时给book增加了一个feeds属性

#书籍的推送历史记录
class DeliverLog(MyBaseModel):
    username = CharField()
    to = CharField()
    size = IntegerField()
    time = CharField()
    datetime = DateTimeField()
    book = CharField()
    status = CharField()

#added 2017-09-01 记录已经推送的期数/章节等信息，可用来处理连载的漫画/小说等
class LastDelivered(MyBaseModel):
    username = CharField()
    bookname = CharField()
    num = IntegerField(default=0) #num和record可以任选其一用来记录，或使用两个配合都可以
    record = CharField(default='') #record同时也用做在web上显示
    datetime = DateTimeField()
    
class WhiteList(MyBaseModel):
    mail = CharField()
    user = ForeignKeyField(KeUser, backref='white_lists')

class UrlFilter(MyBaseModel):
    url = CharField()
    user = ForeignKeyField(KeUser, backref='url_filters')

#某些网站需要会员才能阅读
class SubscriptionInfo(MyBaseModel):
    title = CharField()   #书籍的标题
    account = CharField()
    encrypted_pwd = CharField()
    user = ForeignKeyField(KeUser, backref='subscr_infos')
    
    @property
    def password(self):
        return ke_decrypt(self.encrypted_pwd, self.user.secret_key)
        
    @password.setter
    def password(self, pwd):
        self.encrypted_pwd = ke_encrypt(pwd, self.user.secret_key)

#Shared RSS links from other users [for kindleear.appspot.com only]
class SharedRss(MyBaseModel):
    title = CharField()
    url = CharField()
    isfulltext = BooleanField()
    category = CharField()
    creator = CharField()
    created_time = DateTimeField()
    subscribed = IntegerField(default=0) #for sort
    last_subscribed_time = DateTimeField(null=True)
    invalid_report_days = IntegerField(default=0) #some one reported it is a invalid link
    last_invalid_report_time = DateTimeField(null=True) #a rss will be deleted after some days of reported_invalid

    #返回数据库中所有的分类
    @classmethod
    def categories(self):
        return set([item.category for item in SharedRss.select(SharedRss.category)])
    
#Buffer for category of shared rss [for kindleear.appspot.com only]
class SharedRssCategory(MyBaseModel):
    name = CharField()
    last_updated = DateTimeField() #for sort

#当前仅使用 name='dbTableVersion' 行保存数据库格式版本
class AppInfo(MyBaseModel):
    name = CharField()
    value = IntegerField()
    description = CharField(null=True)
    comment = CharField(null=True)

#创建数据库表格，一个数据库只需要创建一次
#如果是sql数据库，可以使用force=True删掉之前的数据库文件
def CreateDatabaseTable(force=False):
    if force and DATABASE_ENGINE == "sqlite":
        try:
            os.remove(dbName)
        except:
            pass

    Book.create_table()
    KeUser.create_table()
    Feed.create_table()
    DeliverLog.create_table()
    LastDelivered.create_table()
    WhiteList.create_table()
    UrlFilter.create_table()
    SubscriptionInfo.create_table()
    SharedRss.create_table()
    SharedRssCategory.create_table()
    AppInfo.create_table()
    
    AppInfo(name='dbTableVersion', value=__DB_VERSION__).save()


if __name__ == '__main__':
    if DATABASE_ENGINE == 'sqlite':
        CreateDatabaseTable()
