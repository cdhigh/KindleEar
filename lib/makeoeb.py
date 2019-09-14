#!usr/bin/Python
# -*- coding:utf-8 -*-
#将News feed生成的HTML文件转换成内存中的OEB格式
#Author: cdhigh <https://github.com/cdhigh>
import os, sys, uuid, re

#这两个是必须先引入的，会有一些全局初始化
import calibre.startup
import calibre.utils.resources

from calibre.ebooks.conversion.mobioutput import MOBIOutput
from calibre.ebooks.conversion.epuboutput import EPUBOutput
from calibre.utils.bytestringio import byteStringIO
from config import *

def MimeFromFilename(f):
    #从文件名生成MIME
    f = f.lower()
    if f.endswith(('.gif', '.png', 'bmp')):
        return r'image/' + f[-3:]
    elif f.endswith(('.jpg', '.jpeg')):
        return r'image/jpeg'
    elif f.endswith('.tiff'):
        return r'image/' + f[-4:]
    else:
        return ''

#传递给Mobi/epub模块的参数设置
class OptionValues(object):
    pass

class ServerContainer(object):
    def __init__(self, log=None):
        self.log = log if log else default_log
    def read(self, path):
        path = path.lower()
        #所有的图片文件都放在images目录下
        if path.endswith((".jpg",".png",".gif",".jpeg")) \
            and r'/' not in path:
            path = os.path.join("images", path)

        d = ''
        try:
            with open(path, "rb") as f:
                d = f.read()
        except Exception as e:
            self.log.warn("read file '%s' failed : %s" % (path, str(e)))
        
        return d
    def write(self, path):
        return None
    def exists(self, path):
        return False
    def namelist(self):
        return []

#创建一个空的OEB书籍
def CreateOeb(log, path_or_stream, opts, encoding='utf-8'):
    from calibre.ebooks.conversion.preprocess import HTMLPreProcessor
    from calibre.ebooks.oeb.base import OEBBook
    html_preprocessor = HTMLPreProcessor(log, opts)
    if not encoding:
        encoding = None
    pretty_print = opts.pretty_print if opts else False
    return OEBBook(log, html_preprocessor, pretty_print=pretty_print, input_encoding=encoding)

#OEB的一些生成选项
def getOpts(output_type='kindle', book_mode='periodical'):
    from calibre.customize.profiles import (KindleOutput, KindlePaperWhiteOutput, KindleDXOutput, KindleFireOutput, 
        KindleVoyageOutput, KindlePaperWhite3Output, KindleOasisOutput, OutputProfile)
    from config import REDUCE_IMAGE_TO
    opts = OptionValues()
    setattr(opts, "pretty_print", False)
    setattr(opts, "prefer_author_sort", True)
    setattr(opts, "share_not_sync", False)
    setattr(opts, "mobi_file_type", 'both' if book_mode == 'comic' else 'old') #mobi_file_type='old' | 'both'
    setattr(opts, "dont_compress", True)
    setattr(opts, "no_inline_toc", True)
    setattr(opts, "toc_title", "Table of Contents")
    setattr(opts, "mobi_toc_at_start", False)
    setattr(opts, "linearize_tables", True)
    setattr(opts, "source", None)
    outputdic = {
        'kindle': KindleOutput,
        'kindledx': KindleDXOutput,
        'kindlepw': KindlePaperWhiteOutput,
        'kindlefire': KindleFireOutput,
        'kindlevoyage': KindleVoyageOutput,
        'kindlepw3': KindlePaperWhite3Output,
        'kindlepw4': KindlePaperWhite3Output,
        'kindleoasis': KindleOasisOutput,
        'others': OutputProfile,
        }
    OutputDevice = outputdic.get(output_type, KindleOutput)
    setattr(opts, "dest", OutputDevice(None))
    setattr(opts, "output_profile", OutputDevice(None))
    setattr(opts, "mobi_ignore_margins", True)
    setattr(opts, "extract_to", None)
    setattr(opts, "change_justification", "Left")
    setattr(opts, "process_images", True)
    setattr(opts, "mobi_keep_original_images", False)
    setattr(opts, "graying_image", COLOR_TO_GRAY) #changed
    setattr(opts, "image_png_to_jpg", COLOR_TO_GRAY) #changed
    setattr(opts, "fix_indents", False)
    if REDUCE_IMAGE_TO:
        setattr(opts, "reduce_image_to", REDUCE_IMAGE_TO)
    else:
        setattr(opts, "reduce_image_to", OutputDevice.comic_screen_size if book_mode == 'comic' else OutputDevice.screen_size)
    
    #epub
    setattr(opts, "dont_split_on_page_breaks", False)
    setattr(opts, "flow_size", 260)
    setattr(opts, "no_default_epub_cover", True)
    setattr(opts, "no_svg_cover", True)
    setattr(opts, "preserve_cover_aspect_ratio", True)
    setattr(opts, "epub_flatten", False)
    setattr(opts, "epub_dont_compress", False)
    setattr(opts, "verbose", 0)
    
    #extra customed by KindleEar
    setattr(opts, "process_images_immediately", True)
    setattr(opts, "book_mode", book_mode)
    return opts
    
def setMetaData(oeb, title='Feeds', lang='zh-cn', date=None, creator='KindleEar',
    pubtype='periodical:magazine:KindleEar'): #pubtype='periodical:magazine:KindleEar' | 'book:book:KindleEar'
    oeb.metadata.add('language', lang if lang else 'zh-cn')
    oeb.metadata.add('creator', creator)
    oeb.metadata.add('title', title)
    oeb.metadata.add('identifier', str(uuid.uuid4()), id='uuid_id', scheme='uuid')
    oeb.uid = oeb.metadata.identifier[0]
    oeb.metadata.add("publication_type", pubtype)
    if not date:
        import datetime
        date = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d')
    oeb.metadata.add("date", date)


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
    
    if 'custom.css' in oeb.manifest.hrefs:
        linkCss = '<link charset="utf-8" href="custom.css" rel="stylesheet" type="text/css" />'
    else:
        linkCss = ''
        
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
                html_content.append(body_obj.group() + '</div>') #insect article
                secondary_toc_list.append((title, num_articles, brief, thumbnail))
                num_articles += 1
            else:
                html_content.pop()
        html_content.append('</body></html>')
        
        html_content.insert(0, '<html><head><title>%s</title><style type="text/css">%s</style>%s</head><body>' % (sec, ''.join(css), linkCss))
        
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
        html_toc_1 = [u'<html><head><title>Table Of Contents</title></head><body><h2>%s</h2><ul>' % (TABLE_OF_CONTENTS)]
        html_toc_1_ = []
        #We need index but not reversed()
        for a in xrange(len(html_toc_2) - 1, -1, -1):
            #Generate Secondary HTML TOC
            id_, href = oeb.manifest.generate(id='section', href='toc_%d.html' % (a))
            item = oeb.manifest.add(id_, href, 'application/xhtml+xml', data=" ".join(html_toc_2[a]))
            oeb.spine.insert(0, item, True)
            html_toc_1_.append('&nbsp;&nbsp;&nbsp;&nbsp;<li><a href="%s">%s</a></li><br />' % (href,name_section_list[a]))
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
            sectoc = toc.add(unicode(ncx[1]), ncx[2], klass='section', play_order=po, id='Main-section-%d' % po, 
                toc_thumbnail=toc_thumbnail)
        elif sectoc:
            sectoc.add(unicode(ncx[1]), ncx[2], description=ncx[3] if ncx[3] else None, klass='article', play_order=po, 
                id='article-%d' % po, toc_thumbnail=toc_thumbnail)
        po += 1
