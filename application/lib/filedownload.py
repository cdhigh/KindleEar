#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""GAE文件下载类，如果文件太大，则分块下载
更新：切换到Python3后GAE限制提高到32M，不再需要分块下载
"""
from collections import namedtuple
from urllib.parse import urlparse, urlunparse
from urlopener import UrlOpener

DownloadedFileTuple = namedtuple("DownloadedFileTuple", "status fileName content")

#FileDownload工具函数，简化文件下载工作 
#返回一个命名元祖 DownloadedFileTuple
def Download(url):
    url, fileName = ConvertDownloadUrl(url)

    opener = UrlOpener()
    resp = opener.open(url)
    content = resp.content
    
    if resp.status_code == 413:
        return DownloadedFileTuple('too large', fileName, b'')
    elif resp.status_code not in (200, 206):
        return DownloadedFileTuple(f'dl failed:{resp.status_code}', fileName, b'')
    elif not content:
        return DownloadedFileTuple('not resuming', fileName, b'')
    else:
        return DownloadedFileTuple('', fileName, content)


#根据需要，将url适当转换用于下载书籍本身，而不是包含书籍的html
#返回：(newUrl, fileName)
def ConvertDownloadUrl(url):
    parts = urlparse(url)
    fileName = parts.path.split('/')[-1]
    if parts.netloc in ('github.com', 'www.github.com') and '/blob/' in parts.path:
        parts = parts._replace(path=parts.path.replace('/blob/', '/raw/'))

    return urlunparse(parts), fileName

