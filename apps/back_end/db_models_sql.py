#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#关系数据库行结构定义，使用peewee ORM
#根据以前的经验，经常出现有网友部署时没有成功建立数据库索引，所以现在排序在应用内处理，数据量不大
#Author: cdhigh <https://github.com/cdhigh>
import os, sys, json, datetime
from operator import attrgetter

if __name__ == '__main__': #调试使用，调试时为了单独执行此文件
    thisDir = os.path.dirname(os.path.abspath(__file__))
    appDir = os.path.normpath(os.path.join(thisDir, "..", ".."))
    sys.path.insert(0, appDir)
    sys.path.insert(0, os.path.join(appDir, 'lib'))
from apps.utils import ke_encrypt, ke_decrypt
from peewee import *
from playhouse.db_url import connect
from playhouse.shortcuts import model_to_dict
from config import (DATABASE_ENGINE, DATABASE_HOST, DATABASE_PORT, DATABASE_USERNAME, 
                DATABASE_PASSWORD, DATABASE_NAME)

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
class JSONField(TextField):
    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        if value is not None:
            return json.loads(value)

    @classmethod
    def list_default(cls):
        return []
    @classmethod
    def dict_default(cls):
        return {}

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

    #将当前行数据转换为一个字典结构，由子类使用，将外键转换为ID，日期转换为字符串
    #可以传入 only=[Book.title, ...]，或 exclude=[]
    def to_dict(self, **kwargs):
        ret = model_to_dict(self, **kwargs)
        for key in ret:
            data = ret[key]
            if isinstance(data, datetime.datetime):
                ret[key] = data.strftime('%Y-%m-%d %H:%M:%S')
        return ret

#--------------db models----------------
#class Book(MyBaseModel):
#    title = CharField(unique=True)
#    description = CharField()
#    users = JSONField(default=JSONField.list_default) #有哪些账号订阅了这本书
#    builtin = BooleanField()
#    needs_subscription = BooleanField() #是否需要登陆网页
#    separated = BooleanField() #是否单独推送
    
    #====自定义书籍
#    language = CharField(default='')
#    masthead_file = CharField(default='') # GIF 600*60
#    cover_file = CharField(default='')
#    keep_image = BooleanField(default=True)
#    oldest_article = IntegerField(default=7)

    #feeds, owner 属性为KeUser自动添加的
    
class KeUser(MyBaseModel): # kindleEar User
    name = CharField(unique=True)
    passwd = CharField()
    expiration_days = IntegerField(default=0) #账号超期设置值，0为永久有效
    secret_key = CharField(default='')
    kindle_email = CharField(default='')
    email = CharField(default='') #可能以后用于重置密码之类的操作
    enable_send = BooleanField(default=False)
    send_days = JSONField(default=JSONField.list_default)
    send_time = IntegerField()
    timezone = IntegerField(default=0)
    book_type = CharField(default='epub') #mobi,epub
    device = CharField(default='')
    expires = DateTimeField(null=True) #超过了此日期后账号自动停止推送

    book_title = CharField()
    use_title_in_feed = BooleanField(default=True) # 文章标题优先选择订阅源中的还是网页中的
    title_fmt = CharField(default='') #在元数据标题中添加日期的格式
    author_format = CharField(default='') #修正Kindle 5.9.x固件的bug【将作者显示为日期】
    book_mode = CharField(default='') #书籍模式，'periodical'|'comic'，漫画模式可以直接全屏
    merge_books = BooleanField(default=True) #是否合并书籍成一本
    remove_hyperlinks = CharField(default='') #去掉文本或图片上的超链接{'' | 'image' | 'text' | 'all'}
    keep_image = BooleanField(default=True)
    oldest_article = IntegerField(default=7)
    book_language = CharField() #自定义RSS的语言
    enable_custom_rss = BooleanField(default=True)

    share_key = CharField(default='')
    share_links = JSONField(default=JSONField.dict_default) #evernote/wiz/pocket/instapaper包含子字典，微博/facebook/twitter等仅包含0/1
    share_fuckgfw = BooleanField(default=False) #归档和分享时是否需要翻墙

    cover = BlobField(null=True) #保存各用户的自定义封面图片二进制内容
    css_content = TextField(default='') #保存用户上传的css样式表
    sg_enable = BooleanField(default=False)
    sg_apikey = CharField(default='')
    custom = JSONField(default=JSONField.dict_default) #留着扩展，避免后续一些小特性还需要升级数据表结构
    
    #自己直接所属的自定义RSS列表，返回[Recipe,]
    def all_custom_rss(self):
        return sorted(Recipe.select().where(Recipe.user == self.name).where(Recipe.type_ == 'custom'), 
            key=attrgetter('time'), reverse=True)

    #自己直接所属的上传Recipe列表，返回[Recipe,]
    def all_uploaded_recipe(self):
        return sorted(Recipe.select().where(Recipe.user == self.name).where(Recipe.type_ == 'upload'), 
            key=attrgetter('time'), reverse=True)

    #自己订阅的Recipe，如果传入recipe_id，则使用id筛选，返回一个，否则返回一个列表
    def get_booked_recipe(self, recipe_id=None):
        if recipe_id:
            return BookedRecipe.select().where(BookedRecipe.user == self.name).where(BookedRecipe.recipe_id == recipe_id).first()
        else:
            return sorted(BookedRecipe.get_all(BookedRecipe.user == self.name), key=attrgetter('time'), reverse=True)

    #本用户所有的白名单
    def white_lists(self):
        return WhiteList.get_all(WhiteList.user == self.name)
    def url_filters(self):
        return UrlFilter.get_all(UrlFilter.user == self.name)

    #删除自己订阅的书，白名单，过滤器等，就是完全的清理，预备用于删除此账号
    def erase_traces(self):
        BookedRecipe.delete().where(BookedRecipe.user == self.name).execute()
        Recipe.delete().where(Recipe.user == self.name).execute()
        WhiteList.delete().where(WhiteList.user == self.name).execute()
        UrlFilter.delete().where(UrlFilter.user == self.name).execute()
        DeliverLog.delete().where(DeliverLog.username == self.name).execute() #推送记录
            
#RSS订阅源，包括自定义RSS，上传的recipe，内置在zip里面的builtin_recipe不包括在内
#每个Recipe的字符串表示为：custom:id, upload:id
class Recipe(MyBaseModel):
    title = CharField()
    url = CharField(default='')
    description = CharField(default='')
    isfulltext = BooleanField(default=False)
    type_ = CharField() #'custom','upload'
    needs_subscription = BooleanField(default=False) #是否需要登陆网页，只有上传的recipe才有意义
    src = TextField(default='') #保存上传的recipe的unicode字符串表示，已经解码
    time = DateTimeField() #源被加入的时间，用于排序
    user = CharField() #哪个账号创建的，和nosql一致，保存用户名
    language = CharField(default='')

    #在程序内其他地方使用的id，在数据库内则使用 self.id
    @property
    def recipe_id(self):
        return '{}:{}'.format(self.type_, self.id)

    #将各种表示的recipe id转换回数据库id，返回 (type, id)
    @classmethod
    def type_and_id(cls, id_):
        id_ = str(id_)
        if ':' in id_:
            return id_.split(':', 1)
        elif id_.startswith(('custom__', 'upload__', 'builtin__')):
            return id_.split('__', 1)
        else:
            return '', id_

#已经被订阅的Recipe信息，包括自定义RSS/上传的recipe/内置builtin_recipe
class BookedRecipe(MyBaseModel):
    recipe_id = CharField()
    separated = BooleanField() #是否单独推送
    user = CharField()
    title = CharField()
    description = CharField()
    needs_subscription = BooleanField(default=False)
    account = CharField(default='') #如果网站需要登录才能看
    encrypted_pwd = CharField(default='')
    send_days = JSONField(default=JSONField.list_default)
    send_times = JSONField(default=JSONField.list_default)
    time = DateTimeField() #源被订阅的时间，用于排序

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
    username = CharField()
    to = CharField()
    size = IntegerField(default=0)
    time_str = CharField() #每个用户的时区可能不同，为显示方便，创建时就生成字符串
    datetime = DateTimeField(index=True)
    book = CharField(default='')
    status = CharField()
    
class WhiteList(MyBaseModel):
    mail = CharField()
    user = CharField()

class UrlFilter(MyBaseModel):
    url = CharField()
    user = CharField()

#Shared RSS links from other users [for kindleear.appspot.com only]
class SharedRss(MyBaseModel):
    title = CharField()
    url = CharField(default='')
    isfulltext = BooleanField(default=False)
    language = CharField(default='')
    category = CharField(default='')
    recipe_url = CharField(default='') #客户端优先使用此字段获取recipe，为什么不用上面的url是要和以前的版本兼容
    src = TextField(default='') #保存分享的recipe的unicode字符串表示，已经解码
    description = CharField(default='')
    creator = CharField(default='') #保存贡献者的md5
    created_time = DateTimeField(default=datetime.datetime.utcnow)
    subscribed = IntegerField(default=0) #for sort
    last_subscribed_time = DateTimeField(default=datetime.datetime.utcnow, index=True)
    invalid_report_days = IntegerField(default=0) #some one reported it is a invalid link
    last_invalid_report_time = DateTimeField(default=datetime.datetime.utcnow) #a rss will be deleted after some days of reported_invalid

    #返回数据库中所有的分类
    @classmethod
    def categories(self):
        return set([item.category for item in SharedRss.select(SharedRss.category)])
    
#Buffer for category of shared rss [for kindleear.appspot.com only]
class SharedRssCategory(MyBaseModel):
    name = CharField()
    last_updated = DateTimeField(index=True) #for sort

#当前使用:
#name='dbTableVersion'.int_value 行保存数据库格式版本
#name='lastSharedRssTime'.time_value 保存共享库的最新更新日期
class AppInfo(MyBaseModel):
    name = CharField()
    int_value = IntegerField(default=0)
    str_value = CharField(default='')
    time_value = DateTimeField(default=datetime.datetime.utcnow)
    description = CharField(default='')
    comment = CharField(default='')
    
#创建数据库表格，一个数据库只需要创建一次
#如果是sql数据库，可以使用force=True删掉之前的数据库文件
def CreateDatabaseTable(force=False):
    if DATABASE_ENGINE == "sqlite":
        if not force and os.path.exists(dbName):
            print(f'[Error] Database "{dbName}" already exists')
            return
        elif os.path.exists(dbName):
            try:
                os.remove(dbName)
            except:
                pass

    KeUser.create_table()
    Recipe.create_table()
    BookedRecipe.create_table()
    DeliverLog.create_table()
    WhiteList.create_table()
    UrlFilter.create_table()
    SharedRss.create_table()
    SharedRssCategory.create_table()
    AppInfo.create_table()
    
    AppInfo(name='dbTableVersion', int_value=__DB_VERSION__).save()
    print(f'Create database "{dbName}" finished')


if __name__ == '__main__':
    if DATABASE_ENGINE == 'sqlite':
        CreateDatabaseTable()
