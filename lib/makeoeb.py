#!usr/bin/Python
# -*- coding:utf-8 -*-
#将News feed生成的HTML文件转换成内存中的OEB格式
#Author: cdhigh <https://github.com/cdhigh>
import os, sys, uuid

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
        KindleVoyageOutput, KindlePaperWhite3Output, OutputProfile)
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

