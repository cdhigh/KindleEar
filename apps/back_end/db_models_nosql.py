#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#nosql数据库结构定义，使用umongo/udatastore
#mongo中的一个collection相当于SQL中的一个表
#insert_one({:}).inserted_id, insert_many([]), find_one({:}), find({}).limit(3).sort('age', -1)
#update_one({'_id':'1'}, {'$set':{'age':21}}), replace_one({:}, {:})
#update_many({:}, {'$set':{}}), delete_one({:}), delete_many({:}).deleted_count
#userguide: <https://umongo.readthedocs.io/en/latest/userguide.html>
#Author: cdhigh <https://github.com/cdhigh/KindleEar>


from apps.utils import ke_encrypt, ke_decrypt
from config import DATABASE_ENGINE, DATABASE_HOST, DATABASE_PORT, DATABASE_USERNAME, DATABASE_PASSWORD, DATABASE_NAME

if DATABASE_ENGINE == "datastore":
    from google.cloud import datastore
    from umongo import Document, fields, validate
    from udatastore import DataStoreInstance
    dbClient = datastore.Client(project=APP_ID, namespace='abcd')
    dbInstance = DataStoreInstance()
    dbInstance.init(dbClient)
elif DATABASE_ENGINE == "mongo":
    from pymongo import MongoClient
    from umongo import Document, fields, validate
    from umongo.frameworks import PyMongoInstance
    dbClient = MongoClient(DATABASE_HOST, DATABASE_PORT)
    db = dbClient[DATABASE_NAME]
    if DATABASE_USERNAME and DATABASE_PASSWORD:
        db.authenticate(DATABASE_USERNAME, DATABASE_PASSWORD)
    dbInstance = PyMongoInstance()
    dbInstance.init(db)
else:
    raise Exception("database engine '{}' not supported yet".format(DATABASE_ENGINE))

#调用此函数正式连接到数据库（打开数据库）
def connectToDatabase():
    pass

#关闭数据库连接
def closeDataBase():
    pass

#数据表的共同基类
class MyBaseModel(Document):
    class Meta:
        abstract = True

    #为了方便使用，新增此接口，查询不到返回None，而不抛出异常
    @classmethod
    def GetOne(cls, *query, **kwargs):
        try:
        User.find_one({"email": 'goku@sayen.com'})
            return cls.find_one()
        except DoesNotExist:
            return None


#--------------db models----------------
#对应到每一个”书“，注意，同一个用户的”自定义RSS“会归到同一本书内
@dbInstance.register
class Book(MyBaseModel):
    title = fields.StringField(required=True)
    description = fields.StringField()
    users = fields.ListField()
    builtin = fields.BooleanField()
    needs_subscription = fields.BooleanField() #是否需要登陆网页
    separate = fields.BooleanField() #是否单独推送
    
    #====自定义书籍
    language = fields.StringField()
    masthead_file = fields.StringField() # GIF 600*60
    cover_file = fields.StringField()
    keep_image = fields.BooleanField()
    oldest_article = fields.IntegerField()
    
    #这三个属性只有自定义RSS才有意义
    @property
    def feeds(self):
        try:
            return Feed.all().filter('book = ', self.key()).order('time')
        except NeedIndexError: #很多人不会部署，经常出现没有建立索引的情况，干脆碰到这种情况直接消耗CPU时间自己排序得了
            return sorted(Feed.all().filter("book = ", self.key()), key=attrgetter('time'))
            
    @property
    def feedsCount(self):
        return self.feeds.count()
        
    @property
    def owner(self):
        return KeUser.all().filter('own_feeds = ', self.key())

@dbInstance.register
class KeUser(MyBaseModel): # kindleEar User
    name = fields.StringField(required=True, unique=True)
    passwd = fields.StringField(required=True)
    secret_key = fields.StringField()
    kindle_email = fields.StringField()
    enable_send = fields.BooleanField()
    send_days = fields.ListField()
    send_time = fields.IntegerField()
    timezone = fields.IntegerField()
    book_type = fields.StringField() #mobi,epub
    device = fields.StringField()
    expires = fields.DateTimeField() #超过了此日期后账号自动停止推送
    own_feeds = fields.ReferenceField(Book) # 每个用户都有自己的自定义RSS
    use_title_in_feed = fields.BooleanField() # 文章标题优先选择订阅源中的还是网页中的
    title_fmt = fields.StringField() #在元数据标题中添加日期的格式
    merge_books = fields.BooleanField() #是否合并书籍成一本
    
    share_fuckgfw = fields.BooleanField() #归档和分享时是否需要翻墙
    evernote = fields.BooleanField() #是否分享至evernote
    evernote_mail = fields.StringField() #evernote邮件地址
    wiz = fields.BooleanField() #为知笔记
    wiz_mail = fields.StringField()
    pocket = fields.BooleanField(default=False) #send to add@getpocket.com
    pocket_access_token = fields.StringField(default='')
    pocket_acc_token_hash = fields.StringField(default='')
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
    cover = fields.ObjectIdField() #保存各用户的自定义封面图片二进制内容
    css_content = fields.StringField() #added 2019-09-12 保存用户上传的css样式表
    
    book_mode = fields.StringField() #added 2017-08-31 书籍模式，'periodical'|'comic'，漫画模式可以直接全屏
    expiration_days = fields.IntegerField() #added 2018-01-07 账号超期设置值，0为永久有效
    remove_hyperlinks = fields.StringField() #added 2018-05-02 去掉文本或图片上的超链接{'' | 'image' | 'text' | 'all'}
    author_format = fields.StringField() #added 2020-09-17 修正Kindle 5.9.x固件的bug【将作者显示为日期】

    @property
    def white_list(self):
        return WhiteList.all().filter('user = ', self.key())
    
    @property
    def url_filter(self):
        return UrlFilter.all().filter('user = ', self.key())
    
    #获取此账号对应的书籍的网站登陆信息
    def subscription_info(self, title):
        return SubscriptionInfo.all().filter('user = ', self.key()).filter('title = ', title).get()

#自定义RSS订阅源
@dbInstance.register
class Feed(MyBaseModel):
    book = fields.ReferenceField(Book)
    title = fields.StringField()
    url = fields.StringField()
    isfulltext = fields.BooleanField()
    time = fields.DateTimeField() #源被加入的时间，用于排序

#书籍的推送历史记录
@dbInstance.register
class DeliverLog(MyBaseModel):
    username = fields.StringField()
    to = fields.StringField()
    size = fields.IntegerField()
    time = fields.StringField()
    datetime = fields.DateTimeField()
    book = fields.StringField()
    status = fields.StringField()

#added 2017-09-01 记录已经推送的期数/章节等信息，可用来处理连载的漫画/小说等
@dbInstance.register
class LastDelivered(MyBaseModel):
    username = fields.StringField()
    bookname = fields.StringField()
    num = fields.IntegerField(default=0) #num和record可以任选其一用来记录，或使用两个配合都可以
    record = fields.StringField(default='') #record同时也用做在web上显示
    datetime = fields.DateTimeField()

@dbInstance.register
class WhiteList(MyBaseModel):
    mail = fields.StringField()
    user = fields.ReferenceField(KeUser)

@dbInstance.register
class UrlFilter(MyBaseModel):
    url = fields.StringField()
    user = fields.ReferenceField(KeUser)

@dbInstance.register
class SubscriptionInfo(MyBaseModel):
    title = fields.StringField()
    account = fields.StringField()
    encrypted_pwd = fields.StringField()
    user = fields.ReferenceField(KeUser)
    
    @property
    def password(self):
        return ke_decrypt(self.encrypted_pwd, self.user.secret_key)
        
    @password.setter
    def password(self, pwd):
        self.encrypted_pwd = ke_encrypt(pwd, self.user.secret_key)

#Shared RSS links from other users [for kindleear.appspot.com only]
@dbInstance.register
class SharedRss(MyBaseModel):
    title = fields.StringField()
    url = fields.StringField()
    isfulltext = fields.BooleanField()
    category = fields.StringField()
    creator = fields.StringField()
    created_time = fields.DateTimeField()
    subscribed = fields.IntegerField(default=0) #for sort
    invalid_report_days = fields.IntegerField(default=0) #some one reported it is a invalid link
    last_invalid_report_time = fields.DateTimeField() #a rss will be deleted after some days of reported_invalid
    
    #return all categories in database
    @classmethod
    def categories(self):
        return [item.category for item in fields.GqlQuery('SELECT DISTINCT category FROM SharedRss')]
    
#Buffer for category of shared rss [for kindleear.appspot.com only]
@dbInstance.register
class SharedRssCategory(MyBaseModel):
    name = fields.StringField()
    last_updated = fields.DateTimeField() #for sort
