#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#将News feed生成的HTML文件转换成内存中的OEB格式
#Author: cdhigh <https://github.com/cdhigh>

import os, uuid, datetime
from collections import deque
from collections import namedtuple

from calibre.ebooks.conversion.plugins.mobi_output import MOBIOutput, AZW3Output
from calibre.ebooks.conversion.plugins.epub_output import EPUBOutput

from config import *

#TOC(Table of Contents)初始默认CSS
INIT_TOC_CSS='.pagebreak{page-break-before:always;}h1{font-size:2.0em;}h2{font-size:1.5em;}h3{font-size:1.4em;}h4{font-size:1.2em;}h5{font-size:1.1em;}h6{font-size:1.0em;}'
ItemNcxTocTuple = namedtuple("ItemNcxTocTuple", "klass title href brief thumbnailUrl")
TABLE_OF_CONTENTS = "Table of Contents"

#从文件名生成MIME，只针对图像文件
def ImageMimeFromName(f):
    f = f.lower()
    if f.endswith(('.gif', '.png', 'bmp')):
        return 'image/{}'.format(f[-3:])
    elif f.endswith(('.jpg', '.jpeg')):
        return 'image/jpeg'
    elif f.endswith('.tiff'):
        return 'image/' + f[-4:]
    else:
        return ''

#传递给Mobi/epub模块的参数设置
class OptionValues(object):
    pass

#用做服务器环境下的文件读写桩对象
class ServerContainer(object):
    def __init__(self, log=None):
        self.log = log if log else default_log
    def read(self, path):
        path = path.lower()
        #所有的图片文件都放在images目录下
        if path.endswith((".jpg",".png",".gif",".jpeg")) \
            and '/' not in path:
            path = os.path.join("images", path)

        d = ''
        try:
            with open(path, "rb") as f:
                d = f.read()
        except Exception as e:
            self.log.warning("read file '{}' failed : {}".format(path, e))
        
        return d
    def write(self, path):
        return None
    def exists(self, path):
        return False
    def namelist(self):
        return []

#创建一个空的OEB书籍
#opts: OptionValues实例，描述书籍的一些元信息
#log: 用来记录错误信息的Logging实例，为空则使用 default_log
#container: 用来读写文件的桩对象，如果为空，则自动创建一个 ServerContainer
#encoding: OEB的文件编码
def CreateEmptyOeb(opts, log=None, container=None, encoding='utf-8'):
    from calibre.ebooks.conversion.preprocess import HTMLPreProcessor
    from calibre.ebooks.oeb.base import OEBBook
    log = log if log else default_log
    html_preprocessor = HTMLPreProcessor(log, opts)
    if not encoding:
        encoding = None
    pretty_print = opts.pretty_print if opts else False
    oeb = OEBBook(log, html_preprocessor, pretty_print=pretty_print, input_encoding=encoding)
    oeb.container = container or ServerContainer(log)
    return oeb

def setMetaData(oeb, title='Feeds', lang='zh-cn', date=None, creator='KindleEar',
    pubType='periodical:magazine:KindleEar'): #pubType='periodical:magazine:KindleEar' | 'book:book:KindleEar'
    oeb.metadata.add('language', lang if lang else 'zh-cn')
    oeb.metadata.add('creator', creator)
    oeb.metadata.add('title', title)
    oeb.metadata.add('identifier', str(uuid.uuid4()), id='uuid_id', scheme='uuid')
    oeb.uid = oeb.metadata.identifier[0]
    oeb.metadata.add("publication_type", pubType)
    if not date:
        date = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d')
    oeb.metadata.add("date", date)
