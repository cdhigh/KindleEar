#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#网友共享的订阅源数据
import datetime
from urllib.parse import urljoin
from flask import Blueprint, render_template, request, current_app
from flask_babel import gettext as _
from apps.base_handler import *
from apps.utils import str_to_bool
from apps.back_end.db_models import *
from lib.urlopener import UrlOpener
from .library_offical import *

bpLibrary = Blueprint('bpLibrary', __name__)

GITHUB_SHARED_RSS = 'https://github.com/cdhigh/KindleEar/tree/master/books/shared_rss.json'

#给网友提供共享的订阅源数据，初始只返回一个空白页，然后在页面内使用ajax获取数据，参加 SharedLibraryMgrPost()
@bpLibrary.route("/library", endpoint='SharedLibrary')
@login_required()
def SharedLibrary():
    user = get_login_user()
    tips = ''
    return render_template('library.html', tab='shared', user=user, tips=tips)

def buildKeUrl(path, url=KINDLEEAR_SITE):
    return urljoin('http://localhost:5000/', path) if current_app.debug else urljoin(url, path)
def srvErrStr(status_code, url=KINDLEEAR_SITE):
    return _('Cannot fetch data from {}, status: {}').format(url, UrlOpener.CodeMap(status_code))

#用户分享了一个订阅源，可能为自定义RSS或上传的recipe
@bpLibrary.post("/library", endpoint='SharedLibraryPost')
@login_required(forAjax=True)
def SharedLibraryPost():
    user = get_login_user()
    form = request.form
    recipeId = form.get('id')
    category = form.get('category')
    lang = form.get('lang', '').lower()
    isfulltext = str_to_bool(form.get('isfulltext', ''))
    creator = form.get('creator')

    recipeType, dbId = Recipe.type_and_id(recipeId)
    recipe = Recipe.get_by_id_or_none(dbId)
    if not recipe:
        return {'status': _('The recipe does not exist.')}

    opener = UrlOpener()
    url = buildKeUrl(LIBRARY_KINDLEEAR)
    data = {'category': category, 'title': recipe.title, 'url': recipe.url, 'lang': lang, 'isfulltext': recipe.isfulltext,
         'src': recipe.src, 'description':recipe.description, 'key': KINDLEEAR_SITE_KEY, 'creator': creator}
    
    resp = opener.open(url, data)
    if resp.status_code == 200:
        return resp.json()
    else:
        return {'status': srvErrStr(resp.status_code)}

#网友分享库的一些操作，包括获取更新时间，获取源信息，报告失效等
@bpLibrary.post("/library/mgr/<mgrType>", endpoint='SharedLibraryMgrPost')
@login_required(forAjax=True)
def SharedLibraryMgrPost(mgrType):
    user = get_login_user()
    form = request.form
    opener = UrlOpener()
    if mgrType == LIBRARY_GETLASTTIME: #获取分享库的最近更新时间
        url = buildKeUrl(LIBRARY_KINDLEEAR)
        resp = opener.open(f'{url}?key={KINDLEEAR_SITE_KEY}&data_type={LIBRARY_GETLASTTIME}')
        if resp.status_code == 200:
            return resp.json()
        else:
            return {'status': srvErrStr(resp.status_code)}
    elif mgrType == LIBRARY_GETRSS: #获取分享库的RSS列表
        #一个来源是"官方"KindleEar库
        rssList = []
        ret = {'status': 'ok'}
        url = buildKeUrl(LIBRARY_KINDLEEAR)
        resp = opener.open(f'{url}?key={KINDLEEAR_SITE_KEY}&data_type={LIBRARY_GETRSS}')
        keRss = []
        if resp.status_code == 200:
            keRss = resp.json()
        else:
            ret['status'] = srvErrStr(resp.status_code)

        #另一个来源是github分享库
        resp = opener.open(GITHUB_SHARED_RSS)
        if resp.status_code == 200:
            recipes = resp.json()
            if isinstance(recipes, list): #去掉重复项
                existingUrls = {item.get('u') for item in keRss}
                for item in recipes:
                    if item.get('u') not in existingUrls:
                        keRss.append(item)
        #elif ret['status'] == 'ok':
        #    ret['status'] = srvErrStr(resp.status_code, 'github')
        ret['data'] = keRss
        return ret
    elif mgrType == LIBRARY_REPORT_INVALID: #报告一个源失效了
        url = buildKeUrl(LIBRARY_MGR + mgrType)
        title = form.get('title', '')
        feedUrl = form.get('url', '')
        recipeId = form.get('recipeId', '') #当前仅用于数据库ID
        data = {'title': title, 'url': feedUrl, 'recipeId': recipeId, 'key': KINDLEEAR_SITE_KEY}
        resp = opener.open(url, data)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {'status': srvErrStr(resp.status_code)}
    else:
        return {'status': 'Unknown command: {}'.format(mgrType)}

#获取共享的订阅源的分类信息
@bpLibrary.route("/library/category", endpoint='SharedLibraryCategory')
@login_required(forAjax=True)
def SharedLibraryCategory():
    user = get_login_user()
    
    #连接分享服务器获取数据
    respDict = {'status': 'ok', 'categories': []}

    opener = UrlOpener()
    url = buildKeUrl(LIBRARY_CATEGORY)
    resp = opener.open(f'{url}?key={KINDLEEAR_SITE_KEY}')

    if resp.status_code == 200:
        respDict['categories'] = resp.json()
    else:
        respDict['status'] = srvErrStr(resp.status_code)

    return respDict

