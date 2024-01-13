#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#关系数据库行结构定义，使用peewee ORM
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Author:
# cdhigh <https://github.com/cdhigh>
#Contributors:
# rexdf <https://github.com/rexdf>

from apps.utils import ke_encrypt, ke_decrypt
from peewee import *
from playhouse.shortcuts import model_to_dict
from config import DATABASE_ENGINE, DATABASE_HOST, DATABASE_PORT, DATABASE_USERNAME, DATABASE_PASSWORD, DATABASE_NAME

#用于在数据库结构升级后的兼容设计，数据库结构和前一版本不兼容则需要升级此版本号
__DB_VERSION__ = 1

if DATABASE_ENGINE == "sqlite":
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
def connectToDatabase():
    global dbInstance
    dbInstance.connect(reuse_if_open=True)

#关闭数据库连接
def closeDataBase():
    global dbInstance
    if not dbInstance.is_closed():
        dbInstance.close()

#数据表的共同基类
class MyBaseModel(Model):
    class Meta:
        database = dbInstance
        
    #为了方便使用，新增此接口，查询不到返回None，而不抛出异常
    @classmethod
    def GetOne(cls, *query, **kwargs):
        try:
            return cls.get(*query,**kwargs)
        except DoesNotExist:
            return None

    #兼容GAE的一个接口
    @classmethod
    def get_by_id(cls, id_):
        try:
            return cls.get(cls.id == id_)
        except DoesNotExist:
            return None

    #将当前行数据转换为一个字典结构，由子类使用，不进行任何转换
    def ToRawDict(self):
        return {field: getattr(self, field) for field in self._meta.fields}
        
    #将当前行数据转换为一个字典结构，由子类使用，将外键转换为ID，日期转换为字符串
    def ToDict(self):
        ret = model_to_dict(self)
        for key in ret:
            data = ret[key]
            if isinstance(data, datetime.datetime):
                ret[key] = data.strftime('%Y-%m-%d %H:%M:%S')
        return ret

    #另一个转换行数据为字典的函数，如果不想再依赖playhouse可以使用这个
    def ToDict1(self):
        ret = {}
        for field in self._meta.fields:
            data = getattr(self, field)
            if isinstance(data, MyBaseModel): #外键，则仅返回其外键ID
                data = data.id
            elif isinstance(data, datetime.datetime):
                data = data.strftime('%Y-%m-%d %H:%M:%S')
            ret[field] = data
        return ret

#--------------db models----------------
class Book(MyBaseModel):
    title = CharField(unique=True)
    description = CharField()
    users = CharField() #账号名之间使用逗号分割
    builtin = BooleanField()
    needs_subscription = BooleanField() #是否需要登陆网页
    separate = BooleanField() #是否单独推送
    
    #====自定义书籍
    language = CharField()
    masthead_file = CharField() # GIF 600*60
    cover_file = CharField()
    keep_image = BooleanField()
    oldest_article = IntegerField()
    
class KeUser(MyBaseModel): # kindleEar User
    name = CharField(required=True, unique=True)
    passwd = CharField(required=True)
    expiration_days = IntegerField(default=0) #账号超期设置值，0为永久有效
    secret_key = CharField(default='')
    kindle_email = CharField()
    enable_send = BooleanField()
    send_days = CharField() #如果有多个日期，之间使用逗号分割
    send_time = IntegerField()
    timezone = IntegerField()
    book_type = CharField() #mobi,epub
    device = CharField()
    expires = DateTimeField() #超过了此日期后账号自动停止推送
    own_feeds = ForeignKeyField(Book, backref='owner') # 每个用户都有自己的自定义RSS，也给Book增加一个owner
    use_title_in_feed = BooleanField() # 文章标题优先选择订阅源中的还是网页中的
    title_fmt = CharField() #在元数据标题中添加日期的格式
    author_format = CharField() #修正Kindle 5.9.x固件的bug【将作者显示为日期】
    book_mode = CharField() #书籍模式，'periodical'|'comic'，漫画模式可以直接全屏
    merge_books = BooleanField() #是否合并书籍成一本
    remove_hyperlinks = CharField() #去掉文本或图片上的超链接{'' | 'image' | 'text' | 'all'}
    
    share_fuckgfw = BooleanField() #归档和分享时是否需要翻墙
    evernote = BooleanField() #是否分享至evernote
    evernote_mail = CharField() #evernote邮件地址
    wiz = BooleanField() #为知笔记
    wiz_mail = CharField()
    pocket = BooleanField() #send to add@getpocket.com
    pocket_access_token = CharField()
    pocket_acc_token_hash = CharField()
    instapaper = BooleanField()
    instapaper_username = CharField()
    instapaper_password = CharField()
    xweibo = BooleanField()
    tweibo = BooleanField()
    facebook = BooleanField() #分享链接到facebook
    twitter = BooleanField()
    tumblr = BooleanField()
    browser = BooleanField()
    qrcode = BooleanField() #是否在文章末尾添加文章网址的QRCODE
    cover = BlobField() #保存各用户的自定义封面图片二进制内容
    css_content = TextField() #保存用户上传的css样式表

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
    user = ForeignKeyField(KeUser, backref='white_list')

class UrlFilter(MyBaseModel):
    url = CharField()
    user = ForeignKeyField(KeUser, backref='url_filter')
    
class SubscriptionInfo(MyBaseModel):
    title = CharField()
    account = CharField()
    encrypted_pwd = CharField()
    user = ForeignKeyField(KeUser, backref='subscription_info')
    
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
    invalid_report_days = IntegerField(default=0) #some one reported it is a invalid link
    last_invalid_report_time = DateTimeField() #a rss will be deleted after some days of reported_invalid
    
    #返回数据库中所有的分类
    @classmethod
    def categories(self):
        return [item.category for item in SharedRss.select(SharedRss.category)]
    
#Buffer for category of shared rss [for kindleear.appspot.com only]
class SharedRssCategory(MyBaseModel):
    name = CharField()
    last_updated = DateTimeField() #for sort

#当前仅使用 name='dbTableVersion' 行保存数据库格式版本
class SerialNo(MyBaseModel):
    name = CharField()
    sn = IntegerField()

#创建数据库表格，一个数据库只需要创建一次
#如果是sql数据库，可以使用force=True删掉之前的数据库文件
def createDatabaseTable(force=False):
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
    SerialNo.create_table()
    
    SerialNo.create(name='dbTableVersion', sn=__DB_VERSION__)
    