#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#管理订阅页面

import datetime, json
from operator import attrgetter
from urllib.parse import urljoin
from bottle import route, request, post, redirect, response
from google.appengine.api import memcache
from apps.utils import etagged
from apps.base_handler import *
from apps.db_models import *
from lib.urlopener import UrlOpener
from books import BookClasses, BookClass
from books.base_comic_book import BaseComicBook
from books.comic import ComicBaseClasses
from config import *
from apps.view.library import KINDLEEAR_SITE, SHARED_LIBRARY_MGR_KINDLEEAR, SHARED_LIB_MGR_CMD_SUBSFROMSHARED

# 管理我的订阅和杂志列表
@route("/my")
def MySubscription(self, tips=None):
    user = get_current_user()
    query = request.query
    titleToAdd = query.title_to_add
    urlToAdd = query.url_to_add
    myfeeds = user.own_feeds.feeds if user.own_feeds else None
    books = list(Book.all().filter("builtin = ", True))
    # 简单排个序，为什么不用数据库直接排序是因为Datastore数据库需要建立索引才能排序
    books.sort(key=attrgetter("title"))

    return render_page("my.html", "Feeds", current="my", user=user, books=books,
        myfeeds=myfeeds, comic_base_classes=ComicBaseClasses, tips=tips,
        subscribe_url=urlparse.urljoin(DOMAIN, self.__url__), title_to_add=titleToAdd,
        url_to_add=urlToAdd)

@post("/my")
def MySubscriptionPost():  # 添加自定义RSS
    user = get_current_user()
    forms = request.forms
    title = forms.t
    url = forms.url
    isfulltext = bool(forms.get('fulltext'))
    if not title or not url:
        return MySubscription(_("Title or url is empty!"))

    if not url.lower().startswith('http'): #http and https
        url = 'https://' + url

    #判断是否重复
    if url.lower() in (item.url.lower() for item in user.own_feeds.feeds):
        return MySubscription(_("Duplicated subscription!"))

    Feed(title=title, url=url, book=user.own_feeds, isfulltext=isfulltext,
        time=datetime.datetime.utcnow()).put()
    memcache.delete('{}.feedscount'.format(user.own_feeds.key().id()))
    redirect('/my')

#添加/删除自定义RSS订阅的AJAX处理函数
@post("/feeds/<actType>")
def FeedsAjaxPost(self, actType):
    user = get_current_user(forAjax=True)
    response.content_type = 'application/json'
    forms = request.forms
    actType = actType.lower()

    if actType == 'delete':
        feedId = forms.feedid
        try:
            feedId = int(feedId)
        except:
            return json.dumps({'status': _('The id is invalid!')})

        feed = Feed.get_by_id(feedId)
        if feed:
            feed.delete()
            return json.dumps({'status': 'ok'})
        else:
            return json.dumps({'status': _('The feed ({}) not exist!').format(feedId)})
    elif actType == 'add':
        title = forms.title
        url = forms.url
        isfulltext = bool(forms.get('fulltext', '').lower() == 'true')
        fromSharedLibrary = bool(forms.get('fromsharedlibrary', '').lower() == 'true')

        respDict = {'status':'ok', 'title':title, 'url':url, 'isfulltext':isfulltext}

        if not title or not url:
            respDict['status'] = _("Title or Url is empty!")
            return json.dumps(respDict)

        if not url.lower().startswith('http'):
            url = 'https://' + url
            respDict['url'] = url

        #判断是否重复
        if url.lower() in (item.url.lower() for item in user.own_feeds.feeds):
            respDict['status'] = _("Duplicated subscription!")
            return json.dumps(respDict)

        fd = Feed(title=title, url=url, book=user.own_feeds, isfulltext=isfulltext,
            time=datetime.datetime.utcnow())
        fd.put()
        respDict['feedid'] = fd.key().id()
        memcache.delete('{}.feedscount'.format(user.own_feeds.key().id()))

        #如果是从共享库中订阅的，则通知共享服务器，提供订阅数量信息，以便排序
        if fromSharedLibrary:
            SendNewSubscription(title, url)

        return json.dumps(respDict)
    else:
        return json.dumps({'status': 'Unknown command: {}'.format(actType)})

#通知共享服务器，有一个新的订阅
def SendNewSubscription(title, url):
    opener = UrlOpener()
    path = SHARED_LIBRARY_MGR_KINDLEEAR + SHARED_LIB_MGR_CMD_SUBSFROMSHARED
    srvUrl = urljoin(KINDLEEAR_SITE, path)
    data = {'title': title, 'url': url}
    opener.open(srvUrl, data) #只管杀不管埋，不用管能否成功了

#订阅/退订内置书籍的AJAX处理函数
@post("/books/<actType>")
def BooksAjaxPost(self, actType):
    user = get_current_user(forAjax=True)
    response.content_type = 'application/json'
    forms = request.forms
    id_ = forms.id_
    try:
        id_ = int(id_)
    except:
        return json.dumps({'status': _('The id is invalid!')})

    bk = Book.get_by_id(id_)
    if not bk:
        return json.dumps({'status': _('The book ({}) not exist!').format(id_)})

    actType = actType.lower()
    if actType == 'unsubscribe':
        if user.name in bk.users:
            bk.users.remove(user.name)
            bk.separate = False
            bk.put()

        #为安全起见，退订后也删除网站登陆信息（如果有的话）
        subs_info = user.subscription_info(bk.title)
        if subs_info:
            subs_info.delete()

        return json.dumps({'status':'ok', 'title': bk.title, 'desc': bk.description})
    elif actType == 'subscribe':
        separate = forms.separate

        respDict = {'status':'ok'}

        bkcls = BookClass(bk.title)
        if not bkcls:
            return json.dumps({'status': 'The book ({}) not exist!'.format(id_)})

        #如果是漫画类，则不管是否选择了“单独推送”，都自动变成“单独推送”
        if issubclass(bkcls, BaseComicBook):
            separate = 'true'

        if user.name not in bk.users:
            bk.users.append(user.name)
            bk.separate = bool(separate.lower() in ('true', '1'))
            bk.put()

        respDict['title'] = bk.title
        respDict['desc'] = bk.description
        respDict['needs_subscription'] = bk.needs_subscription
        respDict['subscription_info'] = bool(user.subscription_info(bk.title))
        respDict['separate'] = bk.separate
        return json.dumps(respDict)
    else:
        return json.dumps({'status': 'Unknown command: {}'.format(actType)})

#订阅一本书
@route("/subscribe/<id_>")
def Subscribe(id_):
    session = login_required()
    try:
        id_ = int(id_)
    except:
        return "The id is invalid!<br />"

    bk = Book.get_by_id(id_)
    if not bk:
        return 'The book ({}) not exist!'.format(id_)

    bkcls = BookClass(bk.title)
    if not bkcls:
        return 'The book ({}) not exist!'.format(id_)

    #如果是漫画类，则不管是否选择了“单独推送”，都自动变成“单独推送”
    if issubclass(bkcls, BaseComicBook):
        separate = 'true'
    else:
        separate = request.query.get('separate', 'true')

    if session.userName not in bk.users:
        bk.users.append(session.userName)
        bk.separate = bool(separate in ('true', '1'))
        bk.put()
    redirect('/my')

#取消一个订阅
@route("/unsubscribe/<id_>")
def Unsubscribe(self, id_):
    user = get_current_user()
    try:
        id_ = int(id_)
    except:
        return "The id is invalid!<br />"

    bk = Book.get_by_id(id_)
    if not bk:
        return 'The book ({}) not exist!'.format(id_)

    session = current_session()
    if session.userName in bk.users:
        bk.users.remove(session.userName)
        bk.separate = False
        bk.put()

    #为安全起见，退订后也删除网站登陆信息（如果有的话）
    subsInfo = user.subscription_info(bk.title)
    if subsInfo:
        subsInfo.delete()

    redirect('/my')

@route("/delfeed/<id_>")
def DelFeed(id_):
    user = get_current_user()
    try:
        id_ = int(id_)
    except:
        return "The id is invalid!<br />"

    feed = Feed.get_by_id(id_)
    if feed:
        feed.delete()

    redirect('/my')

@route("/booklogininfo/<id_>")
#修改书籍的网站登陆信息
def BookLoginInfo(self, id_, tips=None):
    user = get_current_user()
    try:
        bk = Book.get_by_id(int(id_))
    except:
        bk = None
    if not bk:
        return 'The book not exist!'

    subsInfo = user.subscription_info(bk.title)
    return render_page('booklogininfo.html', "Book Login Infomation", bk=bk, subs_info=subsInfo, tips=tips)

@post("/booklogininfo/<id_>")
def BookLoginInfoPost(id_):
    user = get_current_user()
    account = request.forms.account
    password = request.forms.password

    try:
        bk = Book.get_by_id(int(id_))
    except:
        bk = None
    if not bk:
        return 'The book not exist!'

    subsInfo = user.subscription_info(bk.title)
    if subsInfo:
        #任何一个留空则删除登陆信息
        if not account or not password:
            subsInfo.delete()
        else:
            subsInfo.account = account
            subsInfo.password = password
            subsInfo.put()
    elif account and password:
        subsInfo = SubscriptionInfo(account=account, user=user, title=bk.title)
        subsInfo.put() #先保存一次才有user信息，然后才能加密
        subsInfo.password = password
        subsInfo.put()

    redirect('/my')
