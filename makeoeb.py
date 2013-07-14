#!usr/bin/Python
# -*- coding:utf-8 -*-
#将News feed生成的HTML文件转换成内存中的OEB格式
import os, sys,__builtin__, uuid, locale, codecs, logging, datetime
from StringIO import StringIO

sys.extensions_location = r"."
sys.resources_location = r"."

#这两个是必须先引入的，会有一些全局初始化
import calibre.startup
import calibre.utils.resources

#from calibre.utils.usrlogging import *
from calibre.customize.profiles import KindleInput, KindleOutput
from calibre.ebooks.oeb.base import TOC
from calibre.ebooks.conversion.mobioutput import MOBIOutput
from calibre.ebooks.conversion.epuboutput import EPUBOutput
from calibre.utils.bytestringio import byteStringIO
from calibre.ebooks.oeb.base import OEBBook
from calibre.ebooks.conversion.preprocess import HTMLPreProcessor

#传递给Mobi/epub模块的参数设置
class OptionValues(object):
    pass

class FsContainer(object):
    """An empty container.
    For use with book formats which do not support container-like access.
    """
    def __init__(self, dir=None, log=None):
        self.log = log
        self.dir = dir
    def read(self, path):
        print(path)
        f = open(os.path.join(self.dir, path), "rb")
        d = f.read()
        f.close()
        return d
    def write(self, path):
        return None
    def exists(self, path):
        return False
    def namelist(self):
        return []

def CreateOeb(log, path_or_stream, opts, encoding='utf-8'):
    """创建一个空的OEB书籍"""
    html_preprocessor = HTMLPreProcessor(log, opts)
    if not encoding:
        encoding = None
    oeb = OEBBook(log, html_preprocessor, pretty_print=opts.pretty_print, input_encoding=encoding)
    return oeb

def getOpts():
    opts = OptionValues()
    setattr(opts, "pretty_print", False)
    setattr(opts, "prefer_author_sort", True)
    setattr(opts, "share_not_sync", False)
    setattr(opts, "mobi_file_type", 'old')
    setattr(opts, "dont_compress", True)
    setattr(opts, "no_inline_toc", True)
    setattr(opts, "toc_title", "Table of Contents")
    setattr(opts, "mobi_toc_at_start", False)
    setattr(opts, "linearize_tables", True)
    setattr(opts, "source", None)
    setattr(opts, "dest", KindleOutput(None))
    setattr(opts, "output_profile", KindleOutput(None))
    setattr(opts, "mobi_ignore_margins", True)
    setattr(opts, "extract_to", None)
    setattr(opts, "change_justification", "Left")
    setattr(opts, "process_images", True)
    setattr(opts, "mobi_keep_original_images", False)
    setattr(opts, "graying_image", True)
    setattr(opts, "image_png_to_jpg", False)
    setattr(opts, "fix_indents", False)
    
    #epub
    setattr(opts, "dont_split_on_page_breaks", False)
    setattr(opts, "flow_size", 260)
    setattr(opts, "no_default_epub_cover", True)
    setattr(opts, "no_svg_cover", True)
    setattr(opts, "preserve_cover_aspect_ratio", True)
    setattr(opts, "epub_flatten", False)
    setattr(opts, "epub_dont_compress", True)
    
    return opts
    
def setMetaData(oeb, title='Feeds', lang='zh-cn', date=None, creator='Arroz'):
    oeb.metadata.add('language', lang if lang else 'zh-cn')
    oeb.metadata.add('creator', creator)
    oeb.metadata.add('title', title)
    oeb.metadata.add('identifier', str(uuid.uuid4()), id='uuid_id', scheme='uuid')
    oeb.uid = oeb.metadata.identifier[0]
    oeb.metadata.add("publication_type", "periodical:magazine:KindleEar")
    if not date:
        date = datetime.datetime.strftime(datetime.datetime.now(),"%Y-%m-%d")
    oeb.metadata.add("date", date)

