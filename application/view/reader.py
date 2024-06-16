#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#KindleEar在线RSS阅读器，为电子墨水屏进行了专门优化
#Author: cdhigh <https://github.com/cdhigh>
import os, json, shutil, time
from functools import wraps
from operator import itemgetter
from lxml import etree #type:ignore
from bs4 import BeautifulSoup
from flask import Blueprint, render_template, session, request, send_from_directory, current_app as app
from flask_babel import gettext as _
from build_ebook import html_to_book
from ..base_handler import *
from ..utils import xml_escape, xml_unescape, str_to_int, str_to_float, str_to_bool
from ..back_end.db_models import *
from ..back_end.send_mail_adpt import send_to_kindle
from .settings import get_locale, LangMap

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
    userName = request.args.get('username')
    password = request.args.get('password')
    key = request.args.get('key')
    user = get_login_user()
    #为了方便在墨水屏上使用，如果没有登录的话，可以使用查询字符串传递用户名和密码
    if not user and userName:
        user = KeUser.get_or_none(KeUser.name == userName)
        if user:
            isValidKey = key and (key == user.share_links.get('key'))
            try:
                isValidPassword = password and (user.passwd_hash == user.hash_text(password))
                if isValidKey or isValidPassword:
                    session['login'] = 1
                    session['userName'] = userName
                    session['role'] = 'admin' if userName == app.config['ADMIN_NAME'] else 'user'
                else:
                    user = None
            except Exception as e:
                default_log.warning(f"Failed to hash password and username: {e}")
                user = None

    if not user:
        if userName and (password or key):
            time.sleep(5) #防止暴力破解
        return redirect(url_for("bpLogin.Login", next=url_for('bpReader.ReaderRoute')))

    oebDir = app.config['EBOOK_SAVE_DIR']
    if oebDir:
        userDir = os.path.join(oebDir, user.name).replace('\\', '/')
        oebBooks = GetSavedOebList(userDir)
        comicTitle = 'Nothing here'
    else:
        oebBooks = []
        comicTitle = 'Not activated'
        
    oebBooks = json.dumps(oebBooks, ensure_ascii=False)
    initArticle = url_for('bpReader.ReaderArticleNoFoundRoute', tips='')
    params = user.cfg('reader_params')
    shareKey = user.share_links.get('key')
    if (get_locale() or '').startswith('zh'):
        helpPage = 'https://cdhigh.github.io/KindleEar/Chinese/reader.html'
    else:
        helpPage = 'https://cdhigh.github.io/KindleEar/English/reader.html'
    return render_template('reader.html', oebBooks=oebBooks, initArticle=initArticle, params=params,
        shareKey=shareKey, comicTitle=comicTitle, helpPage=helpPage)

#在线阅读器的404页面
@bpReader.route("/reader/404", endpoint='ReaderArticleNoFoundRoute')
@login_required()
def ReaderArticleNoFoundRoute(user):
    tips = request.args.get('tips')
    oebDir = app.config['EBOOK_SAVE_DIR']
    if not oebDir:
        tips = _("Online reading feature has not been activated yet.")
    elif tips is None:
        tips = _('The article is missing?')
    params = user.cfg('reader_params')
    return render_template('reader_404.html', tips=tips.strip(), params=params)

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
    language = request.form.get('language', '')
    if not ((type_ in ('book', 'article')) and ('/' in src) and title):
        return {'status': _("Some parameters are missing or wrong.")}

    title = xml_unescape(title)
    msg = 'ok'
    if type_ == 'book':
        book = '/'.join(src.split('/')[:2])
    elif type_ == 'article':
        msg = PushSingleArticle(src, title, user, userDir, language)
    return {'status': msg}

#删除某些书籍
@bpReader.post("/reader/delete", endpoint='ReaderDeletePost')
@login_required(forAjax=True)
@reader_route_preprocess(forAjax=True)
def ReaderDeletePost(user: KeUser, userDir: str):
    books = request.form.get('books', '')
    if not books:
        return _("Some parameters are missing or wrong.")

    for book in books.split('|'):
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

#设置阅读器的默认参数
@bpReader.post("/reader/settings", endpoint='ReaderSettingsPost')
@login_required(forAjax=True)
@reader_route_preprocess(forAjax=True)
def ReaderSettingsPost(user: KeUser, userDir: str):
    form = request.form
    fontSize = str_to_float(form.get('fontSize', '1.0'), 1.0)
    allowLinks = 1 if str_to_bool(form.get('allowLinks', 'true')) else 0
    topleftDict = 1 if str_to_bool(form.get('topleftDict', 'true')) else 0
    inkMode = str_to_int(form.get('inkMode', '1'), 1)
    params = user.cfg('reader_params')
    params.update({'fontSize': fontSize, 'allowLinks': allowLinks, 'inkMode': inkMode, 'topleftDict': topleftDict})
    user.set_cfg('reader_params', params)
    user.save()
    return {'status': 'ok'}

#网页查词
@bpReader.route("/reader/dict", endpoint='ReaderDictRoute')
@login_required()
@reader_route_preprocess()
def ReaderDictRoute(user: KeUser, userDir: str):
    from dictionary import all_dict_engines

    #刷新词典列表，方便在不重启服务的情况下添加删除离线词典文件
    for dic in all_dict_engines.values():
        if hasattr(dic, 'refresh'):
            dic.refresh()
    
    engines = {name: {'databases': klass.databases} for name,klass in all_dict_engines.items()}
    return render_template('dict.html', user=user, engines=engines, tips='', langMap=LangMap())

#Api查词
@bpReader.post("/reader/dict", endpoint='ReaderDictPost')
@login_required(forAjax=True)
@reader_route_preprocess(forAjax=True)
def ReaderDictPost(user: KeUser, userDir: str):
    from dictionary import CreateDictInst, GetDictDisplayName
    form = request.form
    word = form.get('word', '').strip()
    language = form.get('language', '').replace('_', '-').split('-')[0].lower() #书本语种
    if not word:
        return {'status': _("The text is empty.")}

    #为一个字典列表[{language:,engine:,database:,}]
    dictParams = user.cfg('reader_params').get('dicts', [])

    #优先使用网页传递过来的引擎和数据库参数
    engine = form.get('engine')
    database = form.get('database')
    if not engine or not database:
        defDict = {}
        params = {}
        for item in dictParams:
            itemLang = item.get('language', 'und')
            if not itemLang or (itemLang == 'und'):
                defDict = item
            elif not params and (itemLang == language):
                params = item
        if not params:
            params = defDict
        engine = params.get('engine', '')
        database = params.get('database', '')
    
    inst = CreateDictInst(engine, database)
    #将其他可选的词典信息也传递给网页
    others = []
    added = set()
    for e in dictParams:
        itemEngine = e.get('engine')
        itemDb = e.get('database')
        indi = f'{itemEngine}.{itemDb}'
        if (indi not in added) and ((itemEngine != inst.name) or (itemDb != inst.database)):
            added.add(indi)
            dbName = GetDictDisplayName(itemEngine, itemDb)
            others.append({'language': e.get('language', ''), 'engine': itemEngine, 'database': itemDb,
                'dbName': f'{itemEngine} [{dbName}]'})

    try:
        definition = inst.definition(word, language)
        if not definition and language: #如果查询不到，尝试使用构词法词典获取词根
            stem = GetWordStem(word, language)
            if stem:
                word = stem
                definition = inst.definition(word, language) #再次查询
    except Exception as e:
        #import traceback
        #traceback.print_exc()
        definition = f'Error:<br/>{e}'
    #print(json.dumps(definition)) #TODO
    return {'status': 'ok', 'word': word, 'definition': definition, 
        'dictname': str(inst), 'others': others}

#根据构词法获取词干
#language: 语种代码，只有前两个字母
def GetWordStem(word, language):
    try:
        import dictionary
        import hunspell #type:ignore
    except Exception as e:
        #import traceback #TODO
        #default_log.warning(traceback.format_exc())
        return ''

    dictDir = app.config['DICTIONARY_DIR'] or ''
    morphDir = os.path.join(dictDir, 'morphology') if dictDir else ''
    dics = []
    if morphDir and os.path.exists(morphDir):
        dics.extend([os.path.splitext(e)[0] for e in os.listdir(morphDir) if e.endswith('.dic') and e.startswith(language)])

    if dics:
        dic = dics[0]
    elif language.startswith('en'): #使用默认英语变形数据 en_US
        dic = 'en_US'
        morphDir = None
    else:
        return ''

    stems = []
    try:
        hObj = hunspell.Hunspell(lang=dic, hunspell_data_dir=morphDir)
        stems = [s for s in hObj.stem(word) if s != word]
        default_log.debug(f'got stem tuple: {stems}')
    except Exception as e:
        default_log.warning(f'Get stem of "{word}" failed: {e}')

    stem = stems[0] if stems else ''
    if isinstance(stem, bytes):
        stem = stem.decode('utf-8')
    return stem
    
#将一个特定的文章制作成电子书推送
def PushSingleArticle(src: str, title: str, user: KeUser, userDir: str, language: str):
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

    book = html_to_book(str(soup), title, user, imgs, language=language, options={'dont_save_webshelf': True})
    if book:
        send_to_kindle(user, title, book, fileWithTime=False)
        return 'ok'
    else:
        return _('Failed to create ebook.')

#获取当前用户保存的所有电子书，返回一个列表[{date:, books: [{title:, articles:[{title:, src:}],},...]}, ]
def GetSavedOebList(userDir: str) -> list:
    if not os.path.exists(userDir):
        return []

    ret = []
    for date in sorted(os.listdir(userDir), reverse=True):
        someDay = {'date': date, 'books': []}
        dateDir = os.path.join(userDir, date)
        for book in sorted(os.listdir(dateDir), reverse=True):
            bookDir = os.path.join(dateDir, book)
            opfFile = os.path.join(bookDir, 'content.opf')
            tocFile = os.path.join(bookDir, 'toc.ncx')
            prefix = f'{date}/{book}'
            meta = ExtractBookMeta(opfFile)
            articles = ExtractArticleList(tocFile, prefix)
            if meta and articles:
                someDay['books'].append({'title': meta['title'], 'language': meta['language'], 
                    'bookDir': prefix, 'articles': articles})
        if someDay['books']:
            ret.append(someDay)

    ret.sort(key=itemgetter('date'), reverse=True)
    return ret

#从content.opf里面提取文章元信息，返回一个字典 {title:,language:,}
def ExtractBookMeta(opfFile: str) -> dict:
    if not os.path.exists(opfFile):
        return {}

    try:
        tree = etree.parse(opfFile)
    except Exception as e:
        default_log.warning(f"Error parsing Toc file: {opfFile} : {e}")
        return {}

    root = tree.getroot()
    ret = {}
    title = root.find('.//{*}title')
    if title is not None: #需要使用not None
        ret['title'] = xml_escape(title.text)
    lang = root.find('.//{*}language')
    if lang is not None:
        ret['language'] = xml_escape(lang.text)
    
    return ret

#从toc.ncx里面提取文章列表，返回一个字典列表 [{title:,'src':,}]
def ExtractArticleList(ncxFile: str, prefix: str) -> list:
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
                ret.append({'title': text, 'src': f'{prefix}/{src}'})
    return ret
