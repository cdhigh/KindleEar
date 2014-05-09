#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

class BadFormat(ValueError):
    pass

def do_explode(path, dest):
    pass

def explode(path, dest, question=lambda x:True):
    pass

def set_cover(oeb):
    if 'cover' not in oeb.guide or oeb.metadata['cover']:
        return
    cover = oeb.guide['cover']
    if cover.href in oeb.manifest.hrefs:
        item = oeb.manifest.hrefs[cover.href]
        oeb.metadata.clear('cover')
        oeb.metadata.add('cover', item.id)

def do_rebuild(opf, dest_path):
    pass

def rebuild(src_dir, dest_path):
    pass
