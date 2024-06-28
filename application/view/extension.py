#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#浏览器扩展程序的支持代码
#Author: cdhigh<https://github.com/cdhigh>
import json, re
from urllib.parse import unquote, urljoin
from html import escape
from bs4 import BeautifulSoup
from flask import Blueprint, request, make_response, current_app as app
from flask_babel import gettext as _
from calibre.web.feeds.news import get_tags_from_rules
from ..base_handler import *
from ..utils import xml_escape
from ..back_end.db_models import *
from urlopener import UrlOpener

bpExtension = Blueprint('bpExtension', __name__)

HTML_TPL = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        <title>failed</title></head><body><p>{}</p><br/><p style="text-align:right;color:silver;">by KindleEar &nbsp;</p></body></html>"""


#接受扩展程序的请求，下载一个页面，并且将js全部去掉，然后再返回
@bpExtension.route("/ext/removejs")
def ExtRemoveJsRoute():
    args = request.args
    userName = args.get('name', app.config['ADMIN_NAME'])
    key = args.get('key')
    url = args.get('url')
    user = KeUser.get_or_none(KeUser.name == userName)
    if not user or user.share_links.get('key') != key:
        return HTML_TPL.format(_("The username '{}' does not exist.").format(escape(userName)))
    elif not url:
        return HTML_TPL.format(_("Some parameters are missing or wrong."))

    opener = UrlOpener()
    resp = opener.open(unquote(url))
    if resp.status_code == 200:
        #encoding: 查看响应头Content-Type，apparent_encoding: 使用chardet根据内容猜测
        encoding = resp.encoding or resp.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(resp.text, 'lxml')
        RemoveSoupJs(soup, url)
        resp = make_response(str(soup).encode(encoding, 'replace'))
        resp.headers['Content-Type'] = f'text/html; charset={encoding}'
        resp.headers['Access-Control-Allow-Origin'] = '*' #允许跨域访问CSS/FONT之类的
        return resp
    else:
        return HTML_TPL.format(GetRespErrorInfo(resp, escape(url)))


#接受扩展程序的请求，下载一个页面，将js全部去掉，根据特定的规则提取正文内容，然后返回
@bpExtension.route("/ext/extractor")
def ExtRenderWithRules():
    args = request.args
    userName = args.get('name', app.config['ADMIN_NAME'])
    key = args.get('key')
    url = args.get('url')
    ruleStr = args.get('rules', '')
    user = KeUser.get_or_none(KeUser.name == userName)
    if not user or user.share_links.get('key') != key:
        return HTML_TPL.format(_("The username '{}' does not exist.").format(escape(userName)))
    elif not url or not ruleStr:
        return HTML_TPL.format(_("Some parameters are missing or wrong."))

    ruleStr = unquote(ruleStr)
    try:
        rulesList = json.loads(unquote(ruleStr))
    except Exception as e:
        return HTML_TPL.format(_("The rules parameter is invalid.") + '<br/>' + str(e))

    opener = UrlOpener()
    resp = opener.open(unquote(url))
    if resp.status_code != 200:
        return HTML_TPL.format(GetRespErrorInfo(resp, escape(url)))

    encoding = resp.encoding or resp.apparent_encoding or 'utf-8'
    rawHtml = resp.text
    soup = BeautifulSoup(rawHtml, 'lxml')
    RemoveSoupJs(soup, url)
    oldBody = soup.find('body')
    if not oldBody:
        return rawHtml

    newBody = soup.new_tag('body')
    for item in rulesList:
        rules = [BuildCssSelector(elem) for elem in item]
        newBody.extend(get_tags_from_rules(soup, rules))
    oldBody.replace_with(newBody)
    resp = make_response(str(soup).encode(encoding, 'replace'))
    resp.headers['Content-Type'] = f'text/html; charset={encoding}'
    resp.headers['Access-Control-Allow-Origin'] = '*' #允许跨域访问CSS/FONT之类的
    return resp

#删除soup里面的javascript代码
def RemoveSoupJs(soup, url):
    for tag in list(soup.find_all('script')):
        tag.extract()
    for attr in ['onload', 'onclick', 'onchange', 'onmouseover', 'onmouseout', 'onkeydown',
        'onkeyup', 'onkeypress', 'onsubmit', 'onfocus', 'onblur', 'oninput', 'ondblclick',
        'oncontextmenu', 'onmousedown', 'onmouseup', 'onscroll', 'onloadstart', 'onloadend',
        'onerror']:
        for o in soup.find_all(attrs={attr: True}):
            del o[attr]

    #将相对路径转换为绝对路径
    for tag in soup.find_all(['a', 'link'], href=True):
        href = tag['href']
        if href.startswith('javascript'):
            href = '#'
        elif not href.startswith('http'):
            href = urljoin(url, href)
        tag['href'] = href

    #纠正或规则化soup里面的图片地址，比如相对地址/延迟加载等
    for tag in soup.find_all('img'):
        attrs = tag.attrs
        #大部分使用延迟加载的网站都使用data-src|data-original
        altUrl = attrs.get('data-src', '') or attrs.get('data-original', '')
        imgUrl = attrs.pop('src', '') or altUrl
        if not imgUrl or imgUrl.endswith('/none.gif'):
            #分两步是优先使用有src字样的，第二步是更大胆一点猜测
            candi = [attrs[attr] for attr in attrs if ('src' in attr)]
            candi.extend([attrs[attr] for attr in attrs if attr.startswith('data') or ('file' in attr)])
            imgUrl = candi[0] if candi else imgUrl

        if imgUrl and not imgUrl.startswith(('data:', 'http', 'www', 'file:')):
            tag['src'] = urljoin(url, imgUrl)
        else:
            tag['src'] = imgUrl
        
    return soup

#根据浏览器扩展程序定义的rule规则字典结构，构建CSS查询字符串
def BuildCssSelector(rule: dict):
    txt = [rule.get('name', '').lower()]
    id_ = rule.get('id')
    for item in (rule.get('class') or []):
        txt.append('.' + item)
    if id_:
        txt.append('#' + id_)
    for item in (rule.get('attrs') or []):
        txt.append('[' + item + ']')

    return ''.join(txt)

#根据浏览器扩展程序定义的一个rule规则列表，构建空格分隔的CSS选择器字符串
def BuildMultiCssSelector(rules: list):
    return ' '.join([BuildCssSelector(item) for item in rules])

#根据页面HTML源码获取页面编码
def GetPageSrcEncoding(soup, default=''):
    meta1 = soup.find('meta', attrs={'http-equiv': 'Content-Type'})
    meta2 = soup.find('meta', attrs={'charset': True})
    code = default
    if meta1: #<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        content = meta1.get('content', '')
        match = re.search(r'charset=([^\s;]+)', content)
        code = match.group(1) if match else code
    elif meta2:
        code = meta2.get('charset')

    return code or default

#设置页面HTML源码的编码
def SetPageSrcEncoding(soup, encoding):
    meta1 = soup.find('meta', attrs={'http-equiv': 'Content-Type'})
    meta2 = soup.find('meta', attrs={'charset': True})
    if meta1: #<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        meta1['content'] = f'text/html; charset={encoding}'
    elif meta2:
        meta2['charset'] = encoding
    else:
        attrs = {'http-equiv': 'Content-Type', 'content': f'text/html; charset={encoding}'}
        meta1 = soup.new_tag('meta', attrs=attrs)
        try:
            soup.find('head').insert(0, meta1)
        except Exception as e:
            default_log.warning(f'Set page encoding {encoding} failed: {e}')


#requests返回非200响应时获取错误码和响应头
def GetRespErrorInfo(resp, url):
    info = [f'Get url failed: {url}', f'Status code: {UrlOpener.CodeMap(resp.status_code)}',]
    text = resp.text
    if text:
        info.append(f'Response body:')
        if '<html' in text:
            info.append(f'<pre style="white-space:pre-wrap;font-size:0.8em;">{xml_escape(text)}</pre>')
        else:
            info.append(text)
    info.append('')
    info.append('--------------------------------')
    info.append('<strong>Response Headers:</strong>')
    info.append('--------------------------------')
    info.extend([f'<p style="display:inline;white-space:nowrap"><strong>{k}:</strong> <small>{v}</small></p>' 
        for k,v in resp.headers.items()])
    return '<br/>'.join(info)
