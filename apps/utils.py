#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Author:
# cdhigh <https://github.com/cdhigh>
#Contributors:
# rexdf <https://github.com/rexdf>
import os, sys
from functools import wraps
from hashlib import md5
import web
from config import *
import datetime
import gettext
import re

#当异常出现时，使用此函数返回真实引发异常的文件名，函数名和行号
def get_exc_location():
    #追踪到最终的异常引发点
    exc_info = sys.exc_info()[2]
    last_exc = exc_info.tb_next
    while (last_exc.tb_next):
        last_exc = last_exc.tb_next
    fileName = os.path.basename(last_exc.tb_frame.f_code.co_filename)
    funcName = last_exc.tb_frame.f_code.co_name
    lineNo = last_exc.tb_frame.f_lineno
    last_exc = None
    exc_info = None
    return fileName, funcName, lineNo

#字符串转整数，出错则返回0
def str_to_int(txt):
    try:
        return int(txt.strip())
    except:
        return 0

def local_time(fmt="%Y-%m-%d %H:%M", tz=TIMEZONE):
    return (datetime.datetime.utcnow()+datetime.timedelta(hours=tz)).strftime(fmt)

def hide_email(email):
    """ 隐藏真实email地址，使用星号代替部分字符 """
    if not email or '@' not in email:
        return email
    email = email.split('@')
    if len(email[0]) < 4:
        return email[0][0] + '**@' + email[-1]
    to = email[0][0:2] + ''.join(['*' for s in email[0][2:-1]]) + email[0][-1]
    return to + '@' + email[-1]
    
def set_lang(lang):
    """ 设置网页显示语言 """
    tr = gettext.translation('lang', 'i18n', languages=[lang])
    tr.install(True)
    main.jjenv.install_gettext_translations(tr)

def fix_filesizeformat(value, binary=False):
    " bugfix for do_filesizeformat of jinja2 "
    bytes = float(value)
    base = binary and 1024 or 1000
    prefixes = [
        (binary and 'KiB' or 'kB'),(binary and 'MiB' or 'MB'),
        (binary and 'GiB' or 'GB'),(binary and 'TiB' or 'TB'),
        (binary and 'PiB' or 'PB'),(binary and 'EiB' or 'EB'),
        (binary and 'ZiB' or 'ZB'),(binary and 'YiB' or 'YB'),]
    if bytes < base:
        return '1 Byte' if bytes == 1 else '%d Bytes' % bytes
    else:
        for i, prefix in enumerate(prefixes):
            unit = base ** (i + 2)
            if bytes < unit:
                return '%.1f %s' % ((base * bytes / unit), prefix)
        return '%.1f %s' % ((base * bytes / unit), prefix)

        
#将etag应用于具体页面的装饰器
#此装饰器不能减轻服务器压力，但是可以减小客户端的再次加载页面时间
def etagged():
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwds):
            rsp_data = func(*args, **kwds)
            if type(rsp_data) is unicode:
                etag = '"%s"' % md5(rsp_data.encode('utf-8', 'ignore')).hexdigest()
            else:
                etag = '"%s"' % md5(rsp_data).hexdigest()
            #格式参见：<http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.26>
            n = set([x.strip().lstrip('W/') for x in web.ctx.env.get('HTTP_IF_NONE_MATCH', '').split(',')])
            if etag in n:
                raise web.notmodified()
            else:
                web.header('ETag', etag)
                web.header('Cache-Control', 'no-cache')
                return rsp_data
        return wrapper
    return decorator
    
#创建OEB的两级目录，主要代码由rexdf贡献
#sections为有序字典，关键词为段名，元素为元组列表(title,brief,humbnail,content)
#toc_thumbnails为字典，关键词为图片原始URL，元素为其在oeb内的href。
def InsertToc(oeb, sections, toc_thumbnails, insertHtmlToc=True, insertThumbnail=True):
    css_pat = r'<style type="text/css">(.*?)</style>'
    css_ex = re.compile(css_pat, re.M | re.S)
    body_pat = r'(?<=<body>).*?(?=</body>)'
    body_ex = re.compile(body_pat, re.M | re.S)
    
    num_articles = 1
    num_sections = 0
    
    ncx_toc = []
    #html_toc_2 secondary toc
    html_toc_2 = []
    name_section_list = []
    for sec in sections.keys():
        css = ['.pagebreak{page-break-before:always;}h1{font-size:2.0em;}h2{font-size:1.5em;}h3{font-size:1.4em;}h4{font-size:1.2em;}h5{font-size:1.1em;}h6{font-size:1.0em;}']
        html_content = []
        secondary_toc_list = []
        first_flag = False
        sec_toc_thumbnail = None
        for title, brief, thumbnail, content in sections[sec]:
            #获取自定义的CSS
            for css_obj in css_ex.finditer(content):
                if css_obj and css_obj.group(1) and css_obj.group(1) not in css:
                    css.append(css_obj.group(1))
                
            if first_flag:
                html_content.append('<div id="%d" class="pagebreak">' % (num_articles)) #insert anchor && pagebreak
            else:
                html_content.append('<div id="%d">' % (num_articles)) #insert anchor && pagebreak
                first_flag = True
                if thumbnail:
                    sec_toc_thumbnail = thumbnail #url
            
            #将body抽取出来
            body_obj = re.search(body_ex, content)
            if body_obj:
                html_content.append(body_obj.group()+'</div>') #insect article
                secondary_toc_list.append((title, num_articles, brief, thumbnail))
                num_articles += 1
            else:
                html_content.pop()
        html_content.append('</body></html>')
        
        html_content.insert(0, '<html><head><title>%s</title><style type="text/css">%s</style></head><body>' % (sec, ''.join(css)))
        
        #add section.html to maninfest and spine
        #We'd better not use id as variable. It's a python builtin function.
        id_, href = oeb.manifest.generate(id='feed', href='feed%d.html' % num_sections)
        item = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=''.join(html_content))
        oeb.spine.add(item, True)
        
        #在目录分类中添加每个目录下的文章篇数
        sec_with_num = '%s (%d)' % (sec, len(sections[sec]))
        ncx_toc.append(('section', sec_with_num, href, '', sec_toc_thumbnail)) #Sections name && href && no brief
        
        #generate the secondary toc
        if insertHtmlToc:
            html_toc_ = ['<html><head><title>toc</title></head><body><h2>%s</h2><ol>' % (sec_with_num)]
        for title, anchor, brief, thumbnail in secondary_toc_list:
            if insertHtmlToc:
                html_toc_.append('&nbsp;&nbsp;&nbsp;&nbsp;<li><a href="%s#%d">%s</a></li><br />'%(href, anchor, title))
            ncx_toc.append(('article',title, '%s#%d'%(href,anchor), brief, thumbnail)) # article name & article href && article brief
        if insertHtmlToc:
            html_toc_.append('</ol></body></html>')
            html_toc_2.append(html_toc_)
            name_section_list.append(sec_with_num)

        num_sections += 1

    if insertHtmlToc:
        #Generate HTML TOC for Calibre mostly
        ##html_toc_1 top level toc
        html_toc_1 = [u'<html><head><title>Table Of Contents</title></head><body><h2>%s</h2><ul>'%(TABLE_OF_CONTENTS)]
        html_toc_1_ = []
        #We need index but not reversed()
        for a in xrange(len(html_toc_2)-1,-1,-1):
            #Generate Secondary HTML TOC
            id_, href = oeb.manifest.generate(id='section', href='toc_%d.html' % (a))
            item = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=" ".join(html_toc_2[a]))
            oeb.spine.insert(0, item, True)
            html_toc_1_.append('&nbsp;&nbsp;&nbsp;&nbsp;<li><a href="%s">%s</a></li><br />'%(href,name_section_list[a]))
        html_toc_2 = []
        for a in reversed(html_toc_1_):
            html_toc_1.append(a)
        html_toc_1_ = []
        html_toc_1.append('</ul></body></html>')
        #Generate Top HTML TOC
        id_, href = oeb.manifest.generate(id='toc', href='toc.html')
        item = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=''.join(html_toc_1))
        oeb.guide.add('toc', 'Table of Contents', href)
        oeb.spine.insert(0, item, True)

    #Generate NCX TOC for Kindle
    po = 1 
    toc = oeb.toc.add(unicode(oeb.metadata.title[0]), oeb.spine[0].href, id='periodical', klass='periodical', play_order=po)
    po += 1
    for ncx in ncx_toc:
        if insertThumbnail and ncx[4]:
            toc_thumbnail = toc_thumbnails[ncx[4]]
        else:
            toc_thumbnail = None
            
        if ncx[0] == 'section':
            sectoc = toc.add(unicode(ncx[1]), ncx[2], klass='section', play_order=po, id='Main-section-%d'%po, 
                toc_thumbnail=toc_thumbnail)
        elif sectoc:
            sectoc.add(unicode(ncx[1]), ncx[2], description=ncx[3] if ncx[3] else None, klass='article', play_order=po, 
                id='article-%d'%po, toc_thumbnail=toc_thumbnail)
        po += 1
                    
#-----------以下几个函数为安全相关的
def new_secret_key(length=8):
    import random
    allchars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXZY0123456789'
    return ''.join([random.choice(allchars) for i in range(length)])
    
def ke_encrypt(s, key):
    return auth_code(s, key, 'ENCODE')
    
def ke_decrypt(s, key):
    return auth_code(s, key, 'DECODE')

def auth_code(string, key, operation='DECODE'):
    import hashlib,base64
    key = str(key) if key else ''
    string = str(string)
    key = hashlib.md5(key).hexdigest()
    keya = hashlib.md5(key[:16]).hexdigest()
    keyb = hashlib.md5(key[16:]).hexdigest()
    cryptkey = keya + hashlib.md5(keya).hexdigest()
    key_length = len(cryptkey)
    
    if operation == 'DECODE':
        string = base64.urlsafe_b64decode(string)
    else:
        string = hashlib.md5(string + keyb).hexdigest()[:16] + string
    string_length = len(string)
    
    result = ''
    box = range(256)
    rndkey = {}
    for i in range(256):
        rndkey[i] = ord(cryptkey[i % key_length])
    
    j = 0
    for i in range(256):
        j = (j + box[i] + rndkey[i]) % 256
        tmp = box[i]
        box[i] = box[j]
        box[j] = tmp
    a = j = 0
    for i in range(string_length):
        a = (a + 1) % 256
        j = (j + box[a]) % 256
        tmp = box[a]
        box[a] = box[j]
        box[j] = tmp
        result += chr(ord(string[i]) ^ (box[(box[a] + box[j]) % 256]))
    if operation == 'DECODE':
        if result[:16] == hashlib.md5(result[16:] + keyb).hexdigest()[:16]:
            return result[16:]
        else:
            return ''
    else:
        return base64.urlsafe_b64encode(result)
        