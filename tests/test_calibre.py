#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#测试Calibre功能
import os, sys, logging, builtins
import pytest

currDir = os.path.dirname(os.path.abspath(__file__))
baseDir = os.path.dirname(currDir)
sys.path.insert(0, os.path.join(baseDir, 'lib'))
sys.path.insert(0, baseDir)
log = logging.getLogger()
builtins.__dict__['default_log'] = log
builtins.__dict__['_'] = lambda x: x

from collections import defaultdict
import datetime, time, imghdr, io
from bs4 import BeautifulSoup
from makeoeb import *
from calibre.ebooks.conversion.plugins.mobi_output import MOBIOutput, AZW3Output
from calibre.ebooks.conversion.plugins.epub_output import EPUBOutput
from books.base_book import ItemHtmlTuple

#用于本机测试
class WindowsTestContainer(object):
    def __init__(self, log=None):
        self.log = log if log else default_log
    def read(self, path):
        path = path.lower()
        #所有的图片文件都放在images目录下
        if path.endswith((".jpg",".png",".gif",".jpeg")) \
            and '/' not in path:
            path = os.path.join(baseDir, "images", path)

        d = ''
        self.log.warning("reading file '{}'".format(path))
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

class TestCalibre:
    def setup_method(self):
        pass
    def teardown_method(self):
        pass

    def test_epub(self):
        self.CreateEbook("epub")

    def test_mobi(self):
        self.CreateEbook("mobi")

    def test_azw3(self):
        self.CreateEbook("azw3")

    def CreateEbook(self, bookType):
        itemCnt = 0
        imgIndex = 0
        sections = defaultdict(list)
        tocThumbnails = {}
        bookMode = 'periodical'
        log = default_log
        opts = GetOpts("kindle", bookMode)
        oeb = CreateOeb(log, opts)
        oeb.container = WindowsTestContainer(log)
        bookTitle = "test"
        pubType = 'book:book:KindleEar' if bookMode == 'comic' else 'periodical:magazine:KindleEar'
        author = 'KindleEar'
        setMetaData(oeb, bookTitle, "zh", "2024-01-11", pubType=pubType, creator=author)

        #masthead
        id_, href = oeb.manifest.generate('masthead', "mh_default.gif")
        oeb.manifest.add(id_, href, ImageMimeFromName("mh_default.gif"))
        oeb.guide.add('masthead', 'Masthead Image', href)

        #添加图像
        with open(os.path.join(baseDir, 'images\\cv_default.jpg'), 'rb') as f:
            content = f.read()
        id_, href = oeb.manifest.generate(id='img', href="test.jpg")
        oeb.manifest.add(id_, href, "image/jpeg", data=content)
        tocThumbnails["https://k.app.com/cv.jpg"] = href
        #添加CSS
        with open(os.path.join(baseDir, 'static\\base.css'), 'r', encoding='utf-8') as f:
            content = f.read()
        oeb.manifest.add('css', "https://k.app.com/base.css", "text/css", data=content)

        #添加HTML
        with open(os.path.join(baseDir, 'static\\faq.html'), 'r', encoding='utf-8') as f:
            content = f.read()
        soup = BeautifulSoup(content, 'lxml')
        #section url title soup brief thumbnailUrl
        item = ItemHtmlTuple('sec1', 'https://k.app.com/faq.html', 'T1', soup, 'Brief', "https://k.app.com/cv.jpg")
        sections[item.section].append(item)

        #添加HTML
        with open(os.path.join(baseDir, 'static\\faq_en.html'), 'r', encoding='utf-8') as f:
            content = f.read()
        soup = BeautifulSoup(content, 'lxml')
        #section url title soup brief thumbnailUrl
        item = ItemHtmlTuple('sec1', 'https://k.app.com/faq_en.html', 'T2', soup, 'Brief2', "")
        sections[item.section].append(item)

        #插入单独的目录页
        InsertToc(oeb, sections, tocThumbnails)
        oIO = io.BytesIO()
        if bookType == "epub":
            o = EPUBOutput()
        elif bookType == "mobi":
            o = MOBIOutput()
        else:
            o = AZW3Output()
        o.convert(oeb, oIO, opts, log)
        
        with open(os.path.join(currDir, f"test.{bookType}"), 'wb') as f:
            f.write(oIO.getvalue())

if __name__ == "__main__":
    sys.exit(pytest.main())

