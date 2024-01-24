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
import datetime
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
    id = fields.StringField()
    @classmethod
    def get_all(cls, *query):
        return cls.select().where(*query).execute()

    @classmethod
    def get_one(cls, *query):
        return cls.select().where(*query).execute()

    #和peewee一致
    @classmethod
    def get_by_id_or_none(cls, id_):
        if isinstance(id_, (str, int)):
            id_ = DataStoreKey.from_legacy_urlsafe(str(id_))
        return cls.get_by_key(id_)

    #返回Key/Id的字符串表达
    @property
    def key_or_id_string(self):
        return self.key.to_legacy_urlsafe().decode()

    #做外键使用的字符串或ID
    @property
    def reference_key_or_id(self):
        return self.key.to_legacy_urlsafe().decode()

    #将当前行数据转换为一个字典结构，由子类使用，将外键转换为ID，日期转换为字符串
    #可以传入 only=[Book.title, ...]，或 exclude=[]
    def to_dict(self, **kwargs):
        ret = self.to_python_dict(**kwargs)
        for key in ret:
            data = ret[key]
            if isinstance(data, datetime.datetime):
                ret[key] = data.strftime('%Y-%m-%d %H:%M:%S')
        return ret

#--------------db models----------------

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

    book_title = fields.StringField()
    use_title_in_feed = fields.BooleanField() #文章标题优先选择订阅源中的还是网页中的
    title_fmt = fields.StringField() #在元数据标题中添加日期的格式
    author_format = fields.StringField() #修正Kindle 5.9.x固件的bug【将作者显示为日期】
    book_mode = fields.StringField() #书籍模式，'periodical'|'comic'，漫画模式可以直接全屏
    merge_books = fields.BooleanField() #是否合并书籍成一本
    remove_hyperlinks = fields.StringField() #去掉文本或图片上的超链接{'' | 'image' | 'text' | 'all'}
    keep_image = fields.BooleanField(default=True)
    oldest_article = fields.IntField(default=7)
    book_language = fields.StringField() #自定义RSS的语言
    enable_custom_rss = fields.BooleanField(default=True)
    
    share_key = fields.StringField(default='')
    share_links = fields.DictField() #evernote/wiz/pocket/instapaper包含子字典，微博/facebook/twitter等仅包含0/1
    share_fuckgfw = fields.BooleanField() #归档和分享时是否需要翻墙

    cover = fields.AnyField() #保存各用户的自定义封面图片二进制内容
    css_content = fields.StringField() #added 2019-09-12 保存用户上传的css样式表
    sg_enable = fields.BooleanField(default=False)
    sg_apikey = fields.StringField(default='')
    custom = fields.DictField() #留着扩展，避免后续一些小特性还需要升级数据表结构

    #自己直接所属的自定义RSS列表，返回[Recipe,]
    def all_custom_rss(self):
        return sorted(Recipe.select().where(Recipe.user == self.name).where(Recipe.type_ == 'custom'), 
            key=attrgetter('time'), reverse=True)

    #自己直接所属的上传Recipe列表，返回[Recipe,]
    def all_uploaded_recipe(self):
        return sorted(Recipe.select().where(Recipe.user == self.name).where(Recipe.type_ == 'uploaded'), 
            key=attrgetter('time'), reverse=True)

    #自己订阅的Recipe，如果传入recipe_id，则使用id筛选，返回一个，否则返回一个列表
    def get_booked_recipe(self, recipe_id=None):
        if recipe_id:
            return BookedRecipe.select().where(BookedRecipe.user == self.name).where(BookedRecipe.recipe_id == recipe_id).first()
        else:
            return BookedRecipe.get_all(BookedRecipe.user == self.name)

    #本用户所有的白名单
    def white_lists(self):
        return WhiteList.get_all(WhiteList.user == self.name)
    
    def url_filters(self):
        return UrlFilter.get_all(UrlFilter.user == self.name)

    #删除自己订阅的书，白名单，过滤器等，就是完全的清理
    def erase_traces(self):
        map(lambda x: x.delete_instance(), list(Recipe.get_all(Recipe.user == self.name)))
        map(lambda x: x.delete_instance(), list(self.get_booked_recipe()))
        map(lambda x: x.delete_instance(), list(self.white_lists()))
        map(lambda x: x.delete_instance(), list(self.url_filters()))
        map(lambda x: x.delete_instance(), list(DeliverLog.get_all(DeliverLog.username == self.name)))
        map(lambda x: x.delete_instance(), list(LastDelivered.get_all(LastDelivered.username == self.name)))
        
#RSS订阅源，包括自定义RSS，上传的recipe，内置在zip里面的builtin_recipe不包括在内
#每个Recipe的字符串表示为：custom:id, uploaded:id
class Recipe(MyBaseModel):
    __kind__ = "Recipe"
    title = fields.StringField()
    url = fields.StringField(default='')
    description = fields.StringField(default='')
    isfulltext = fields.BooleanField(default=False)
    type_ = fields.StringField() #'custom','uploaded'
    needs_subscription = fields.BooleanField(default=False) #是否需要登陆网页，只有上传的recipe才有意义
    content = fields.AnyField() #保存上传的recipe的utf-8编码后的二进制内容
    time = fields.DateTimeField() #源被加入的时间，用于排序
    user = fields.StringField(default='') #哪个账号创建的

#已经被订阅的Recipe信息
class BookedRecipe(MyBaseModel):
    recipe_id = fields.CharField() #这个ID不是Recipe数据库ID，而是 builtin:xxx, uploaded:xxx, custom:xxx
    separated = fields.BooleanField() #是否单独推送
    user = fields.CharField()
    title = fields.StringField()
    description = fields.StringField()
    needs_subscription = fields.BooleanField(default=False)
    account = fields.StringField(default='') #如果网站需要登录才能看
    encrypted_pwd = fields.StringField(default='')
    time = fields.DateTimeField() #源被订阅的时间，用于排序

    @property
    def password(self):
        userInst = KeUser.get_one(KeUser.name == self.user)
        return ke_decrypt(self.encrypted_pwd, userInst.secret_key if userInst else '')
        
    @password.setter
    def password(self, pwd):
        userInst = KeUser.get_one(KeUser.name == self.user)
        self.encrypted_pwd = ke_encrypt(pwd, userInst.secret_key if userInst else '')

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
    user = fields.StringField() #保存账号名

class UrlFilter(MyBaseModel):
    __kind__ = "UrlFilter"
    url = fields.StringField()
    user = fields.StringField()  #保存账号名

#Shared RSS links from other users [for kindleear.appspot.com only]
class SharedRss(MyBaseModel):
    __kind__ = "SharedRss"
    title = fields.StringField()
    url = fields.StringField()
    isfulltext = fields.BooleanField()
    language = fields.StringField()
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
