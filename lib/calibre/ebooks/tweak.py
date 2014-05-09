#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

class Error(ValueError):
    pass

def ask_cli_question(msg):
    pass

def mobi_exploder(path, tdir, question=lambda x:True):
    pass

def zip_exploder(path, tdir, question=lambda x:True):
    pass

def zip_rebuilder(tdir, path):
    pass

def get_tools(fmt):
    fmt = fmt.lower()

    if fmt in {'mobi', 'azw', 'azw3'}:
        from calibre.ebooks.mobi.tweak import rebuild
        ans = mobi_exploder, rebuild
    elif fmt in {'epub', 'htmlz'}:
        ans = zip_exploder, zip_rebuilder
    else:
        ans = None, None

    return ans

def tweak(ebook_file):
    pass

