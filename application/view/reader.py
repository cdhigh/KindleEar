#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#KindleEar在线RSS阅读器，为电子墨水屏进行了专门优化
#Author: cdhigh <https://github.com/cdhigh>
import os, json, shutil
from functools import wraps
from operator import itemgetter
from lxml import etree #type:ignore
from bs4 import BeautifulSoup
from flask import Blueprint, render_template, session, request, send_from_directory, current_app as app
from flask_babel import gettext as _
from ..base_handler import *
from ..back_end.db_models import *
from ..back_end.send_mail_adpt import send_to_kindle
from build_ebook import html_to_book

bpReader = Blueprint('bpReader', __name__)

#阅读器路由每个函数校验基本配置代码基本一致，使用此装饰器避免重复代码
#使用此装饰器的函数需要有形参 userDir
def reader_route_preprocess(forAjax=False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            oebDir = app.config['EBOOK_SAVE_DIR']
            if not oebDir:
                msg = _("Online reading feature has not been activated yet.")
                return {'status': msg} if forAjax else msg

            user = kwargs.get('user') #login_required装饰器能保证user一定有效
            userDir = os.path.join(oebDir, user.name).replace('\\', '/') #type:ignore
            kwargs['userDir'] = userDir
            return func(*args, **kwargs)
        return wrapper
    return decorator

#在线阅读器首页
@bpReader.route("/reader", endpoint='ReaderRoute')
def ReaderRoute():
    oebDir = app.config['EBOOK_SAVE_DIR']
    if not oebDir:
        return _("Online reading feature has not been activated yet.")

    userName = request.args.get('username')
    password = request.args.get('password')
    user = get_login_user()
    #为了方便在墨水屏上使用，如果没有登录的话，可以使用查询字符串传递用户名和密码
    if not user and userName and password:
        user = KeUser.get_or_none(KeUser.name == userName)
        if user:
            try:
                if user.passwd_hash == user.hash_text(password):
                    session['login'] = 1
                    session['userName'] = userName
                    session['role'] = 'admin' if userName == app.config['ADMIN_NAME'] else 'user'
                else:
                    user = None
            except Exception as e:
                default_log.warning(f"Failed to hash password and username: {e}")
                user = None

    if not user:
        return redirect(url_for("bpLogin.Login", next=url_for('bpReader.ReaderRoute')))

    userDir = os.path.join(oebDir, user.name).replace('\\', '/')
    oebBooks = GetSavedOebList(userDir)
    oebBooks = json.dumps(oebBooks, ensure_ascii=False)
    initArticle = url_for('bpReader.ReaderArticleNoFoundRoute', tips='')
    return render_template('reader.html', oebBooks=oebBooks, initArticle=initArticle)

#在线阅读器的404页面
@bpReader.route("/reader/404", endpoint='ReaderArticleNoFoundRoute')
@login_required()
@reader_route_preprocess()
def ReaderArticleNoFoundRoute(user: KeUser, userDir: str):
    tips = request.args.get('tips')
    if tips is None:
        tips = _('The article is missing?')
    return render_template('reader_404.html', tips=tips.strip())

#获取文章或图像内容
@bpReader.route("/reader/article/<path:path>", endpoint='ReaderArticleRoute')
@login_required()
@reader_route_preprocess()
def ReaderArticleRoute(path: str, user: KeUser, userDir: str):
    return send_from_directory(userDir, path)

#推送一篇文章或一本书
@bpReader.post("/reader/push", endpoint='ReaderPushPost')
@login_required(forAjax=True)
@reader_route_preprocess(forAjax=True)
def ReaderPushPost(user: KeUser, userDir: str):
    type_ = request.form.get('type')
    src = request.form.get('src', '') #2024-05-30/KindleEar/feed_0/article_1/index.html
    title = request.form.get('title', '')
    print(type_, src, title) #TODO
    if not ((type_ in ('book', 'article')) and ('/' in src) and title):
        return {'status': _("Some parameters are missing or wrong.")}

    msg = 'ok'
    if type_ == 'book':
        book = '/'.join(src.split('/')[:2])
    elif type_ == 'article':
        msg = PushSingleArticle(src, title, user, userDir)
    return {'status': msg}

#删除某些书籍
@bpReader.post("/reader/delete", endpoint='ReaderDeletePost')
@login_required(forAjax=True)
@reader_route_preprocess(forAjax=True)
def ReaderDeletePost(user: KeUser, userDir: str):
    books = ''
    try:
        books = json.loads(request.form.get('books', ''))
    except:
        pass
    if not books or not isinstance(books, list):
        return _("Some parameters are missing or wrong.")

    for book in books:
        bkDir = os.path.join(userDir, book)
        dateDir = os.path.dirname(bkDir)
        if os.path.exists(bkDir):
            try:
                shutil.rmtree(bkDir)
            except Exception as e:
                default_log.warning(f'Failed to delete dir: {bkDir}: {e}')

            #如果目录为空，则将目录也一并删除
            if not os.listdir(dateDir):
                try:
                    shutil.rmtree(dateDir)
                except:
                    pass
    return {'status': 'ok'}

#将一个特定的文章制作成电子书推送
def PushSingleArticle(src: str, title: str, user: KeUser, userDir: str):
    path = os.path.join(userDir, src).replace('\\', '/')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
    except Exception as e:
        return _('Failed to push: {}').format(e)

    imgs = []
    dirName = os.path.dirname(path)
    soup = BeautifulSoup(html, 'lxml')
    #将css嵌入html
    css = []
    for tag in soup.head.find_all('link', attrs={'type': 'text/css', 'href': True}): #type:ignore
        try:
            with open(os.path.join(dirName, tag['href']), 'r', encoding='utf-8') as f:
                data = f.read()
        except:
            continue
        tag.extract()
        css.append(data)

    style = soup.head.find('style') #type:ignore
    if not style:
        style = soup.new_tag('style')
        style.string = '\n'.join(css)
        soup.head.append(style) #type:ignore
    else:
        style.string = '\n'.join(css) + '\n' + (style.string or '') #type:ignore
    
    for tag in soup.find_all('img', src=True): #读取图片，修正图片路径，从images目录里面移出
        src = tag['src']
        try:
            with open(os.path.join(dirName, src), 'rb') as f:
                data = f.read()
        except:
            tag.extract()
            continue

        if data:
            if src.startswith('images/'):
                src = src[7:]
            elif src.startswith('/images/'):
                src = src[8:]
            tag['src'] = src
            imgs.append((src, data))
        else:
            tag.extract()

    book = html_to_book(str(soup), title, user, imgs, language=GetOebLanguage(path, userDir))
    if book:
        send_to_kindle(user, title, book, fileWithTime=False)
        return 'ok'
    else:
        return _('Failed to create ebook.')

#获取一个本地保存电子书的语言种类，实际是找到content.opf，在里面提取
#path: 一本书或一篇文章的绝对地址
def GetOebLanguage(path, userDir):
    opfPath = ''
    while len(path) > len(userDir):
        if os.path.exists(os.path.join(path, 'content.opf')):
            opfPath = os.path.join(path, 'content.opf')
            break
        else:
            path = os.path.dirname(path)

    if opfPath:
        tree = etree.parse(opfPath)
        root = tree.getroot()
        dcLang = root.find('.//{*}language')
        return dcLang.text if dcLang is not None else ''
    else:
        return ''

#获取当前用户保存的所有电子书，返回一个列表[{date:, books: [{title:, articles:[{text:, src:}],},...]}, ]
def GetSavedOebList(userDir: str) -> list:
    if not os.path.exists(userDir):
        return []

    ret = []
    for date in os.listdir(userDir):
        someDay = {'date': date, 'books': []}
        dateDir = os.path.join(userDir, date)
        for title in os.listdir(dateDir):
            prefix = f'{date}/{title}'
            tocFile = os.path.join(dateDir, title, 'toc.ncx')
            articles = ExtractArticleListFromNcx(tocFile, prefix)
            if articles:
                someDay['books'].append({'title': title, 'articles': articles})
        if someDay['books']:
            ret.append(someDay)

    ret.sort(key=itemgetter('date'), reverse=True)
    return ret

#从toc.ncx里面提取文章列表，返回一个字典列表 [{text:,'src':,}]
def ExtractArticleListFromNcx(ncxFile: str, prefix: str) -> list:
    if not os.path.exists(ncxFile):
        return []

    try:
        tree = etree.parse(ncxFile)
    except Exception as e:
        default_log.warning(f"Error parsing Toc file: {ncxFile} : {e}")
        return []

    root = tree.getroot()
    navPoints = root.findall('.//{*}navPoint')
    #只需要最低一层 navPoint
    ret = []
    for nav in [e for e in navPoints if (len(e.findall('.//{*}navPoint')) == 0)]:
        text = nav.find('.//{*}text')
        src = nav.find('.//{*}content')
        if text is not None and src is not None:  #这里必须使用None判断
            text = (text.text or '').strip()
            src = src.attrib.get('src', '')
            if text and src:
                ret.append({'text': text, 'src': f'{prefix}/{src}'})
    return ret
