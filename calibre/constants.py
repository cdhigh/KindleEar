__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__appname__   = u'calibre'
numeric_version = (1, 0, 0)
__version__   = u'.'.join(map(unicode, numeric_version))
__author__    = u"Kovid Goyal <kovid@kovidgoyal.net>"

'''
Various run time constants.
'''

import sys, codecs

iswindows = False
ispy3 = False

#try:
#    preferred_encoding = locale.getpreferredencoding()
#    codecs.lookup(preferred_encoding)
#except:
preferred_encoding = 'utf-8'

winerror   = None
_osx_ver = None

filesystem_encoding = sys.getfilesystemencoding()
if filesystem_encoding is None:
    filesystem_encoding = 'utf-8'
else:
    try:
        if codecs.lookup(filesystem_encoding).name == 'ascii':
            filesystem_encoding = 'utf-8'
    except:
        filesystem_encoding = 'utf-8'

DEBUG = False
plugins = None
CONFIG_DIR_MODE = 0700
config_dir = ""
