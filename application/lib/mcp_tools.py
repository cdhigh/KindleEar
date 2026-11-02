#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#MCP (Model Context Protocol) tools/resources/prompts registry for KindleEar.
#Every handler signature is handler(user: KeUser, args: dict) -> dict, and the
#result is JSON-serialized as the tool call text content by mcp_protocol.py.
#readonly=True tools never modify user data and stay usable in read-only mode.
#Author: cdhigh <https://github.com/cdhigh>
import os, re, json, time, shutil
from collections import defaultdict
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup, NavigableString, Comment
from urlopener import UrlOpener
from recipe_helper import GenerateRecipeSource, GetBuiltinRecipeInfo, GetBuiltinRecipeSource
from application.back_end.db_models import *
from application.ke_utils import new_secret_key, xml_unescape
from mcp_protocol import McpError, ToolWriteForbidden, INVALID_PARAMS

#返回给AI客户端的内容截断上限
MAX_CONTENT_CHARS = 40 * 1024
MAX_MAIL_CHARS = 10 * 1024

#==================== 通用辅助 ====================

def _clip(text, limit=MAX_CONTENT_CHARS):
    if text and len(text) > limit:
        return text[:limit] + '\n...[TRUNCATED %d chars]...' % (len(text) - limit)
    return text or ''

def _to_int(val, default):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default

def _user_shelf_dir(user):
    oebDir = os.getenv('EBOOK_SAVE_DIR') or ''
    if not oebDir:
        raise ValueError('Online reading feature is not activated (EBOOK_SAVE_DIR is not configured).')
    return os.path.join(oebDir, user.name).replace('\\', '/')

def _shelf_file(user, src):
    src = (src or '').replace('\\', '/').strip('/')
    if not src or '..' in src:
        raise ValueError('Invalid article path.')
    path = os.path.join(_user_shelf_dir(user), *src.split('/'))
    if not os.path.isfile(path):
        raise ValueError('Article file not found: %s' % src)
    return path

def _validate_book_dir(book_dir):
    book_dir = (book_dir or '').replace('\\', '/').strip('/')
    parts = book_dir.split('/')
    if len(parts) != 2 or not all(parts) or '..' in book_dir:
        raise ValueError('book_dir must look like "YYYY-MM-DD/NNN_title", got: %s' % book_dir)
    return book_dir

def _norm_mail(mail):
    mail = (mail or '').strip().lower()
    if not mail:
        return ''
    if mail == '*':
        return mail
    if mail.startswith('*@'):
        return mail[1:]
    if '@' not in mail:
        return '@' + mail.lstrip('@')
    return mail

def _html_text_len(html):
    try:
        return len(BeautifulSoup(html, 'lxml').get_text(strip=True))
    except Exception:
        return len(html or '')

def _skeletonize(soup):
    #保留标签结构与关键属性，去掉全部文本节点，方便AI分析DOM而节约token
    for tag in soup.find_all(['style', 'link', 'meta', 'noscript', 'svg', 'path']):
        tag.decompose()
    for elem in soup.find_all(True):
        for child in list(elem.children):
            if isinstance(child, NavigableString):
                child.extract()
        for attr in list(elem.attrs):
            if attr not in ('id', 'class', 'href', 'src', 'name', 'type', 'itemprop', 'data-src'):
                elem.attrs.pop(attr, None)
    return soup

#==================== 系统/账号 ====================

def tool_get_service_status(user, args):
    import sys, platform
    deps = {}
    try:
        from importlib.metadata import version as depVersion
        for name in ('requests', 'beautifulsoup4', 'lxml', 'soupsieve', 'cssselect',
                'feedparser', 'Flask', 'peewee'):
            try:
                deps[name] = depVersion(name)
            except Exception:
                deps[name] = None
    except Exception:
        pass
    try:
        import cssselect
        readabilityOk = True
    except Exception:
        readabilityOk = False
    return {'status': 'ok', 'service': 'KindleEar', 'version': appVer,
        'python': sys.version.split()[0], 'platform': platform.platform(),
        'task_queue_service': os.getenv('TASK_QUEUE_SERVICE', ''),
        'database': (os.getenv('DATABASE_URL', '') or '').split(':')[0],
        'ebook_save_dir_configured': bool(os.getenv('EBOOK_SAVE_DIR')),
        'mcp_readonly_mode': bool(user.custom.get('mcp_readonly')),
        'mcp_tool_count': len(TOOL_REGISTRY),
        'dependencies': deps,
        'readability_ok': readabilityOk,
        'readability_note': 'readability/lxml.cssselect needs the cssselect package; '
            'when missing, extract_article_preview degrades to justext/simpleextract.',
        'server_time': time.strftime('%Y-%m-%d %H:%M:%S')}

def tool_get_account_info(user, args):
    return {'status': 'ok', 'username': user.name,
        'email': user.cfg('email'), 'kindle_email': user.cfg('kindle_email'),
        'delivery_mode': user.cfg('delivery_mode'), 'timezone': user.cfg('timezone'),
        'enable_send': user.cfg('enable_send'),
        'send_days': user.send_days, 'send_time': user.send_time,
        'book_type': user.book_cfg('type'), 'device': user.book_cfg('device'),
        'language': user.book_cfg('language'), 'oldest_article': user.book_cfg('oldest_article'),
        'inbox_count': len(list(InBox.get_all(InBox.user == user.name)))}

#==================== 投递/推送 ====================

def tool_list_delivery_logs(user, args):
    from application.view.logs import GetOrderedDeliverLog
    limit = max(1, min(_to_int(args.get('limit'), 20), 100))
    logs = GetOrderedDeliverLog(user.name, limit)
    shelf = _shelf_lookup(user)
    entries = []
    for l in logs:
        entry = {'time': l.time_str, 'book': l.book, 'to': l.to, 'size': l.size, 'status': l.status}
        hit = shelf.get(l.book or '')
        if hit:
            entry['shelf_book_dir'] = hit['book_dir']
        entries.append(entry)
    return {'status': 'ok', 'logs': entries}

def tool_get_task_status(user, args):
    from application.view.logs import GetOrderedDeliverLog
    book = (args.get('book') or '').lower()
    logs = GetOrderedDeliverLog(user.name, 50)
    if book:
        logs = [l for l in logs if book in (l.book or '').lower()]
    shelf = _shelf_lookup(user)
    entries = []
    for l in logs[:10]:
        entry = {'time': l.time_str, 'book': l.book, 'size': l.size, 'status': l.status,
            'status_note': {'ok': 'Delivery succeeded.', 'nonews': 'No new articles found.',
                'fetch failed': 'Failed to build/fetch the book.'}.get(l.status, '')}
        hit = shelf.get(l.book or '')
        if hit:
            entry['shelf'] = hit
        entries.append(entry)
    return {'status': 'ok', 'logs': entries,
        'shelf_note': _shelf_note(user)}

def tool_push_url_to_kindle(user, args):
    urls = args.get('urls') or []
    if isinstance(urls, str):
        urls = [urls]
    urls = [u.strip() for u in urls if u and u.strip()]
    title = (args.get('title') or '').strip()
    if not urls or not title:
        raise ValueError('Both "urls" (list of web page urls) and "title" are required.')
    from application.back_end.task_queue_adpt import create_url2book_task
    create_url2book_task({'userName': user.name, 'urls': '|'.join(urls), 'title': title,
        'key': user.share_links.get('key', ''), 'action': '', 'text': '',
        'language': args.get('language', ''), 'sender': ''})
    return {'status': 'queued', 'title': title, 'urls': urls,
        'note': 'The task was queued. Completion is visible in delivery logs in a few minutes.'}

def tool_push_text_to_kindle(user, args):
    title = (args.get('title') or '').strip()
    text = args.get('text') or ''
    if not title or not text.strip():
        raise ValueError('Both "title" and "text" are required.')
    from application.work.url2book import u2lCreateEbookFromText
    from application.back_end.send_mail_adpt import send_to_kindle
    book = u2lCreateEbookFromText(user, args.get('url', ''), title, text,
        language=args.get('language', ''))
    if not book:
        raise ValueError('Failed to build the ebook from the text.')
    send_to_kindle(user, title, book, fileWithTime=False)
    return {'status': 'ok', 'title': title, 'book_size': len(book), 'sent_to': user.cfg('kindle_email')}

def tool_deliver_now(user, args):
    from application.view.deliver import queueOneBook, flushQueueToPush
    if 'email' in (user.cfg('delivery_mode') or '') and not user.cfg('kindle_email'):
        raise ValueError('Delivery mode includes email but kindle_email is not configured.')
    idList = args.get('recipe_ids') or []
    toPush = []
    if idList:
        for id_ in idList:
            recipeType, dbId = Recipe.type_and_id(id_)
            bked = user.get_booked_recipe(id_)
            r = Recipe.get_by_id_or_none(dbId) if (not bked and recipeType == 'custom') else None
            if r:
                toPush.append({'id_': r.recipe_id, 'separated': r.custom.get('separated', False), 'title': r.title})
            elif bked:
                toPush.append({'id_': bked.recipe_id, 'separated': bked.separated, 'title': bked.title})
        if not toPush:
            raise ValueError('No matching subscription found for the given recipe_ids.')
    else:
        toPush = [{'id_': r.recipe_id, 'separated': r.separated, 'title': r.title}
            for r in user.get_booked_recipe()]
    if not toPush:
        return {'status': 'ok', 'queued': [], 'note': 'No subscriptions to deliver.'}
    queue = defaultdict(list)
    for item in toPush:
        queueOneBook(queue, user, item['id_'], item['separated'], reason='manual')
    flushQueueToPush(queue, reason='manual')
    return {'status': 'queued', 'queued': [item['title'] for item in toPush],
        'shelf_note': _shelf_note(user)}

#==================== 订阅管理 ====================

def tool_list_subscriptions(user, args):
    subs = [{'recipe_id': bked.recipe_id, 'title': bked.title, 'description': bked.description,
        'separated': bked.separated, 'needs_subscription': bked.needs_subscription,
        'has_account': bool(bked.account), 'send_days': bked.send_days, 'send_times': bked.send_times,
        'translator_enabled': bool(bked.translator), 'tts_enabled': bool(bked.tts),
        'summarizer_enabled': bool(bked.summarizer)} for bked in user.get_booked_recipe()]
    return {'status': 'ok', 'count': len(subs), 'subscriptions': subs}

def tool_search_builtin_recipes(user, args):
    query = (args.get('query') or '').lower()
    language = (args.get('language') or '').lower()
    limit = max(1, min(_to_int(args.get('limit'), 20), 50))
    try:
        tree = ET.parse(os.path.join(appDir, 'application', 'recipes', 'builtin_recipes.xml'))
        root = tree.getroot()
    except Exception as e:
        raise ValueError('Cannot open builtin recipes index: %s' % e)
    hits = []
    for child in root:
        attrs = child.attrib.get
        title, desc = attrs('title', ''), attrs('description', '') or ''
        if language and language not in (attrs('language', '') or '').lower():
            continue
        if query and query not in title.lower() and query not in desc.lower() \
                and query not in (attrs('author', '') or '').lower():
            continue
        hits.append({'id': attrs('id', ''), 'title': title, 'author': attrs('author', ''),
            'language': attrs('language', ''),
            'needs_subscription': attrs('needs_subscription', 'no') in ('yes', 'optional'),
            'description': desc[:200]})
        if len(hits) >= limit:
            break
    return {'status': 'ok', 'count': len(hits), 'recipes': hits}

def tool_add_custom_rss(user, args):
    from application.view.subscribe import AddCustomRss
    title = (args.get('title') or '').strip()
    url = (args.get('url') or '').strip()
    if not title or not url:
        raise ValueError('Both "title" and "url" are required.')
    form = {'title': title, 'url': url, 'fulltext': 'yes' if args.get('fulltext') else '',
        'separated': 'yes' if args.get('separated') else ''}
    return AddCustomRss(user, form)

def tool_remove_subscription(user, args):
    from application.view.subscribe import UnsubscribeRecipe, DeleteRecipe, DeleteCustomRss
    recipe_id = (args.get('recipe_id') or '').strip()
    if not recipe_id:
        raise ValueError('"recipe_id" is required (e.g. "builtin:cnn", "custom:3", "upload:5").')
    recipeType, dbId = Recipe.type_and_id(recipe_id)
    if recipeType == 'custom':
        return DeleteCustomRss(user, recipe_id)
    recipe = GetBuiltinRecipeInfo(recipe_id) if recipeType == 'builtin' else Recipe.get_by_id_or_none(dbId)
    if not recipe:
        raise ValueError('The recipe does not exist: %s' % recipe_id)
    ret = UnsubscribeRecipe(user, recipe_id, recipe)
    if recipeType == 'upload' and args.get('delete_source'):
        DeleteRecipe(user, recipe_id, 'upload', recipe, force=True)
        ret['source_deleted'] = True
    return ret

def tool_update_subscription_schedule(user, args):
    from application.view.subscribe import ScheduleRecipe
    recipe_id = (args.get('recipe_id') or '').strip()
    if not recipe_id:
        raise ValueError('"recipe_id" is required.')
    days = args.get('days') or {}
    times = args.get('times') or []
    if not isinstance(days, dict):
        days = {}
    if not isinstance(times, list):
        times = []
    form = {'type': days.get('type', ''), 'days': ','.join(str(d) for d in days.get('days', [])),
        'times': ','.join(str(t) for t in times)}
    return ScheduleRecipe(user, recipe_id, form)

def tool_import_opml(user, args):
    import opml
    content = args.get('content') or ''
    if not content.strip():
        raise ValueError('"content" (the OPML xml text) is required.')
    try:
        rssList = opml.from_string(content.encode('utf-8'))
    except Exception as e:
        raise ValueError('Failed to parse OPML: %s' % e)
    defaultFullText = bool(args.get('default_fulltext'))
    added, updated = 0, 0

    def walk(outline):
        if not outline:
            return
        for idx in range(len(outline)):
            obj = outline[idx]
            if len(obj) > 0:
                yield from walk(obj)
            yield obj

    for o in walk(rssList):
        title = xml_unescape(getattr(o, 'text', '') or getattr(o, 'title', '') or '')
        url = xml_unescape(getattr(o, 'xmlUrl', '') or '')
        isfulltext = bool(getattr(o, 'isFulltext', '')) or defaultFullText
        if not title or not url:
            continue
        if not url.startswith('http'):
            url = ('https:/' if url.startswith('/') else 'https://') + url
        dbItem = Recipe.get_or_none((Recipe.user == user.name) & (Recipe.title == title))
        if dbItem:
            dbItem.url = url
            dbItem.isfulltext = isfulltext
            dbItem.save()
            updated += 1
        else:
            Recipe.create(title=title, url=url, user=user.name, isfulltext=isfulltext, type_='custom')
            added += 1
    from application.view.subscribe import UpdateBookedCustomRss
    UpdateBookedCustomRss(user)
    return {'status': 'ok', 'added': added, 'updated': updated}

#==================== 在线书架 ====================

def tool_list_shelf(user, args):
    from application.view.reader import GetSavedOebList
    books = GetSavedOebList(_user_shelf_dir(user))
    return {'status': 'ok', 'days': books,
        'note': 'Each book has a book_dir field, used by list_articles/read_article/delete_book.'}

def tool_list_articles(user, args):
    from application.view.reader import ExtractArticleList
    book_dir = _validate_book_dir(args.get('book_dir'))
    userDir = _user_shelf_dir(user)
    tocFile = os.path.join(userDir, *book_dir.split('/'), 'toc.ncx')
    return {'status': 'ok', 'book_dir': book_dir,
        'articles': ExtractArticleList(tocFile, book_dir)}

def tool_read_article(user, args):
    src = (args.get('src') or '').strip()
    if not src:
        raise ValueError('"src" (the article path from list_articles) is required.')
    fmt = (args.get('format') or 'text').lower()
    path = _shelf_file(user, src)
    with open(path, 'rb') as f:
        html = f.read().decode('utf-8', 'replace')
    if fmt == 'html':
        content = html
    else:
        soup = BeautifulSoup(html, 'lxml')
        content = soup.get_text('\n', strip=True)
    return {'status': 'ok', 'src': src, 'format': fmt, 'content': _clip(content)}

def tool_search_articles(user, args):
    from application.view.reader import GetSavedOebList
    query = (args.get('query') or '').strip().lower()
    if not query:
        raise ValueError('"query" is required.')
    limit = max(1, min(_to_int(args.get('limit'), 10), 30))
    hits, scanned = [], 0
    for day in GetSavedOebList(_user_shelf_dir(user)):
        for book in day.get('books', []):
            for article in book.get('articles', []):
                if query in (article.get('title') or '').lower():
                    hits.append({'date': day.get('date'), 'book': book.get('title'),
                        'title': article.get('title'), 'src': article.get('src'), 'matched_in': 'title'})
                elif scanned < 200: #标题未命中时再读文件搜索正文
                    scanned += 1
                    try:
                        with open(_shelf_file(user, article.get('src')), 'rb') as f:
                            text = f.read().decode('utf-8', 'replace').lower()
                        if query in text:
                            hits.append({'date': day.get('date'), 'book': book.get('title'),
                                'title': article.get('title'), 'src': article.get('src'), 'matched_in': 'content'})
                    except (ValueError, OSError):
                        pass
                if len(hits) >= limit:
                    return {'status': 'ok', 'query': query, 'count': len(hits), 'articles': hits}
    return {'status': 'ok', 'query': query, 'count': len(hits), 'articles': hits}

def tool_delete_book(user, args):
    book_dir = _validate_book_dir(args.get('book_dir'))
    bookPath = os.path.join(_user_shelf_dir(user), *book_dir.split('/'))
    if not os.path.isdir(bookPath):
        raise ValueError('Book directory not found: %s' % book_dir)
    shutil.rmtree(bookPath)
    return {'status': 'ok', 'deleted': book_dir}

#==================== AI 增强 ====================

def tool_summarize_article(user, args):
    from ebook_summarizer import HtmlSummarizer
    content = args.get('text') or ''
    if not content.strip():
        src = (args.get('src') or '').strip()
        if not src:
            raise ValueError('Provide either "text" or "src" (an article path from the shelf).')
        with open(_shelf_file(user, src), 'rb') as f:
            content = f.read().decode('utf-8', 'replace')
    #摘要引擎配置：默认借用某个已订阅书籍配置的摘要器
    params = {}
    for bked in user.get_booked_recipe():
        cfg = bked.summarizer or {}
        if cfg.get('api_key'):
            params = dict(cfg)
            break
    for key in ('engine', 'api_key', 'model', 'api_host', 'summary_words', 'summary_lang', 'custom_prompt'):
        if args.get(key):
            params[key] = args[key]
    if not params.get('api_key'):
        raise ValueError('No AI summarizer api_key available. Subscribe a book with AI summary '
            'enabled, or pass engine/api_key arguments (engines: gemini, openai, anthropic, ...).')
    soup = BeautifulSoup('<html><body>%s</body></html>' % content, 'lxml')
    HtmlSummarizer(params).summarize_soup(soup)
    tag = soup.find('p', class_='ai_generated_summary')
    summary = tag.get_text(' ', strip=True) if tag else ''
    summary = summary.replace('AI-Generated Summary:', '', 1).strip()
    if not summary:
        raise ValueError('The summarizer returned no summary (check the api_key and engine settings).')
    return {'status': 'ok', 'summary': summary, 'engine': params.get('engine', 'gemini')}

def tool_lookup_word(user, args):
    from dictionary import CreateDictInst, GetDictDisplayName
    word = (args.get('word') or '').strip()
    if not word:
        raise ValueError('"word" is required.')
    language = (args.get('language') or '').replace('_', '-').split('-')[0].lower()
    engine, database = args.get('engine'), args.get('database')
    if not engine:
        params = {}
        for item in user.cfg('reader_params').get('dicts', []):
            itemLang = item.get('language', 'und')
            if (not params) or (itemLang == language):
                params = item
                if itemLang == language:
                    break
        engine, database = params.get('engine', ''), params.get('database', '')
    if not engine:
        raise ValueError('No dictionary configured. Configure dictionaries in the reader settings first, '
            'or pass engine/database arguments (online engines: dict_org, dict_cn, dict_cc, '
            'merriam_webster, oxford_learners).')
    inst = CreateDictInst(engine, database)
    definition = inst.definition(word, language) or ''
    return {'status': 'ok', 'word': word, 'dict': '%s [%s]' % (engine, GetDictDisplayName(engine, database)),
        'definition': _clip(definition, 20 * 1024)}

#==================== 邮件/白名单 ====================

def tool_list_inbox(user, args):
    limit = max(1, min(_to_int(args.get('limit'), 20), 100))
    items = [i for i in InBox.get_all(InBox.user == user.name) if i.status != 'deleted']
    items.sort(key=lambda i: i.datetime, reverse=True)
    return {'status': 'ok', 'count': len(items), 'mails': [{'id': i.id, 'sender': i.sender,
        'subject': i.subject, 'status': i.status, 'time': str(i.datetime)[:16]} for i in items[:limit]]}

def _inbox_item(user, mail_id):
    item = InBox.get_by_id_or_none(mail_id) if str(mail_id or '').isdigit() else None
    if not item or item.user != user.name:
        raise ValueError('Mail not found, pass a valid "mail_id" from list_inbox.')
    try:
        body = json.loads(item.body or '{}')
    except ValueError:
        body = {}
    return item, body

def tool_read_mail(user, args):
    item, body = _inbox_item(user, args.get('mail_id'))
    attachNames = [a.get('name') for a in (body.get('attachments') or []) if isinstance(a, dict)]
    return {'status': 'ok', 'id': item.id, 'sender': item.sender, 'to': item.to,
        'subject': item.subject, 'time': str(item.datetime)[:16],
        'txtBodies': [_clip(t, MAX_MAIL_CHARS) for t in (body.get('txtBodies') or [])],
        'htmlBodies': [_clip(h, MAX_MAIL_CHARS) for h in (body.get('htmlBodies') or [])],
        'attachment_names': attachNames,
        'note': 'Attachment contents are not stored, only names are available.'}

def tool_manage_whitelist(user, args):
    action = (args.get('action') or 'list').lower()
    if action == 'list':
        return {'status': 'ok', 'whitelist': [{'mail': wl.mail} for wl in user.white_lists()]}
    mail = _norm_mail(args.get('mail'))
    if not mail:
        raise ValueError('"mail" is required (a full address, "@domain", or "*").')
    if action == 'add':
        WhiteList.get_or_create(mail=mail, user=user.name)
        return {'status': 'ok', 'added': mail}
    elif action == 'remove':
        from application.mail_hook import delete_mail_hook
        deleted = WhiteList.delete().where((WhiteList.user == user.name) & (WhiteList.mail == mail)).execute()
        hookDeleted = delete_mail_hook(user, mail)
        return {'status': 'ok', 'removed': mail, 'entries_deleted': deleted, 'hook_deleted': bool(hookDeleted)}
    raise ValueError('action must be one of: list, add, remove')

#==================== Recipe 工作台 ====================

def tool_fetch_page(user, args):
    from application.view.extension import RemoveSoupJs
    url = (args.get('url') or '').strip()
    if not url:
        raise ValueError('"url" is required.')
    fmt = (args.get('format') or 'text').lower()
    if fmt not in ('raw', 'skeleton', 'text'):
        fmt = 'text'
    selector = (args.get('selector') or '').strip()
    selectorFormat = (args.get('selector_format') or 'html').lower()
    try:
        maxChars = max(200, min(int(args.get('max_chars') or MAX_CONTENT_CHARS), MAX_CONTENT_CHARS))
    except (TypeError, ValueError):
        maxChars = MAX_CONTENT_CHARS
    try:
        offset = max(0, int(args.get('offset') or 0))
    except (TypeError, ValueError):
        offset = 0
    UrlOpener.set_proxy(user.cfg('proxy'))
    opener = UrlOpener(timeout=max(10, min(_to_int(args.get('timeout'), 30), 60)),
        user_agent=args.get('user_agent') or None)
    resp = opener.open(url)
    if resp.status_code != 200:
        return {'status': 'error', 'http_status': resp.status_code, 'url': url,
            'error': 'The site returned an error, it may have anti-crawl protection.'}
    html = resp.text
    title = ''
    soup = BeautifulSoup(html, 'lxml')
    if soup.title and soup.title.string:
        title = soup.title.string
    if selector:
        nodes = soup.select(selector)
        if fmt == 'text' or selectorFormat == 'text':
            content = '\n'.join(n.get_text('\n', strip=True) for n in nodes)
        else:
            if fmt == 'skeleton':
                for node in nodes:
                    RemoveSoupJs(node, url)
                    _skeletonize(node)
                content = '\n'.join(str(n) for n in nodes)
            else:
                content = '\n'.join(str(n) for n in nodes)
        matched = len(nodes)
        returnFormat = f'selector/{selectorFormat if fmt != "text" else "text"}'
    else:
        matched = None
        if fmt == 'raw':
            content = html
        elif fmt == 'skeleton':
            RemoveSoupJs(soup, url)
            _skeletonize(soup)
            content = str(soup)
        else:
            content = soup.get_text('\n', strip=True)
        returnFormat = fmt
    totalChars = len(content)
    page = content[offset:offset + maxChars]
    nextOffset = offset + len(page) if offset + len(page) < totalChars else None
    return {'status': 'ok', 'url': url, 'format': returnFormat, 'page_title': title,
        'encoding': resp.encoding or resp.apparent_encoding or 'utf-8',
        'matched': matched, 'total_chars': totalChars,
        'offset': offset, 'next_offset': nextOffset,
        'content': page}

def tool_extract_article_preview(user, args):
    from justext_extract import justext_extract
    from simpleextract import simple_extract
    url = (args.get('url') or '').strip()
    if not url:
        raise ValueError('"url" is required.')
    language = args.get('language', '')
    UrlOpener.set_proxy(user.cfg('proxy'))
    resp = UrlOpener(timeout=30).open(url)
    if resp.status_code != 200:
        return {'status': 'error', 'http_status': resp.status_code, 'url': url}
    html = resp.text
    engines = {}
    title = ''
    #readability依赖cssselect(lxml.cssselect)，缺失或解析失败时降级，justext/simpleextract照常
    rHtml = ''
    try:
        import readability
        doc = readability.Document(html, url=url)
        title = doc.short_title() or doc.title()
        rHtml = doc.summary(html_partial=False)
        engines['readability'] = {'text_length': _html_text_len(rHtml), 'preview': rHtml[:400]}
    except Exception as e:
        engines['readability'] = {'error': str(e)}
    try:
        jHtml = justext_extract(html, language, url)
        engines['justext'] = {'text_length': _html_text_len(jHtml), 'preview': jHtml[:400]}
    except Exception as e:
        jHtml = ''
        engines['justext'] = {'error': str(e)}
    try:
        sRet = simple_extract(html)
        sHtml = str(sRet) if hasattr(sRet, 'find_all') else (sRet or '')
        engines['simpleextract'] = {'text_length': _html_text_len(sHtml), 'preview': sHtml[:400]}
    except Exception as e:
        sHtml = ''
        engines['simpleextract'] = {'error': str(e)}

    readabilityOk = 'error' not in engines['readability']
    selected = 'readability' if (readabilityOk and _html_text_len(rHtml) >= 200) else 'justext'
    return {'status': 'ok', 'url': url, 'title': title, 'engines': engines,
        'selected': selected,
        'content': _clip(rHtml if selected == 'readability' else jHtml),
        'note': 'If readability/justext both fail, the recipe needs custom keep_only_tags '
            '(set auto_cleanup=False) instead of relying on auto_cleanup=True.'}

#把书架按标题建立索引（日期倒序，先命中者优先），供交付结果与书架互相印证
def _shelf_lookup(user):
    try:
        from application.view.reader import GetSavedOebList
        books = GetSavedOebList(_user_shelf_dir(user))
    except Exception:
        return {}
    index = {}
    for day in books:
        for book in day.get('books', []):
            index.setdefault(book.get('title') or '', {
                'book_dir': book.get('book_dir'),
                'article_count': len(book.get('articles') or [])})
    return index

#说明一次投递完成后该书是否会出现在在线书架（plumber仅当delivery_mode含local时才保存书架）
def _shelf_note(user):
    if not os.getenv('EBOOK_SAVE_DIR'):
        return ('EBOOK_SAVE_DIR is not configured on this server, books are never saved to the '
            'online shelf (email delivery only), so list_shelf cannot verify it.')
    if 'local' not in (user.cfg('delivery_mode') or ''):
        return ("The delivery mode does not include 'local', the book will NOT appear on the "
            'online shelf. Set the delivery mode to include online reading (settings page) '
            'to verify it afterwards with list_shelf / read_article.')
    return ('After the delivery completes, the book will appear on the online shelf and can '
        'be verified with list_shelf and read_article.')

def tool_validate_recipe(user, args):
    from calibre.web.feeds.recipes import compile_recipe
    src = args.get('src') or ''
    if not src.strip():
        raise ValueError('"src" (the complete recipe python source) is required.')
    try:
        recipe = compile_recipe(src)
    except Exception as e:
        return {'status': 'error', 'error': 'Compile failed: %s' % e}
    if not recipe:
        return {'status': 'error', 'error': 'Cannot find any subclass of BasicNewsRecipe in the source.'}
    return {'status': 'ok', 'class': recipe.__name__, 'title': recipe.title,
        'description': recipe.description, 'language': recipe.language,
        'needs_subscription': recipe.needs_subscription}

def tool_test_recipe(user, args):
    from application.work.recipe_tester import run_recipe_test
    src = args.get('src') or ''
    if not src.strip():
        raise ValueError('"src" (the complete recipe python source) is required.')
    return run_recipe_test(user, src, max_articles=args.get('max_articles', 2),
        max_feeds=args.get('max_feeds', 1), timeout_s=args.get('timeout'),
        content_format=args.get('format', 'html'),
        username=args.get('username', ''), password=args.get('password', ''),
        include_content=bool(args.get('include_content')),
        content_chars=args.get('content_chars', 800),
        download_images=bool(args.get('download_images')))

def tool_save_recipe(user, args):
    from calibre.web.feeds.recipes import compile_recipe
    from application.view.subscribe import SaveRecipeIfCorrect, SubscribeRecipe, DeleteRecipe
    src = args.get('src') or ''
    if not src.strip():
        raise ValueError('"src" (the complete recipe python source) is required.')
    recipe = compile_recipe(src)
    if not recipe:
        raise ValueError('Cannot find any subclass of BasicNewsRecipe in the source.')
    overwritten = False
    if args.get('overwrite'):
        old = Recipe.get_or_none((Recipe.user == user.name) & (Recipe.title == recipe.title))
        if old:
            DeleteRecipe(user, old.recipe_id, old.type_, old, force=True)
            overwritten = True
    params = SaveRecipeIfCorrect(user, src)
    if args.get('subscribe'):
        dbRow = Recipe.get_by_id_or_none(params.get('dbId'))
        if dbRow:
            SubscribeRecipe(user, params['id'], dbRow, bool(args.get('separated')))
    params.pop('dbId', None)
    params['status'] = 'ok'
    params['overwritten'] = overwritten
    return params

def tool_get_recipe_source(user, args):
    recipe_id = (args.get('recipe_id') or '').strip()
    if not recipe_id:
        raise ValueError('"recipe_id" is required ("builtin:xxx", "custom:x" or "upload:x").')
    recipeType, dbId = Recipe.type_and_id(recipe_id)
    if recipeType == 'builtin':
        src = GetBuiltinRecipeSource(recipe_id)
        info = GetBuiltinRecipeInfo(recipe_id)
        if not src:
            raise ValueError('Builtin recipe not found: %s' % recipe_id)
        return {'status': 'ok', 'recipe_id': recipe_id, 'title': info.title if info else '', 'source': src}
    recipe = Recipe.get_by_id_or_none(dbId)
    if not recipe:
        raise ValueError('The recipe does not exist: %s' % recipe_id)
    if recipeType == 'upload':
        return {'status': 'ok', 'recipe_id': recipe_id, 'title': recipe.title, 'source': recipe.src}
    #custom RSS: 生成投递时将会使用的recipe源码预览
    src = GenerateRecipeSource(recipe.title, [recipe.url], user, isfulltext=recipe.isfulltext,
        language=recipe.language)
    return {'status': 'ok', 'recipe_id': recipe_id, 'title': recipe.title,
        'source': src, 'note': 'Generated preview for a custom RSS subscription.'}

def tool_test_delivery(user, args):
    from application.back_end.task_queue_adpt import create_delivery_task
    idList = args.get('recipe_ids') or []
    if isinstance(idList, str):
        idList = [idList]
    idList = [i.strip() for i in idList if i.strip()]
    if not idList:
        raise ValueError('"recipe_ids" is required (one or more subscription ids).')
    create_delivery_task({'userName': user.name, 'recipeId': ','.join(i.replace(':', '__') for i in idList),
        'reason': 'manual', 'key': os.environ.get('DELIVERY_KEY', '')})
    return {'status': 'queued', 'recipe_ids': idList,
        'shelf_note': _shelf_note(user),
        'note': 'A real delivery was queued; check completion with get_task_status / '
            'list_delivery_logs, then verify the book with list_shelf / read_article when '
            'the shelf is enabled.'}

#==================== Mail Hook 工作台 ====================

def tool_get_sample_email(user, args):
    mail_id = args.get('mail_id')
    if mail_id:
        item, body = _inbox_item(user, mail_id)
    else:
        items = [i for i in InBox.get_all(InBox.user == user.name) if i.status != 'deleted']
        items.sort(key=lambda i: i.datetime, reverse=True)
        if not items:
            raise ValueError('The inbox is empty. Send a newsletter mail to your KindleEar inbox first.')
        item = items[0]
        try:
            body = json.loads(item.body or '{}')
        except ValueError:
            body = {}
    return {'status': 'ok', 'id': item.id, 'sender': item.sender, 'to': item.to,
        'subject': item.subject, 'time': str(item.datetime)[:16],
        'txtBodies': [_clip(t, MAX_MAIL_CHARS) for t in (body.get('txtBodies') or [])],
        'htmlBodies': [_clip(h, MAX_MAIL_CHARS) for h in (body.get('htmlBodies') or [])],
        'attachment_names': [a.get('name') for a in (body.get('attachments') or []) if isinstance(a, dict)],
        'note': 'Attachments are stored by name only, the hook receives an empty attachment list in tests.'}

def tool_validate_mail_hook(user, args):
    from application.mail_hook import compile_mail_hook
    src = args.get('src') or ''
    if not src.strip():
        raise ValueError('"src" (the complete hook python source) is required.')
    try:
        cls = compile_mail_hook(src, 'hook.py')
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
    return {'status': 'ok', 'class': cls.__name__,
        'note': 'The hook must define a MailNewsRecipe subclass with optional '
            'preprocess_email/preprocess_soup/extract_urls methods.'}

def tool_test_mail_hook(user, args):
    from application.work.recipe_tester import run_hook_test
    src = args.get('src') or ''
    if not src.strip():
        raise ValueError('"src" (the complete hook python source) is required.')
    return run_hook_test(user, src, mail_id=args.get('mail_id'),
        sample=args.get('sample'), build_book=bool(args.get('build_book')))

def tool_save_mail_hook(user, args):
    from application.mail_hook import save_mail_hook, compile_mail_hook, MAX_HOOK_FILE_SIZE
    mail = (args.get('mail') or '').strip().lower()
    src = args.get('src') or ''
    filename = (args.get('filename') or 'hook.py').strip() or 'hook.py'
    if not mail or not src.strip():
        raise ValueError('Both "mail" (an existing whitelist entry) and "src" are required.')
    if not any(wl.mail == mail for wl in user.white_lists()):
        raise ValueError('"%s" is not in the whitelist, add it first with manage_whitelist.' % mail)
    if len(src.encode('utf-8')) > MAX_HOOK_FILE_SIZE:
        raise ValueError('The hook file is too large (max %d bytes).' % MAX_HOOK_FILE_SIZE)
    compile_mail_hook(src, os.path.basename(filename)) #校验失败会抛异常
    save_mail_hook(user, mail, src, os.path.basename(filename))
    return {'status': 'ok', 'mail': mail, 'filename': os.path.basename(filename)}

#==================== Schema 简写 ====================

def _s(desc, **kw):
    return dict({'type': 'string', 'description': desc}, **kw)
def _i(desc, **kw):
    return dict({'type': 'integer', 'description': desc}, **kw)
def _b(desc):
    return {'type': 'boolean', 'description': desc}
def _a(desc):
    return {'type': 'array', 'items': {'type': 'string'}, 'description': desc}
def _obj(properties, required=None):
    schema = {'type': 'object', 'properties': properties}
    if required:
        schema['required'] = required
    return schema

#==================== 工具注册表 ====================

def get_tool_registry():
    return TOOL_REGISTRY

def get_tool_by_name(name):
    for tool in TOOL_REGISTRY:
        if tool['name'] == name:
            return tool
    return None

def get_resources():
    return MCP_RESOURCES

TOOL_REGISTRY = [
{'name': 'get_service_status', 'title': 'Service status', 'readonly': True,
 'description': 'Get KindleEar service status: version, task queue backend, database type, server time.',
 'inputSchema': _obj({}),
 'handler': tool_get_service_status},
{'name': 'get_account_info', 'title': 'Account info', 'readonly': True,
 'description': 'Get the account settings summary: kindle email, delivery mode, schedule, book format.',
 'inputSchema': _obj({}),
 'handler': tool_get_account_info},
{'name': 'list_delivery_logs', 'title': 'Delivery logs', 'readonly': True,
 'description': 'List recent delivery history entries (book title, recipient, size, status).',
 'inputSchema': _obj({'limit': _i('Max entries to return, default 20')}), 'handler': tool_list_delivery_logs},
{'name': 'get_task_status', 'title': 'Task status', 'readonly': True,
 'description': 'Check the status of recent push tasks, optionally filtered by book title.',
 'inputSchema': _obj({'book': _s('Filter by book title (substring)')}), 'handler': tool_get_task_status},
{'name': 'push_url_to_kindle', 'title': 'Push URLs to Kindle', 'readonly': False,
 'description': 'Convert web page(s) to an ebook and send it to the Kindle. Returns immediately, '
    'the task runs in background; check completion with list_delivery_logs later.',
 'inputSchema': _obj({'urls': _a('One or more web page URLs'),
    'title': _s('Book title'), 'language': _s('Book language code, e.g. en/zh')}, ['urls', 'title']),
 'handler': tool_push_url_to_kindle},
{'name': 'push_text_to_kindle', 'title': 'Push text to Kindle', 'readonly': False,
 'description': 'Convert plain text or HTML content into an ebook and send it to the Kindle. Runs synchronously.',
 'inputSchema': _obj({'title': _s('Book title'), 'text': _s('Text or HTML content'),
    'url': _s('Optional origin URL added to the book'), 'language': _s('Language code')}, ['title', 'text']),
 'handler': tool_push_text_to_kindle},
{'name': 'deliver_now', 'title': 'Deliver now', 'readonly': False,
 'description': 'Queue a manual delivery of all subscriptions, or only the given recipe_ids '
    '(e.g. ["builtin:cnn", "upload:3"]).',
 'inputSchema': _obj({'recipe_ids': _a('Subscription ids to deliver; empty means all')}),
 'handler': tool_deliver_now},
{'name': 'list_subscriptions', 'title': 'List subscriptions', 'readonly': True,
 'description': 'List all subscribed recipes with schedule and AI features status.',
 'inputSchema': _obj({}), 'handler': tool_list_subscriptions},
{'name': 'search_builtin_recipes', 'title': 'Search builtin recipes', 'readonly': True,
 'description': 'Search the ~1700 builtin calibre recipes by keyword and/or language.',
 'inputSchema': _obj({'query': _s('Keyword in title/description/author'), 'language': _s('Language filter, e.g. zh, en'),
    'limit': _i('Max results, default 20')}), 'handler': tool_search_builtin_recipes},
{'name': 'add_custom_rss', 'title': 'Add custom RSS', 'readonly': False,
 'description': 'Add a custom RSS subscription. fulltext=True means the RSS feed contains full article content.',
 'inputSchema': _obj({'title': _s('Subscription title'), 'url': _s('RSS feed URL'),
    'fulltext': _b('RSS has full content'), 'separated': _b('Deliver as a standalone book')}, ['title', 'url']),
 'handler': tool_add_custom_rss},
{'name': 'remove_subscription', 'title': 'Remove subscription', 'readonly': False,
 'description': 'Unsubscribe a recipe. For upload recipes, delete_source=True also removes the stored source.',
 'inputSchema': _obj({'recipe_id': _s('Subscription id'), 'delete_source': _b('Also delete the uploaded source')},
    ['recipe_id']),
 'handler': tool_remove_subscription},
{'name': 'update_subscription_schedule', 'title': 'Update schedule', 'readonly': False,
 'description': 'Set a per-book delivery schedule. days: {"type": "weekday"|"date", "days": [1..7 or 1..31]}, '
    'times: list of hours [7, 20]. Empty days resets to the user schedule.',
 'inputSchema': _obj({'recipe_id': _s('Subscription id'),
    'days': {'type': 'object', 'properties': {'type': _s('weekday or date'), 'days': _a('Day numbers')}},
    'times': _a('Hours of the day')}, ['recipe_id']),
 'handler': tool_update_subscription_schedule},
{'name': 'import_opml', 'title': 'Import OPML', 'readonly': False,
 'description': 'Import an OPML subscription list (pass the xml text as content).',
 'inputSchema': _obj({'content': _s('OPML xml text'), 'default_fulltext': _b('Default fulltext flag')}, ['content']),
 'handler': tool_import_opml},
{'name': 'list_shelf', 'title': 'List shelf', 'readonly': True,
 'description': 'List the online reading shelf: delivered books grouped by date, with article lists.',
 'inputSchema': _obj({}), 'handler': tool_list_shelf},
{'name': 'list_articles', 'title': 'List articles', 'readonly': True,
 'description': 'List the articles of one book on the shelf.',
 'inputSchema': _obj({'book_dir': _s('The book_dir value from list_shelf')}, ['book_dir']),
 'handler': tool_list_articles},
{'name': 'read_article', 'title': 'Read article', 'readonly': True,
 'description': 'Read one article from the shelf, as plain text or html.',
 'inputSchema': _obj({'src': _s('The src value from list_articles'), 'format': _s('text or html, default text')},
    ['src']),
 'handler': tool_read_article},
{'name': 'search_articles', 'title': 'Search articles', 'readonly': True,
 'description': 'Search all shelf articles by keyword (title first, then content).',
 'inputSchema': _obj({'query': _s('Keyword'), 'limit': _i('Max results, default 10')}, ['query']),
 'handler': tool_search_articles},
{'name': 'delete_book', 'title': 'Delete book', 'readonly': False,
 'description': 'Delete one book from the online shelf.',
 'inputSchema': _obj({'book_dir': _s('The book_dir value from list_shelf')}, ['book_dir']),
 'handler': tool_delete_book},
{'name': 'summarize_article', 'title': 'Summarize article', 'readonly': True,
 'description': 'Summarize a shelf article or given text with the configured AI summarizer. '
    'Uses the account summarizer config, or engine/api_key arguments.',
 'inputSchema': _obj({'src': _s('Article src from the shelf'), 'text': _s('Or raw text to summarize'),
    'engine': _s('AI engine: gemini/openai/anthropic/xai/mistral/groq/perplexity/alibaba/...'),
    'api_key': _s('API key if not configured on any subscription'), 'model': _s('Model name'),
    'summary_words': _i('Summary length in words, default 100'), 'summary_lang': _s('Summary language'),
    'custom_prompt': _s('Custom prompt, supports {lang} and {words}')}),
 'handler': tool_summarize_article},
{'name': 'lookup_word', 'title': 'Lookup word', 'readonly': True,
 'description': 'Look up a word with the configured dictionary engines.',
 'inputSchema': _obj({'word': _s('Word to look up'), 'language': _s('Language code, e.g. en'),
    'engine': _s('Dictionary engine (dict_org/dict_cn/dict_cc/merriam_webster/oxford_learners)'),
    'database': _s('Optional local database name')}, ['word']),
 'handler': tool_lookup_word},
{'name': 'list_inbox', 'title': 'List inbox', 'readonly': True,
 'description': 'List the inbound email inbox (saved newsletter mails).',
 'inputSchema': _obj({'limit': _i('Max entries, default 20')}), 'handler': tool_list_inbox},
{'name': 'read_mail', 'title': 'Read mail', 'readonly': True,
 'description': 'Read one inbound email (text/html bodies and attachment names).',
 'inputSchema': _obj({'mail_id': _s('The mail id from list_inbox')}, ['mail_id']),
 'handler': tool_read_mail},
{'name': 'manage_whitelist', 'title': 'Manage whitelist', 'readonly': False,
 'description': 'List/add/remove inbound mail whitelist entries. mail can be a full address, '
    '"@domain" or "*". Removing an entry also deletes its hook.',
 'inputSchema': _obj({'action': _s('list, add or remove'), 'mail': _s('The mail entry')}),
 'handler': tool_manage_whitelist},
{'name': 'fetch_page', 'title': 'Fetch web page', 'readonly': True,
 'description': 'Fetch a web page for structure analysis. format "skeleton" returns only the DOM tag '
    'tree (id/class/href attributes, no text), "raw" the original HTML, "text" the visible text. '
    'Optional selector (BeautifulSoup CSS selector, e.g. "div.mc-article-body") returns only the '
    'matching subtrees - use it to pull a container out of a 1MB+ page. offset/max_chars paginate '
    'long content: read further slices with next_offset. Use the account proxy if configured.',
 'inputSchema': _obj({'url': _s('The page URL'), 'format': _s('raw, skeleton or text, default text'),
    'selector': _s('Optional CSS selector, return only matching subtrees'),
    'selector_format': _s('html or text for selector matches, default html'),
    'offset': _i('Start reading the content at this char position'),
    'max_chars': _i('Max chars returned per call, default 40000'),
    'user_agent': _s('Override the User-Agent header'), 'timeout': _i('Timeout seconds, default 30')},
    ['url']),
 'handler': tool_fetch_page},
{'name': 'extract_article_preview', 'title': 'Preview article extraction', 'readonly': True,
 'description': 'Run the built-in content extraction chain (readability -> justext -> simpleextract) on a URL '
    'and compare the results, to decide whether a recipe can rely on auto_cleanup=True '
    'or needs custom keep_only_tags.',
 'inputSchema': _obj({'url': _s('The article URL'), 'language': _s('Language code, helps justext')}, ['url']),
 'handler': tool_extract_article_preview},
{'name': 'validate_recipe', 'title': 'Validate recipe', 'readonly': True,
 'description': 'Compile-check a calibre recipe source without running it. Returns the error '
    'or the recipe metadata (title, language, needs_subscription).',
 'inputSchema': _obj({'src': _s('The complete recipe python source')}, ['src']),
 'handler': tool_validate_recipe},
{'name': 'test_recipe', 'title': 'Test recipe', 'readonly': True,
 'description': 'Execute a recipe source in test mode: fetches at most max_feeds x max_articles '
    'articles, and returns the article list, the preprocessed content of each downloaded article '
    '(html or text) and the full fetch log. Analyze the returned content for completeness, leftover '
    'navigation/ads, and check the log for 403/captcha/redirect anti-crawl signals. Iterate on the '
    'recipe source and call again until satisfied. Workflow tips: max_articles=0 runs index-only '
    '(seconds, no article downloads) to verify parse_index/link filtering; by default each article '
    'returns a content_chars-char preview only, pass include_content=true for the full preprocessed '
    'html of 1-2 articles; images are not downloaded during iterations (keep_images=False strips '
    '<img> tags so image_count is 0), pass download_images=true on the final verification run; '
    'a print_version() hook returning None skips that article (do not use None to mean "use the '
    'original url"). Typical counter-measures: custom User-Agent, cookies via get_browser(), '
    'delay attribute, use_embedded_content=True for full-text RSS, auto_cleanup + keep_only_tags.',
 'inputSchema': _obj({'src': _s('The complete recipe python source'),
    'max_articles': _i('Articles per feed to fetch, 0 for index-only, default 2, max 5'),
    'max_feeds': _i('Feeds to fetch, default 1, max 5'),
    'format': _s('Content format: html or text, default html'),
    'include_content': _b('Return full preprocessed content per article (default false: preview only)'),
    'content_chars': _i('Preview length in chars when include_content=false, default 800'),
    'download_images': _b('Download images (final verification run only), default false'),
    'timeout': _i('Overall time limit in seconds, default 90, max 300'),
    'username': _s('Site account if the recipe needs_subscription'),
    'password': _s('Site password')}, ['src']),
 'handler': tool_test_recipe},
{'name': 'save_recipe', 'title': 'Save recipe', 'readonly': False,
 'description': 'Validate and save a recipe source as an upload recipe, optionally subscribing to it. '
    'overwrite=True replaces an existing recipe with the same title.',
 'inputSchema': _obj({'src': _s('The complete recipe python source'), 'overwrite': _b('Replace same-title recipe'),
    'subscribe': _b('Subscribe after saving'), 'separated': _b('Deliver as a standalone book')}, ['src']),
 'handler': tool_save_recipe},
{'name': 'get_recipe_source', 'title': 'Get recipe source', 'readonly': True,
 'description': 'Read the source of an existing recipe (builtin, custom RSS preview or uploaded).',
 'inputSchema': _obj({'recipe_id': _s('Recipe id: "builtin:xxx", "custom:x" or "upload:x"')}, ['recipe_id']),
 'handler': tool_get_recipe_source},
{'name': 'test_delivery', 'title': 'Test delivery', 'readonly': False,
 'description': 'Queue a real delivery of the given recipe_ids (merged into one book) to validate '
    'the final result end to end.',
 'inputSchema': _obj({'recipe_ids': _a('Subscription ids')}, ['recipe_ids']),
 'handler': tool_test_delivery},
{'name': 'get_sample_email', 'title': 'Get sample email', 'readonly': True,
 'description': 'Get a saved inbound email (latest one, or by mail_id) as a test sample for mail hooks.',
 'inputSchema': _obj({'mail_id': _s('Optional mail id, default the latest mail')}),
 'handler': tool_get_sample_email},
{'name': 'validate_mail_hook', 'title': 'Validate mail hook', 'readonly': True,
 'description': 'Compile-check a mail hook source (AST safety, syntax and MailNewsRecipe subclass check).',
 'inputSchema': _obj({'src': _s('The complete hook python source')}, ['src']),
 'handler': tool_validate_mail_hook},
{'name': 'test_mail_hook', 'title': 'Test mail hook', 'readonly': True,
 'description': 'Run a mail hook against a saved inbound email (mail_id) or a hand-made sample '
    '{sender,to,subject,txtBodies,htmlBodies}: executes preprocess_email, preprocess_soup and '
    'extract_urls stage by stage with real tracebacks, and compares extracted URLs with the '
    'default extraction. build_book=True additionally dry-runs an ebook build (nothing is sent).',
 'inputSchema': _obj({'src': _s('The complete hook python source'), 'mail_id': _s('Inbox mail id to use as sample'),
    'sample': {'type': 'object', 'description': 'Or a hand-made sample mail'},
    'build_book': _b('Also dry-run the ebook build')}, ['src']),
 'handler': tool_test_mail_hook},
{'name': 'save_mail_hook', 'title': 'Save mail hook', 'readonly': False,
 'description': 'Validate and attach a mail hook to a whitelist entry (the mail must already be whitelisted).',
 'inputSchema': _obj({'mail': _s('The whitelist entry address'), 'src': _s('The complete hook python source'),
    'filename': _s('Optional file name, default hook.py')}, ['mail', 'src']),
 'handler': tool_save_mail_hook},
]

#==================== 资源与提示词 ====================

MCP_RESOURCES = [
{'uri': 'kindlear://subscriptions', 'name': 'Subscriptions', 'mimeType': 'application/json',
 'description': 'All subscribed recipes with schedule and AI feature flags.'},
{'uri': 'kindlear://shelf', 'name': 'Reading shelf', 'mimeType': 'application/json',
 'description': 'All books on the online reading shelf.'},
{'uri': 'kindlear://logs/recent', 'name': 'Recent delivery logs', 'mimeType': 'application/json',
 'description': 'The latest 30 delivery log entries.'},
{'uri': 'kindlear://account', 'name': 'Account summary', 'mimeType': 'application/json',
 'description': 'Account settings summary (email, schedule, formats).'},
]

_RESOURCE_MAP = {
    'kindlear://subscriptions': (tool_list_subscriptions, {}),
    'kindlear://shelf': (tool_list_shelf, {}),
    'kindlear://logs/recent': (tool_list_delivery_logs, {'limit': 30}),
    'kindlear://account': (tool_get_account_info, {}),
}

def read_resource(user, uri):
    entry = _RESOURCE_MAP.get(uri)
    if entry is None:
        raise McpError(INVALID_PARAMS, 'Unknown resource: %s' % uri)
    handler, args = entry
    data = handler(user, args)
    return [{'uri': uri, 'mimeType': 'application/json',
        'text': json.dumps(data, ensure_ascii=False, indent=1, default=str)}]

MCP_PROMPTS = [
{'name': 'create_news_recipe', 'description': 'Guided workflow to author and debug a calibre recipe '
    'for a news site: analyze the site, write the recipe, test-fetch sample articles, fix extraction '
    'and anti-crawl issues iteratively, then save and validate with a real delivery.',
 'arguments': [{'name': 'url', 'description': 'The news site or RSS feed URL', 'required': True},
    {'name': 'language', 'description': 'Site language code, e.g. en, zh', 'required': False}]},
{'name': 'recipe_workflow', 'description': 'The recommended efficient loop for AI recipe authoring: '
    'cheap reconnaissance (selector), extraction decision (3 engines), index-only verification, '
    'small-sample iteration with previews, then save/subscribe, end-to-end delivery and shelf '
    'read-back verification.',
 'arguments': [{'name': 'url', 'description': 'The news site or RSS feed URL', 'required': True}]},
{'name': 'create_mail_hook', 'description': 'Guided workflow to author and test an inbound mail hook '
    '(MailNewsRecipe subclass) for one of the whitelisted senders.',
 'arguments': [{'name': 'sender', 'description': 'The newsletter sender address or @domain', 'required': False}]},
{'name': 'morning_digest', 'description': 'Build a morning digest: read the latest shelf articles '
    'and produce a structured summary.',
 'arguments': []},
{'name': 'subscription_review', 'description': 'Review all subscriptions: usage, schedule conflicts, '
    'failed deliveries, and cleanup suggestions.',
 'arguments': []},
]

def get_prompts():
    return MCP_PROMPTS

def get_prompt(user, name, args):
    url = (args or {}).get('url', '')
    language = (args or {}).get('language', '')
    sender = (args or {}).get('sender', '')
    if name == 'create_news_recipe':
        text = _RECIPE_WORKFLOW.format(url=url or '<the news site URL>', language=language or 'undetermined')
    elif name == 'recipe_workflow':
        text = _RECIPE_WORKFLOW.format(url=url or '<the news site URL>', language='undetermined')
    elif name == 'create_mail_hook':
        text = _HOOK_WORKFLOW.format(sender=sender or '<the whitelisted sender>')
    elif name == 'morning_digest':
        text = ('Read my online shelf with list_shelf, pick the books delivered in the last 24 hours, '
            'read their newest articles with read_article, and produce a structured morning digest: '
            'group by topic, two or three sentences per article with its title and source book, '
            'and end with a list of links worth reading in full.')
    elif name == 'subscription_review':
        text = ('Call list_subscriptions and list_delivery_logs (limit 50). Review: which subscriptions '
            'produce mostly failed/nonews deliveries, which have overlapping schedules, which were '
            'never delivered recently. Propose concrete cleanups (unsubscribe, reschedule via '
            'update_subscription_schedule) and ask me to confirm before applying them.')
    else:
        raise McpError(-32602, 'Unknown prompt: %s' % name)
    return {'description': MCP_PROMPTS[[p['name'] for p in MCP_PROMPTS].index(name)]['description'],
        'messages': [{'role': 'user', 'content': {'type': 'text', 'text': text}}]}

_RECIPE_WORKFLOW = '''Create a production-ready calibre recipe for the news site {url} (language: {language}).

Follow this efficient loop - each stage is designed to be cheap, only the final run downloads everything:

0. REUSE: call search_builtin_recipes first - if a builtin recipe already exists for this site,
read it with get_recipe_source and improve it instead of starting from scratch.

1. RECONNAISSANCE (cheap): call fetch_page on the site with format="skeleton" to see the DOM tag
tree. For a 1MB+ page use a selector (e.g. fetch_page(url, format="text", selector="div.article-body"))
to pull out the article container, and offset/max_chars to page through long content. If the site
offers an RSS/ATOM feed, prefer the feed URL: feed-based recipes are far more reliable than
index-page scraping.

2. EXTRACTION DECISION: call extract_article_preview on one article URL - it runs the three built-in
extraction engines (readability/justext/simpleextract) side by side. If readability or justext
already returns the clean article, the recipe can rely on auto_cleanup=True; only write custom
keep_only_tags/remove_tags when all engines fail.

3. DRAFT: write a complete recipe subclass of BasicNewsRecipe (import from
"calibre.web.feeds.news"). Key attributes: title, description, language, max_articles_per_feed,
oldest_article, feeds, use_embedded_content (True for full-text RSS), auto_cleanup,
keep_only_tags / remove_tags / preprocess_html(soup). IMPORTANT: a print_version() hook that
returns None SKIPS that article - never return None to mean "use the original url".
Validate with validate_recipe.

4. INDEX-ONLY CHECK (seconds, no downloads): call test_recipe with max_articles=0 - it only runs
the index parsing and returns the full article list, so you can verify link selection/dedup/
oldest_article filtering without paying for article downloads. Iterate here while tuning
parse_index or feed filtering.

5. CONTENT ITERATION: call test_recipe with max_articles=2. By default each article returns a
short preview plus size and image_count - enough to judge completeness and junk. Analyze like an
editor: is the main content complete? leftover navigation/ads/cookie banners? Does the fetch log
show 403/429, captcha, redirects, garbled encoding? Pass include_content=true only when you need
the full html of 1-2 articles. Anti-crawl counter-measures: realistic browser User-Agent, cookies
via get_browser(), delay = 1..3, encoding attribute, recursions=1 only for multi-page articles.

6. FINISH: when the samples are clean, call save_recipe with subscribe=true (separated=true if the
site should be its own book), then test_delivery and confirm with get_task_status. The
test_delivery result tells you whether the book will appear on the online shelf (delivery mode
must include "local"); when it does, verify the final ebook with list_shelf and read_article -
including a last run with download_images=true if image fidelity matters.'''

_HOOK_WORKFLOW = '''Create a production-ready inbound mail hook for the whitelisted sender {sender}.

1. Call get_sample_email to fetch a saved mail from this sender as the test sample (or list_inbox
first and pick one). Study the htmlBodies structure.

2. Write a complete MailNewsRecipe subclass (import from "calibre.web.feeds.news"). Available hooks:
- preprocess_email(subject, txtBodies, htmlBodies, attachments): return None or a 4-tuple
(subject, txtBodies, htmlBodies, attachments) to filter/rewrite the raw mail.
- preprocess_soup(soup, attachments): return the cleaned soup (optionally as (soup, attachments)
or (soup, attachments, urls)).
- extract_urls(soup): return a list of article URLs found in the newsletter body.
- plus any BasicNewsRecipe attributes/methods (keep_only_tags, get_browser, preprocess_html...)
applied to the fetched external articles.
Sandbox rules: no imports of os/sys/subprocess/open/exec/eval - the AST safety check rejects them;
bs4 and re are available.

3. Validate with validate_mail_hook, then test with test_mail_hook (pass mail_id). Check each stage
output: is the subject rewritten as intended? is the body clean? are the extracted URLs correct and
complete compared to default_urls_for_compare?

4. When clean, call save_mail_hook with the exact whitelist address, then optionally test_delivery
after sending a new mail from that sender. Report the final hook summary to the user.'''
