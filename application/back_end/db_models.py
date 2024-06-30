#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#数据库结构定义，使用这个文件隔离sql和nosql的差异，尽量向外提供一致的接口
#Visit <https://github.com/cdhigh/KindleEar> for the latest version
#Author: cdhigh <https://github.com/cdhigh>
import os, sys, random, datetime
from operator import attrgetter
from ..utils import PasswordManager, ke_encrypt, ke_decrypt, tz_now

if os.getenv('DATABASE_URL', '').startswith(("datastore", "mongodb", "redis", "pickle")):
    from .db_models_nosql import *
else:
    from .db_models_sql import *

class KeUser(MyBaseModel): # kindleEar User
    name = CharField(unique=True)
    passwd_hash = CharField()
    
    send_days = JSONField(default=JSONField.list_default)
    send_time = IntegerField(default=6)
    expiration_days = IntegerField(default=0) #账号超期设置值，0为永久有效
    expires = DateTimeField(null=True) #超过了此日期后账号自动停止推送
    created_time = DateTimeField(default=datetime.datetime.utcnow)

    #email,sender,kindle_email,secret_key,enable_send,timezone,inbound_email,
    #keep_in_email_days,delivery_mode,webshelf_days,reader_params
    #sender: 可能等于自己的email，也可能是管理员的email
    #delivery_mode: 推送模式：['email' | 'local' | 'email,local']
    base_config = JSONField(default=JSONField.dict_default)
    
    #device,type,title,title_fmt,author_fmt,mode,time_fmt,oldest_article,language,rm_links,
    #rm_links: 去掉文本或图片上的超链接{'' | 'image' | 'text' | 'all'}
    book_config = JSONField(default=JSONField.dict_default)
    
    share_links = JSONField(default=JSONField.dict_default) #evernote/wiz/pocket/instapaper包含子字典，微博/facebook/twitter等仅包含0/1
    covers = JSONField(default=JSONField.dict_default) #保存封面图片数据库ID {'order':,'cover0':,...'cover6':}
    send_mail_service = JSONField(default=JSONField.dict_default) #{'service':,...}
    custom = JSONField(default=JSONField.dict_default) #留着扩展，避免后续一些小特性还需要升级数据表结构
    
    #通过这两个基本配置信息的函数，提供一些合理的初始化值
    def cfg(self, item, default=None):
        value = self.base_config.get(item, default)
        if value is None:
            return {'email': '', 'kindle_email': '', 'secret_key': '', 'timezone': 0,
                'inbound_email': 'save,forward', 'keep_in_email_days': 1,
                'delivery_mode': 'email,local', 'webshelf_days': 7,
                'reader_params': {}}.get(item, value)
        else:
            return value
    def set_cfg(self, item, value):
        cfg = self.base_config
        cfg[item] = value
        self.base_config = cfg

    #通过这两个关于书籍的配置信息的函数，提供一些合理的初始化值
    def book_cfg(self, item, default=None):
        value = self.book_config.get(item, default)
        if value is None:
            return {'type': 'epub', 'title': 'KindleEar', 'time_fmt': '%Y-%m-%d', 'oldest_article': 7,
                'language': 'en'}.get(item, value)
        else:
            return value
    def set_book_cfg(self, item, value):
        cfg = self.book_config
        cfg[item] = value
        self.book_config = cfg

    #自己直接所属的自定义RSS列表，返回[Recipe,]
    def all_custom_rss(self):
        return sorted(Recipe.select().where((Recipe.user == self.name) & (Recipe.type_ == 'custom')), 
            key=attrgetter('time'), reverse=True)

    #自己直接所属的上传Recipe列表，返回[Recipe,]
    def all_uploaded_recipe(self):
        return sorted(Recipe.select().where((Recipe.user == self.name) & (Recipe.type_ == 'upload')), 
            key=attrgetter('time'), reverse=True)

    #自己订阅的Recipe，如果传入recipe_id，则使用id筛选，返回一个，否则返回一个列表
    def get_booked_recipe(self, recipe_id=None):
        if recipe_id:
            return BookedRecipe.select().where((BookedRecipe.user == self.name) & (BookedRecipe.recipe_id == recipe_id)).first()
        else:
            return sorted(BookedRecipe.get_all(BookedRecipe.user == self.name), key=attrgetter('time'), reverse=True)

    #本用户所有的白名单
    def white_lists(self):
        return WhiteList.get_all(WhiteList.user == self.name)
    
    #删除自己订阅的书，白名单，过滤器等，就是完全的清理，预备用于删除此账号
    def erase_traces(self):
        BookedRecipe.delete().where(BookedRecipe.user == self.name).execute()
        Recipe.delete().where(Recipe.user == self.name).execute()
        WhiteList.delete().where(WhiteList.user == self.name).execute()
        DeliverLog.delete().where(DeliverLog.user == self.name).execute()
        UserBlob.delete().where(UserBlob.user == self.name).execute()
        LastDelivered.delete().where(LastDelivered.user == self.name).execute()

    #获取封面二进制数据
    def get_cover_data(self):
        data = b''
        covers = self.covers or {}
        order = covers.get('order', 'random')
        idx = random.randint(0, 6) if (order == 'random') else self.local_time().weekday()
        coverName = f'cover{idx}'
        cover = covers.get(coverName, f'/images/{coverName}.jpg')
        if cover.startswith('/images/'):
            cover = cover[1:]
            try:
                with open(os.path.join(appDir, 'application', cover), 'rb') as f:
                    data = f.read()
            except:
                data = b''
        elif cover.startswith('/dbimage/'):
            dbItem = UserBlob.get_by_id_or_none(cover[9:])
            data = dbItem.data if dbItem else b''
        return data

    #获取用户自定义的CSS
    def get_extra_css(self):
        dbItem = UserBlob.get_or_none((UserBlob.user == self.name) & (UserBlob.name == 'css'))
        return dbItem.data.decode('utf-8') if dbItem else ''

    #根据设置，获取发送邮件的配置数据
    def get_send_mail_service(self):
        adminName = os.environ.get('ADMIN_NAME')
        srv = self.send_mail_service
        if (self.name != adminName) and (srv.get('service') == 'admin'):
            dbItem = KeUser.get_or_none(KeUser.name == adminName)
            srv = dbItem.send_mail_service if dbItem else {}
            if srv.get('service') == 'smtp':
                srv = srv.copy()
                srv['password'] = dbItem.decrypt(srv.get('password'))
        elif srv.get('service') == 'smtp':
            srv = srv.copy()
            srv['password'] = self.decrypt(srv.get('password'))
        return srv

    #使用自身的密钥加密和解密字符串
    def encrypt(self, txt) -> str:
        return ke_encrypt((txt or ''), self.cfg('secret_key')) #type:ignore
    def decrypt(self, txt) -> str:
        return ke_decrypt((txt or ''), self.cfg('secret_key')) #type:ignore
    def hash_text(self, txt) -> str:
        return PasswordManager(self.cfg('secret_key')).create_hash(txt)
    def verify_password(self, password) -> bool:
        new_hash = PasswordManager(self.cfg('secret_key')).migrate_password(self.passwd_hash, password)
        if not new_hash:
            return False
        if new_hash != self.passwd_hash: #迁移至更安全的hash
            self.passwd_hash = new_hash
            self.save()
        return True

    #自定义字典的设置
    def set_custom(self, item, value):
        custom = self.custom
        if value is None:
            custom.pop(item, None)
        else:
            custom[item] = value
        self.custom = custom
        return self

    #返回用户的本地时间，如果参数 fmt 非空，则返回字符串表达，否则返回datetime实例
    def local_time(self, fmt=None):
        tm = datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=self.cfg('timezone'))))
        return tm.strftime(fmt) if fmt else tm
        
#用户的一些二进制内容，比如封面之类的
class UserBlob(MyBaseModel):
    name = CharField()
    user = CharField()
    time = DateTimeField(default=datetime.datetime.utcnow)
    data = BlobField(null=True, index=False)

#RSS订阅源，包括自定义RSS，上传的recipe，内置在zip里面的builtin_recipe不包括在内
#每个Recipe的字符串表示为：custom:id, upload:id
class Recipe(MyBaseModel):
    title = CharField()
    url = CharField(default='')
    description = CharField(default='')
    isfulltext = BooleanField(default=False) #只有自定义RSS才有意义
    type_ = CharField() #'custom','upload'
    needs_subscription = BooleanField(default=False) #是否需要登陆网页，只有上传的recipe才有意义
    src = TextField(default='', index=False) #保存上传的recipe的unicode字符串表示，已经解码
    time = DateTimeField(default=datetime.datetime.utcnow) #源被加入的时间，用于排序
    user = CharField() #哪个账号创建的，和nosql一致，保存用户名
    language = CharField(default='')
    translator = JSONField(default=JSONField.dict_default) #用于自定义RSS的备份，实际使用的是BookedRecipe
    tts = JSONField(default=JSONField.dict_default) #用于自定义RSS的备份，实际使用的是BookedRecipe
    custom = JSONField(default=JSONField.dict_default) #留着扩展，避免后续一些小特性还需要升级数据表结构

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
    recipe_id = CharField() #这个ID不是Recipe数据库ID，而是 builtin:xxx, upload:xxx, custom:xxx
    separated = BooleanField() #是否单独推送
    user = CharField()
    title = CharField()
    description = CharField()
    needs_subscription = BooleanField(default=False)
    account = CharField(default='') #如果网站需要登录才能看
    encrypted_pwd = CharField(default='')
    send_days = JSONField(default=JSONField.dict_default) #{'type':'weekday/date','days':[]}
    send_times = JSONField(default=JSONField.list_default)
    time = DateTimeField(default=datetime.datetime.utcnow) #源被订阅的时间，用于排序
    translator = JSONField(default=JSONField.dict_default)
    tts = JSONField(default=JSONField.dict_default)
    custom = JSONField(default=JSONField.dict_default) #留着扩展，避免后续一些小特性还需要升级数据表结构
    
    @property
    def password(self):
        dbItem = KeUser.get_or_none(KeUser.name == self.user)
        return dbItem.decrypt(self.encrypted_pwd) if dbItem else ''
        
    @password.setter
    def password(self, pwd):
        dbItem = KeUser.get_or_none(KeUser.name == self.user)
        self.encrypted_pwd = dbItem.encrypt(pwd) if dbItem else ''

#书籍的推送历史记录
class DeliverLog(MyBaseModel):
    user = CharField()
    to = CharField()
    size = IntegerField(default=0)
    time_str = CharField() #每个用户的时区可能不同，为显示方便，创建记录时就生成推送时间字符串
    datetime = DateTimeField(default=datetime.datetime.utcnow)
    book = CharField(default='')
    status = CharField()
    
class WhiteList(MyBaseModel):
    mail = CharField()
    user = CharField()
    time = DateTimeField(default=datetime.datetime.utcnow)

#Shared RSS links from other users [for kindleear.appspot.com only]
class SharedRss(MyBaseModel):
    title = CharField(index=True)
    url = CharField(default='', index=True)
    isfulltext = BooleanField(default=False)
    language = CharField(default='')
    category = CharField(default='')
    recipe_url = CharField(default='') #客户端优先使用此字段获取recipe，为什么不用上面的url是要和以前的版本兼容
    src = TextField(default='', index=False) #保存分享的recipe的unicode字符串表示，已经解码
    description = CharField(default='')
    creator = CharField(default='') #保存贡献者的md5
    created_time = DateTimeField(default=datetime.datetime.utcnow)
    subscribed = IntegerField(default=0) #for sort
    last_subscribed_time = DateTimeField(default=datetime.datetime.utcnow, index=True)
    invalid_report_days = IntegerField(default=0) #some one reported it is a invalid link
    last_invalid_report_time = DateTimeField(default=datetime.datetime.utcnow) #a rss will be deleted after some days of reported_invalid
    custom = JSONField(default=JSONField.dict_default)

    #返回数据库中所有的分类
    @classmethod
    def categories(self):
        return set([item.category for item in SharedRss.select(SharedRss.category)])
    
#Buffer for category of shared rss [for kindleear.appspot.com only]
class SharedRssCategory(MyBaseModel):
    name = CharField()
    language = CharField(default='')
    last_updated = DateTimeField(default=datetime.datetime.utcnow)

class LastDelivered(MyBaseModel):
    user = CharField()
    bookname = CharField(default='')
    url = CharField(default='')
    num = IntegerField(default=0)
    record = CharField(default='')
    datetime = DateTimeField(default=datetime.datetime.utcnow)

class InBox(MyBaseModel):
    user = CharField()
    sender = CharField()
    to = CharField()
    subject = CharField()
    status = CharField()
    size = IntegerField(default=0)
    datetime = DateTimeField(default=datetime.datetime.utcnow)
    body = TextField(default='', index=False)
    attachments = CharField(default='') #存放UserBlob的数据库id，逗号分割

class AppInfo(MyBaseModel):
    name = CharField(unique=True)
    value = CharField(default='')
    description = CharField(default='')

    dbSchemaVersion = 'dbSchemaVersion'
    lastSharedRssTime = 'lastSharedRssTime'
    newUserMailService = 'newUserMailService'
    signupType = 'signupType'
    inviteCodes = 'inviteCodes'
    sharedRssLibraryUrl = 'sharedRssLibraryUrl'
    
    @classmethod
    def get_value(cls, name, default=''):
        dbItem = cls.get_or_none(AppInfo.name == name)
        return dbItem.value if dbItem else default

    @classmethod
    def set_value(cls, name, value):
        cls.replace(name=name, value=value).execute()
        
#创建数据库表格，一个数据库只需要创建一次
def create_database_tables():
    dbInstance.create_tables([KeUser, UserBlob, Recipe, BookedRecipe, DeliverLog, WhiteList,
        SharedRss, SharedRssCategory, LastDelivered, InBox, AppInfo], safe=True)
    if not AppInfo.get_value(AppInfo.dbSchemaVersion):
        AppInfo.set_value(AppInfo.dbSchemaVersion, appVer)
    
    return 'Created database tables successfully'

#删除所有表格的所有数据，相当于恢复出厂设置
def delete_database_all_data():
    for model in [KeUser, UserBlob, Recipe, BookedRecipe, DeliverLog, WhiteList,
        SharedRss, SharedRssCategory, LastDelivered, InBox, AppInfo]:
        try:
            model.delete().execute()
        except:
            pass
