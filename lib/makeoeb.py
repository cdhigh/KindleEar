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

#OEB的一些生成选项
def GetOpts(outputType='kindle', bookMode='periodical'):
    from calibre.customize.profiles import output_profiles, KindleOutput
    from config import REDUCE_IMAGE_TO
    #找到对应的设备分辨率之类的信息
    OutputDevice = KindleOutput
    for prfType in output_profiles:
        if prfType.short_name == outputType:
            OutputDevice = prfType
            break

    opts = OptionValues()
    opts.book_mode = bookMode
    opts.pretty_print = True
    opts.prefer_author_sort = True
    opts.share_not_sync = False
    opts.mobi_file_type = 'both' if bookMode == 'comic' else 'old' #mobi_file_type='old' | 'both'
    opts.dont_compress = True
    opts.no_inline_toc = True
    opts.toc_title = "Table of Contents"
    opts.mobi_toc_at_start = False
    opts.linearize_tables = True
    opts.source = None
    opts.dest = OutputDevice(None)
    opts.output_profile = OutputDevice(None)
    opts.mobi_ignore_margins = True
    opts.extract_to = None
    opts.change_justification = "Left"
    opts.process_images = True
    opts.mobi_keep_original_images = False
    opts.graying_image = COLOR_TO_GRAY #changed
    opts.image_png_to_jpg = COLOR_TO_GRAY #changed
    opts.fix_indents = False
    opts.dont_split_on_page_breaks = False
    opts.flow_size = 260
    opts.no_default_epub_cover = True
    opts.no_svg_cover = True
    opts.preserve_cover_aspect_ratio = True
    opts.epub_flatten = False
    opts.epub_dont_compress = False
    opts.epub_inline_toc = False
    opts.epub_version = 2
    opts.expand_css = False
    opts.verbose = 0
    opts.test = 0
    opts.no_inline_navbars = True
    opts.needs_subscription = False
    opts.process_images_immediately = True
    opts.dont_download_recipe = True
    opts.original_recipe_input_arg = ''
    opts.username = ''
    opts.password = ''
    opts.lrf = None
    
    if REDUCE_IMAGE_TO:
        opts.reduce_image_to = REDUCE_IMAGE_TO
    elif bookMode == 'comic':
        opts.reduce_image_to = OutputDevice.comic_screen_size
    else:
        opts.reduce_image_to = OutputDevice.screen_size
    
    return opts
    
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

#创建OEB的两级目录，第一级目录为段(section)目录，第二级目录为段下面每个html的目录
#sections为有序字典，关键词为段名，元素为ItemHtmlTuple
#tocThumbnails为字典，关键词为图片原始URL，元素为其在oeb内的href
#此函数主要代码由rexdf贡献
def InsertToc(oeb, sections, tocThumbnails, insertHtmlToc=True, insertThumbnail=True):
    if 'custom.css' in oeb.manifest.hrefs:
        linkCss = '<link charset="utf-8" href="custom.css" rel="stylesheet" type="text/css" />'
    else:
        linkCss = ''
        
    ncxToc = [] #里面保存的是 ItemNcxTocTuple
    #htmlToc2 secondary toc
    htmlToc2 = [] #每section一个元素，每个元素为对应section的二级目录，为一个html带很多个ol
    nameSectionList = []
    for secIdx, sec in enumerate(sections.keys()):
        cssList = [INIT_TOC_CSS,]
        htmlContent = []
        secondaryTocList = []
        firstFlag = False
        secTocThumbnail = None
        #每个section的每个html文件
        for artiIdx, item in enumerate(sections[sec], 1):
            #抽取每个文件的CSS，统一汇总起来加到最后生成的大文件头部
            styleTag = item.soup.find('style')
            cssList.append(''.join(map(str, styleTag.contents)) if styleTag else '')
            
            #每个原始HTML都使用一个div包装起来再放到最终的大HTML文件里
            htmlContent.append('<div id="{}"{}>'.format(artiIdx, (' class="pagebreak"' if firstFlag else '')))
            firstFlag = True

            #每个section第一篇文章的第一个图像文件做为目录界面上显示的图像
            secTocThumbnail = secTocThumbnail or item.thumbnailUrl
            
            #将body抽取出来，不包含body标签，每个Section里面所有的HTML文件组装为一个大的HTML
            bodyTag = item.soup.find('body')
            htmlContent.append(''.join(map(str, bodyTag.contents)) if bodyTag else '')
            htmlContent.append('</div>')

            secondaryTocList.append((item.title, artiIdx, item.brief, item.thumbnailUrl))

        htmlContent.append('</body></html>')
        htmlContent.insert(0, '<html><head><title>{title}</title><style type="text/css">{css}</style>{linkCss}</head><body>'.format(
            title=sec, css=''.join(cssList), linkCss=linkCss))
        
        #将 section.html 添加到清单（manifest）和书脊（spine）中
        id_, href = oeb.manifest.generate(id='feed', href='feed{}.html'.format(secIdx))
        manif = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=''.join(htmlContent))
        oeb.spine.add(manif, True)
        
        #在目录分类中添加每个目录下的文章篇数
        secTitleWithNum = '{} ({})'.format(sec, len(sections[sec]))
        ncxToc.append(ItemNcxTocTuple('section', secTitleWithNum, href, '', secTocThumbnail))
        
        #生成次级目录（Secondary TOC）
        if insertHtmlToc:
            htmlToc = ['<html><head><title>toc</title></head><body><h2>{}</h2><ol>'.format(secTitleWithNum)]

        for title, anchor, brief, thumbnailUrl in secondaryTocList:
            if insertHtmlToc:
                htmlToc.append('&nbsp;&nbsp;&nbsp;&nbsp;<li><a href="{}#{}">{}</a></li><br />'.format(href, anchor, title))
            ncxToc.append(ItemNcxTocTuple('article', title, '{}#{}'.format(href, anchor), brief, thumbnailUrl))

        if insertHtmlToc:
            htmlToc.append('</ol></body></html>')
            htmlToc2.append(''.join(htmlToc))
            nameSectionList.append(secTitleWithNum)

    if insertHtmlToc:
        #生成Calibre的HTML目录
        htmlTocTop = deque() #html_toc_1 顶层目录，双端列表数据结构，方便在左边插入元素
        
        #因为spine.insert()每次都在头部插入，所以反向遍历 htmlToc2
        for a in range(len(htmlToc2) - 1, -1, -1):
            #生成次级HTML目录
            id_, href = oeb.manifest.generate(id='section', href='toc_{}.html'.format(a))
            manif = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=htmlToc2[a])
            oeb.spine.insert(0, manif, True)
            htmlTocTop.appendleft('&nbsp;&nbsp;&nbsp;&nbsp;<li><a href="{}">{}</a></li><br />'.format(href, nameSectionList[a]))
        
        htmlTocTop.appendleft('<html><head><title>Table Of Contents</title></head><body><h2>{}</h2><ul>'.format(TABLE_OF_CONTENTS))
        htmlTocTop.append('</ul></body></html>')
        #将顶端TOC插入OEB
        id_, href = oeb.manifest.generate(id='toc', href='toc.html')
        manif = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=''.join(htmlTocTop))
        oeb.guide.add('toc', 'Table of Contents', href)
        oeb.spine.insert(0, manif, True)

    #生成 Kindle 的 NCX 目录
    toc = oeb.toc.add(oeb.metadata.title[0], oeb.spine[0].href, id='periodical', klass='periodical', play_order=1)
    secToc = None
    for playOrder, ncx in enumerate(ncxToc, 2):
        tocThumbnail = tocThumbnails[ncx.thumbnailUrl] if insertThumbnail and ncx.thumbnailUrl else None
        if ncx.klass == 'section':
            secToc = toc.add(ncx.title, ncx.href, klass='section', play_order=playOrder, id='Main-section-{}'.format(playOrder), 
                toc_thumbnail=tocThumbnail)
        elif secToc:
            secToc.add(ncx.title, ncx.href, description=ncx.brief if ncx.brief else None, klass='article', play_order=playOrder, 
                id='article-{}'.format(playOrder), toc_thumbnail=tocThumbnail)

