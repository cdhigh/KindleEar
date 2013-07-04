__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__appname__   = u'calibre'
__version__   = "0.9"
__author__    = u"Kovid Goyal <kovid@kovidgoyal.net>"

'''
Various run time constants.
'''

import sys, locale, codecs

iswindows = False
isosx     = False
isnewosx  = False
isfreebsd = False
isnetbsd = False
isdragonflybsd = False
isbsd = False
islinux   = False
isfrozen  = False
isunix = False
isportable = False
ispy3 = False
isxp = False
is64bit = False
isworker = False

try:
    preferred_encoding = locale.getpreferredencoding()
    codecs.lookup(preferred_encoding)
except:
    preferred_encoding = 'utf-8'

iswindows = False
win32event = None
winerror   = None
win32api   = None
fcntl      = None #if iswindows else importlib.import_module('fcntl')

_osx_ver = None

filesystem_encoding = sys.getfilesystemencoding()
if filesystem_encoding is None:
    filesystem_encoding = 'utf-8'
else:
    try:
        if codecs.lookup(filesystem_encoding).name == 'ascii':
            filesystem_encoding = 'utf-8'
            # On linux, unicode arguments to os file functions are coerced to an ascii
            # bytestring if sys.getfilesystemencoding() == 'ascii', which is
            # just plain dumb. This is fixed by the icu.py module which, when
            # imported changes ascii to utf-8
    except:
        filesystem_encoding = 'utf-8'

DEBUG = False
_cache_dir = None
plugins = None
CONFIG_DIR_MODE = 0700
config_dir = ""
