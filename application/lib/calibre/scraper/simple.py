#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>
#使用urlopener模拟calibre的qt WebEngineBrowser
def read_url(storage, url, timeout=60, as_html=True):
    from urlopener import UrlOpener
    raw_bytes = UrlOpener().open_novisit(url, timeout=timeout).read()
    if not as_html:
        return raw_bytes
    from calibre.ebooks.chardet import xml_to_unicode
    return xml_to_unicode(raw_bytes, strip_encoding_pats=True)[0]

def cleanup_overseers():
    return lambda : 1
