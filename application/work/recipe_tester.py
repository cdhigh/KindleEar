#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#MCP工具的测试执行器：在服务端有限时地试运行用户编写的calibre recipe和邮件钩子，
#返回每篇文章预处理后的正文与抓取日志，供AI客户端分析并迭代修改。
#Author: cdhigh <https://github.com/cdhigh>
import os, re, time, json, shutil, logging, tempfile, threading, traceback
from bs4 import BeautifulSoup
from calibre.web.feeds.recipes import compile_recipe
from calibre.ebooks.conversion.plumber import OptionValues
from calibre.customize.ui import output_profiles
from calibre.web.feeds import feeds_from_index
from filesystem_dict import FsDictStub
from build_ebook import convert_book

#返回给AI客户端的单篇文章/页面正文上限
MAX_ARTICLE_CHARS = 40 * 1024
MAX_LOG_LINES = 80

#执行一次recipe测试抓取，不生成、不发送电子书
#user: KeUser实例
#src: recipe源码
#max_articles: 每个源最多试抓的文章数；0表示index_only——只解析索引即返回文章列表，不进入下载阶段
#max_feeds: 最多试抓的源(RSS/栏目)数
#timeout_s: 整体墙钟限制，受MCP_TOOL_TIMEOUT钳制
#content_format: 'html' | 'text'
#include_content: 是否返回每篇预处理正文（默认False，只返回content_chars字符预览）
#content_chars: include_content=False时每篇预览的字符数
#download_images: 是否下载图片（默认False；False时keep_images=False会剥除正文img标签，image_count恒为0）
#username/password: needs_subscription的recipe可传入网站账号
#返回 {status: ok|timeout|error, feeds: [...], effective_timeout_seconds: n, ...}
def run_recipe_test(user, src, max_articles=2, max_feeds=1, timeout_s=None,
        content_format='html', username='', password='',
        include_content=False, content_chars=800, download_images=False):
    effectiveTimeout = clamp_timeout(timeout_s)
    recipe = compile_recipe(src)
    if not recipe:
        raise ValueError('Cannot find any subclass of BasicNewsRecipe in the source.')
    max_feeds = max(1, min(int(max_feeds or 1), 5))
    try:
        maxArticlesVal = int(max_articles)
    except (TypeError, ValueError):
        maxArticlesVal = 2
    indexOnly = (maxArticlesVal == 0)
    if not indexOnly:
        maxArticlesVal = max(1, min(maxArticlesVal, 5))
    try:
        contentChars = max(100, min(int(content_chars or 800), 8000))
    except (TypeError, ValueError):
        contentChars = 800

    opts = OptionValues()
    opts.user = user
    opts.verbose = 1
    opts.test = (max_feeds, maxArticlesVal if maxArticlesVal > 0 else 2)
    opts.lrf = False
    opts.keep_images = bool(download_images)
    opts.keep_svg = False
    opts.output_profile = resolve_output_profile(user)
    opts.no_inline_navbars = False

    tempDir = tempfile.mkdtemp(prefix='mcp_recipe_', dir=os.getenv('KE_TEMP_DIR') or None)
    box = {'ro': None, 'error': None}
    logLines = []
    logHandler = _ListHandler(logLines)

    calibreLog = logging.getLogger('calibre')
    oldLevel = calibreLog.level
    calibreLog.addHandler(logHandler)
    calibreLog.setLevel(logging.DEBUG)
    try:
        def runner():
            try:
                fs = FsDictStub(tempDir)
                ro = recipe(opts, calibreLog, tempDir, fs)
                ro.delivery_reason = 'manual' #绕过LastDelivered增量去重
                if username:
                    ro.username = username
                if password:
                    ro.password = password
                box['ro'] = ro
                if indexOnly: #只解析索引：parse_index（自定义）或parse_feeds（RSS），不进入下载阶段
                    try:
                        index = ro.parse_index()
                    except NotImplementedError:
                        index = None
                    if index:
                        box['index_feeds'] = feeds_from_index(index,
                            oldest_article=ro.oldest_article, max_articles_per_feed=500,
                            log=calibreLog)[:max_feeds]
                    else:
                        box['index_feeds'] = ro.parse_feeds()[:max_feeds]
                else:
                    ro.download()
            except Exception:
                box['error'] = traceback.format_exc()
        worker = threading.Thread(target=runner, daemon=True)
        worker.start()
        worker.join(effectiveTimeout)
        if worker.is_alive():
            return {'status': 'timeout', 'effective_timeout_seconds': effectiveTimeout,
                'recipe_title': getattr(recipe, 'title', ''),
                'log_tail': _tail(logLines),
                'notes': ['The recipe exceeded the time limit and is still running in background. '
                    'Reduce max_articles, increase delay handling or check for slow/anti-crawl sites.'],
                }
    finally:
        calibreLog.removeHandler(logHandler)
        calibreLog.setLevel(oldLevel)

    ro = box['ro']
    ret = {'status': 'error', 'recipe_title': getattr(recipe, 'title', ''),
        'effective_timeout_seconds': effectiveTimeout, 'log_tail': _tail(logLines)}
    if ro is None: #编译或实例化阶段失败，无部分结果可收集
        ret['traceback'] = (box['error'] or '')[-4000:]
        return ret
    #即使download()中途抛错（如全部下载失败而中止），feed_objects与失败清单也已赋值，尽量收集部分结果
    ret['status'] = 'error' if box['error'] else 'ok'
    if box['error']:
        ret['traceback'] = box['error'][-4000:]
    ret['recipe_title'] = getattr(ro, 'title', ret['recipe_title'])
    ret['index_only'] = indexOnly
    feeds = []
    #index_only用解析阶段的Feed对象，正常路径用ro.feed_objects（含下载后的相对路径）
    for f_idx, feed in enumerate(box['index_feeds'] if indexOnly else (getattr(ro, 'feed_objects', None) or [])):
        articles = []
        for a_idx, article in enumerate(feed):
            item = {'title': article.title,
                #orig_url仅在下载成功回调里赋值，失败/中止的文章没有该属性，只有原始url
                'url': getattr(article, 'orig_url', '') or article.url,
                'author': article.author or '', 'date': str(article.date or ''),
                'downloaded': bool(article.downloaded)}
            if article.downloaded:
                path = os.path.join(tempDir, 'feed_%d' % f_idx, article.url)
                try:
                    with open(path, 'rb') as f:
                        html = f.read().decode('utf-8', 'replace')
                except OSError:
                    html = ''
                item['size'] = len(html)
                item['image_count'] = len(BeautifulSoup(html, 'lxml').find_all('img'))
                rendered = _clip(_render(html, content_format))
                if include_content:
                    item['content'] = rendered
                else:
                    item['preview'] = rendered[:contentChars]
            articles.append(item)
        feeds.append({'title': feed.title, 'description': feed.description or '',
            'article_count': len(feed), 'articles': articles})
    ret['feeds'] = feeds
    ret['failed_downloads'] = [{'feed': _obj_title(fd[0]), 'article': _obj_title(fd[1]),
            'detail': str(fd[2])[:800]} for fd in (getattr(ro, 'failed_downloads', None) or [])]
    ret['aborted_articles'] = [{'feed': _obj_title(fd[0]), 'article': _obj_title(fd[1])}
        for fd in (getattr(ro, 'aborted_articles', None) or [])]
    if not download_images and not indexOnly and ret['status'] == 'ok':
        ret['notes'] = ['Images are not downloaded during iterations (keep_images=False strips '
            '<img> tags, so image_count is 0). Pass download_images=true for the final '
            'verification run to inspect images.']
    shutil.rmtree(tempDir, ignore_errors=True)
    return ret

#测试一个邮件钩子：按阶段执行并暴露真实的异常栈(生产的run_mail_preprocess_*会吞掉异常)
#src: 钩子源码
#mail_id: InBox邮件id，作为测试样本
#sample: dict {sender,to,subject,txtBodies,htmlBodies}，手工构造的样本，优先于mail_id
#build_book: 是否做一次不发送的电子书干跑
def run_hook_test(user, src, mail_id=None, sample=None, build_book=False):
    from application.mail_hook import compile_mail_hook
    from application.view.inbound_email import CreateMailSoup, CollectSoupLinks

    hookCls = compile_mail_hook(src, 'hook.py') #校验失败直接抛异常
    if sample and isinstance(sample, dict):
        sender = sample.get('sender') or 'sample@example.com'
        to = sample.get('to') or user.cfg('email') or 'to@example.com'
        subject = sample.get('subject') or 'Sample mail'
        txtBodies = list(sample.get('txtBodies') or [])
        htmlBodies = list(sample.get('htmlBodies') or [])
        if not txtBodies and not htmlBodies:
            raise ValueError('The sample must contain txtBodies or htmlBodies.')
    else:
        mail = _load_inbox_mail(user, mail_id)
        sender, to, subject = mail['sender'], mail['to'], mail['subject']
        txtBodies, htmlBodies = mail['txtBodies'], mail['htmlBodies']

    ret = {'status': 'ok', 'hook_file': getattr(hookCls, '__name__', ''),
        'sender': sender, 'to': to, 'subject': subject, 'stages': {}}
    hook = hookCls()
    hook.sender = sender
    hook.to = to

    #阶段1: 原始邮件过滤
    try:
        result = hook.preprocess_email(subject, txtBodies, htmlBodies, [])
        if result is None:
            ret['stages']['preprocess_email'] = {'changed': False}
        elif isinstance(result, (tuple, list)) and len(result) == 4:
            subject, txtBodies, htmlBodies, _attachs = result
            ret['stages']['preprocess_email'] = {'changed': True, 'subject': subject,
                'txt_count': len(txtBodies), 'html_count': len(htmlBodies)}
        else:
            ret['stages']['preprocess_email'] = {'changed': False,
                'warning': 'Return value is neither None nor a 4-element tuple, ignored.'}
    except Exception:
        ret['status'] = 'error'
        ret['stages']['preprocess_email'] = {'error': traceback.format_exc()[-3000:]}
        return ret

    #阶段2: 邮件正文Soup清洗
    soup = CreateMailSoup(subject, txtBodies, htmlBodies)
    if soup is None:
        ret['stages']['create_mail_soup'] = {'error': 'No usable html/text body, CreateMailSoup returned None.'}
        return ret
    ret['stages']['create_mail_soup'] = {'html_length': len(str(soup))}
    urls = []
    try:
        result = hook.preprocess_soup(soup, [])
        attachments = []
        if result is None:
            pass
        elif isinstance(result, (tuple, list)):
            if len(result) == 3:
                soup, attachments, urls = result
            elif len(result) == 2:
                soup, attachments = result
            elif len(result) == 1:
                soup = result[0]
            else:
                raise ValueError('preprocess_soup returned a tuple of invalid length: %d' % len(result))
        else:
            soup = result
        ret['stages']['preprocess_soup'] = {'changed': result is not None, 'html_length': len(str(soup))}
    except Exception:
        ret['status'] = 'error'
        ret['stages']['preprocess_soup'] = {'error': traceback.format_exc()[-3000:]}
        return ret

    #阶段3: 外链提取
    try:
        if not urls:
            hookUrls = hook.extract_urls(soup)
            if isinstance(hookUrls, (list, tuple)):
                urls = [u for u in hookUrls if u]
        if not urls and getattr(hook, 'urls', None):
            urls = list(hook.urls)
        if isinstance(urls, str):
            urls = [urls]
        ret['stages']['extract_urls'] = {'urls': list(urls or [])[:50],
            'default_urls_for_compare': CollectSoupLinks(soup, False)[:50]}
    except Exception:
        ret['stages']['extract_urls'] = {'error': traceback.format_exc()[-3000:], 'urls': list(urls or [])[:50]}

    #阶段4(可选): 不发送的电子书干跑
    if build_book:
        try:
            recipeCls = type('McpHookRunner%d' % int(time.time()), (hookCls,), {
                'title': subject[:50] or 'MCP Hook Test',
                'language': user.book_cfg('language', 'en'),
                'mail_html': str(soup),
                'merge_mail': True,
                'feeds': list(urls or []),
                'oldest_article': user.book_cfg('oldest_article', 7),
                'delivery_reason': 'manual',
                })
            book = convert_book(recipeCls, 'recipe', user,
                options={'dont_save_webshelf': True, 'test': (1, 3), 'verbose': 0})
            ret['stages']['build_book'] = {'ok': bool(book), 'book_size': len(book) if book else 0}
        except Exception:
            ret['stages']['build_book'] = {'ok': False, 'error': traceback.format_exc()[-3000:]}
    return ret

def clamp_timeout(timeout_s):
    #默认90秒（可用MCP_TOOL_TIMEOUT调整默认值），硬上限300秒
    try:
        default = int(os.getenv('MCP_TOOL_TIMEOUT', '90'))
    except ValueError:
        default = 90
    default = max(10, min(default, 300))
    try:
        timeout_s = int(timeout_s)
    except (TypeError, ValueError):
        timeout_s = default
    return max(5, min(timeout_s, 300))

def resolve_output_profile(user):
    sval = user.book_cfg('device') or 'default'
    prof = None
    for x in output_profiles():
        if x.short_name == sval:
            return x
    for x in output_profiles():
        if x.short_name == 'default':
            prof = x
            break
    return prof

#把HTML按指定格式渲染给AI客户端
def _render(html, content_format):
    if content_format == 'text':
        soup = BeautifulSoup(html, 'lxml')
        return soup.get_text('\n', strip=True)
    return html

def _clip(text):
    if text and len(text) > MAX_ARTICLE_CHARS:
        return text[:MAX_ARTICLE_CHARS] + '\n...[TRUNCATED %d chars]...' % (len(text) - MAX_ARTICLE_CHARS)
    return text or ''

def _obj_title(obj):
    try:
        return getattr(obj, 'title', '') or str(obj)
    except Exception:
        return ''

def _tail(lines):
    return lines[-MAX_LOG_LINES:]

class _ListHandler(logging.Handler):
    #CalibreLogger已在_log前把多参数拼接成单条msg，这里按标准格式捕获即可
    def __init__(self, lines):
        super().__init__(level=logging.DEBUG)
        self.lines = lines
    def emit(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        self.lines.append('%s: %s' % (record.levelname.title(), msg))

def _load_inbox_mail(user, mail_id):
    from application.back_end.db_models import InBox
    item = InBox.get_by_id_or_none(mail_id) if str(mail_id or '').isdigit() else None
    if not item or item.user != user.name:
        raise ValueError('InBox mail not found, pass a valid mail_id of your own inbox.')
    try:
        body = json.loads(item.body or '{}')
    except ValueError:
        body = {}
    return {'sender': item.sender, 'to': item.to, 'subject': item.subject,
        'txtBodies': body.get('txtBodies') or [], 'htmlBodies': body.get('htmlBodies') or []}
