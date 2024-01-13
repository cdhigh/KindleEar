#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#管理订阅页面

import datetime
from operator import attrgetter
from urllib.parse import urljoin
from flask import Blueprint, render_template, request, redirect, url_for
from apps.base_handler import *
from apps.back_end.db_models import *
from lib.urlopener import UrlOpener
from books import BookClasses, BookClass
from books.base_comic_book import BaseComicBook
from books.comic import ComicBaseClasses
from config import *
from apps.view.library import KINDLEEAR_SITE, SHARED_LIBRARY_MGR_KINDLEEAR, SHARED_LIB_MGR_CMD_SUBSFROMSHARED

bpSubscribe = Blueprint('bpSubscribe', __name__)

#管理我的订阅和杂志列表
@bpSubscribe.route("/my", endpoint='MySubscription')
@bpSubscribe.route("/my/<tips>", endpoint='MySubscription')
@login_required
def MySubscription(tips=None):
    user = get_login_user()
    titleToAdd = request.args.get('title_to_add')
    urlToAdd = request.args.get('url_to_add')
    myfeeds = user.own_feeds.feeds if user.own_feeds else None
    books = list(Book.all().filter("builtin = ", True))
    # 简单排个序，为什么不用数据库直接排序是因为Datastore数据库需要建立索引才能排序
    books.sort(key=attrgetter("title"))

    return render_page("my.html", tab="my", user=user, books=books,
        myfeeds=myfeeds, comic_base_classes=ComicBaseClasses, tips=tips,
        subscribe_url=url_for("MySubscription"), title_to_add=titleToAdd,
        url_to_add=urlToAdd)

@bpSubscribe.post("/my", endpoint='MySubscriptionPost')
@login_required
def MySubscriptionPost():  # 添加自定义RSS
    user = get_login_user()
    form = request.form
    title = form.get('rss_title')
    url = form.get('url')
    isfulltext = bool(form.get('fulltext'))
    if not title or not url:
        return redirect(url_for("MySubscription", tips=(_("Title or url is empty!"))))

    if not url.lower().startswith('http'): #http and https
        url = 'https://' + url

    #判断是否重复
    if url.lower() in (item.url.lower() for item in user.own_feeds.feeds):
        return redirect(url_for("MySubscription", tips=(_("Duplicated subscription!"))))

    Feed(title=title, url=url, book=user.own_feeds, isfulltext=isfulltext,
        time=datetime.datetime.utcnow()).put()
    return redirect(url_for("MySubscription"))

#添加/删除自定义RSS订阅的AJAX处理函数
@bpSubscribe.post("/feeds/<actType>", endpoint='FeedsAjaxPost')
@login_required(forAjax=True)
def FeedsAjaxPost(self, actType):
    user = get_login_user(forAjax=True)
    form = request.form
    actType = actType.lower()

    if actType == 'delete':
        try:
            feedId = int(form.get('feedid'))
        except:
            return {'status': _('The id is invalid!')}

        feed = Feed.get_by_id(feedId)
        if feed:
            feed.delete()
            return {'status': 'ok'}
        else:
            return {'status': _('The feed ({}) not exist!').format(feedId)}
    elif actType == 'add':
        title = form.get('title')
        url = form.get('url')
        isfulltext = bool(form.get('fulltext', '').lower() == 'true')
        fromSharedLibrary = bool(form.get('fromsharedlibrary', '').lower() == 'true')

        respDict = {'status':'ok', 'title':title, 'url':url, 'isfulltext':isfulltext}

        if not title or not url:
            respDict['status'] = _("Title or Url is empty!")
            return respDict

        if not url.lower().startswith('http'):
            url = 'https://' + url
            respDict['url'] = url

        #判断是否重复
        if url.lower() in (item.url.lower() for item in user.own_feeds.feeds):
            respDict['status'] = _("Duplicated subscription!")
            return respDict

        fd = Feed(title=title, url=url, book=user.own_feeds, isfulltext=isfulltext,
            time=datetime.datetime.utcnow())
        fd.put()
        respDict['feedid'] = fd.key().id()
        
        #如果是从共享库中订阅的，则通知共享服务器，提供订阅数量信息，以便排序
        if fromSharedLibrary:
            SendNewSubscription(title, url)

        return respDict
    else:
        return {'status': 'Unknown command: {}'.format(actType)}

#通知共享服务器，有一个新的订阅
def SendNewSubscription(title, url):
    opener = UrlOpener()
    path = SHARED_LIBRARY_MGR_KINDLEEAR + SHARED_LIB_MGR_CMD_SUBSFROMSHARED
    srvUrl = urljoin(KINDLEEAR_SITE, path)
    data = {'title': title, 'url': url}
    opener.open(srvUrl, data) #只管杀不管埋，不用管能否成功了

#订阅/退订内置书籍的AJAX处理函数
@bpSubscribe.post("/books/<actType>", endpoint='BooksAjaxPost')
@login_required
def BooksAjaxPost(self, actType):
    user = get_login_user(forAjax=True)
    form = request.form
    try:
        id_ = int(form.get('id_'))
    except:
        return {'status': _('The id is invalid!')}

    bk = Book.get_by_id(id_)
    if not bk:
        return {'status': _('The book ({}) not exist!').format(id_)}

    actType = actType.lower()
    if actType == 'unsubscribe':
        if user.name in bk.users:
            bk.users.remove(user.name)
            bk.separate = False
            bk.put()

        #为安全起见，退订后也删除网站登陆信息（如果有的话）
        subsInfo = user.subscription_info(bk.title)
        if subsInfo:
            subsInfo.delete()

        return {'status':'ok', 'title': bk.title, 'desc': bk.description}
    elif actType == 'subscribe':
        separate = form.get('separate')

        respDict = {'status': 'ok'}

        bkcls = BookClass(bk.title)
        if not bkcls:
            return {'status': 'The book ({}) not exist!'.format(id_)}

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
        return respDict
    else:
        return {'status': 'Unknown command: {}'.format(actType)}

#订阅一本书
@bpSubscribe.route("/subscribe/<id_>", endpoint='Subscribe')
@login_required
def Subscribe(id_):
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
    return redirect(url_for("MySubscription"))

#取消一个订阅
@bpSubscribe.route("/unsubscribe/<id_>", endpoint='Unsubscribe')
@login_required
def Unsubscribe(self, id_):
    user = get_login_user()
    try:
        id_ = int(id_)
    except:
        return "The id is invalid!<br />"

    bk = Book.get_by_id(id_)
    if not bk:
        return 'The book ({}) not exist!'.format(id_)

    if session.userName in bk.users:
        bk.users.remove(session.userName)
        bk.separate = False
        bk.put()

    #为安全起见，退订后也删除网站登陆信息（如果有的话）
    subsInfo = user.subscription_info(bk.title)
    if subsInfo:
        subsInfo.delete()

    return redirect(url_for("MySubscription"))

@bpSubscribe.route("/delfeed/<id_>", endpoint='DelFeed')
@login_required
def DelFeed(id_):
    user = get_login_user()
    try:
        id_ = int(id_)
    except:
        return "The id is invalid!<br />"

    feed = Feed.get_by_id(id_)
    if feed:
        feed.delete()

    return redirect(url_for("MySubscription"))

#修改书籍的网站登陆信息
@bpSubscribe.route("/booklogininfo/<id_>", endpoint='BookLoginInfo')
@login_required
def BookLoginInfo(id_, tips=None):
    user = get_login_user()
    try:
        bk = Book.get_by_id(int(id_))
    except:
        bk = None
    if not bk:
        return 'The book not exist!'

    subsInfo = user.subscription_info(bk.title)
    return render_template('booklogininfo.html', bk=bk, subs_info=subsInfo, tips=tips)

@bpSubscribe.post("/booklogininfo/<id_>", endpoint='BookLoginInfoPost')
@login_required
def BookLoginInfoPost(id_):
    user = get_login_user()
    account = request.form.get('account')
    password = request.form.get('password')

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

    return redirect(url_for("MySubscription"))
