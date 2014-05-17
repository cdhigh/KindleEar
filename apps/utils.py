#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#中文讨论贴：http://www.hi-pda.com/forum/viewthread.php?tid=1213082
#Author:
# cdhigh <https://github.com/cdhigh>
#Contributors:
# rexdf <https://github.com/rexdf>

from config import *
import datetime
import gettext
import re

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

def InsertToc(oeb, sections, toc_thumbnails):
    """ 创建OEB的两级目录，主要代码由rexdf贡献
    sections为有序字典，关键词为段名，元素为元组列表(title,brief,humbnail,content)
    toc_thumbnails为字典，关键词为图片原始URL，元素为其在oeb内的href。
    """
    body_pat = r'(?<=<body>).*?(?=</body>)'
    body_ex = re.compile(body_pat,re.M|re.S)
    num_articles = 1
    num_sections = 0
    
    ncx_toc = []
    #html_toc_2 secondary toc
    html_toc_2 = []
    name_section_list = []
    for sec in sections.keys():
        htmlcontent = ['<html><head><title>%s</title><style type="text/css">.pagebreak{page-break-before:always;}h1{font-size:2.0em;}h2{font-size:1.5em;}h3{font-size:1.4em;} h4{font-size:1.2em;}h5{font-size:1.1em;}h6{font-size:1.0em;} </style></head><body>' % (sec)]
        secondary_toc_list = []
        first_flag = False
        sec_toc_thumbnail = None
        for title, brief, thumbnail, content in sections[sec]:
            if first_flag:
                htmlcontent.append('<div id="%d" class="pagebreak">' % (num_articles)) #insert anchor && pagebreak
            else:
                htmlcontent.append('<div id="%d">' % (num_articles)) #insert anchor && pagebreak
                first_flag = True
                if thumbnail:
                    sec_toc_thumbnail = thumbnail #url
            body_obj = re.search(body_ex, content)
            if body_obj:
                htmlcontent.append(body_obj.group()+'</div>') #insect article
                secondary_toc_list.append((title, num_articles, brief, thumbnail))
                num_articles += 1
            else:
                htmlcontent.pop()
        htmlcontent.append('</body></html>')
        
        #add section.html to maninfest and spine
        #We'd better not use id as variable. It's a python builtin function.
        id_, href = oeb.manifest.generate(id='feed', href='feed%d.html'%num_sections)
        item = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=''.join(htmlcontent))
        oeb.spine.add(item, True)
        ncx_toc.append(('section',sec,href,'',sec_toc_thumbnail)) #Sections name && href && no brief

        #generate the secondary toc
        if GENERATE_HTML_TOC:
            html_toc_ = ['<html><head><title>toc</title></head><body><h2>%s</h2><ol>' % (sec)]
        for title, anchor, brief, thumbnail in secondary_toc_list:
            if GENERATE_HTML_TOC:
                html_toc_.append('&nbsp;&nbsp;&nbsp;&nbsp;<li><a href="%s#%d">%s</a></li><br />'%(href, anchor, title))
            ncx_toc.append(('article',title, '%s#%d'%(href,anchor), brief, thumbnail)) # article name & article href && article brief
        if GENERATE_HTML_TOC:
            html_toc_.append('</ol></body></html>')
            html_toc_2.append(html_toc_)
            name_section_list.append(sec)

        num_sections += 1

    if GENERATE_HTML_TOC:
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
        if ncx[0] == 'section':
            sectoc = toc.add(unicode(ncx[1]), ncx[2], klass='section', play_order=po, id='Main-section-%d'%po, toc_thumbnail=toc_thumbnails[ncx[4]] if GENERATE_TOC_THUMBNAIL and ncx[4] else None)
        elif sectoc:
            sectoc.add(unicode(ncx[1]), ncx[2], description=ncx[3] if ncx[3] else None, klass='article', play_order=po, id='article-%d'%po, toc_thumbnail=toc_thumbnails[ncx[4]] if GENERATE_TOC_THUMBNAIL and ncx[4] else None)
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
        