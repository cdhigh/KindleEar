#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>
#from polyglot.builtins import environ_item, hasenv
import sys, locale, collections, collections.abc

__appname__   = 'calibre'
numeric_version = (7, 2, 0)
__version__   = '.'.join(map(str, numeric_version))
git_version   = None
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"

'''
Various run time constants.
'''


#_plat = sys.platform.lower()
iswindows = False #'win32' in _plat or 'win64' in _plat
ismacos = isosx = False #'darwin' in _plat
isnewosx  = False #ismacos and getattr(sys, 'new_app_bundle', False)
isfreebsd = False #'freebsd' in _plat
isnetbsd = False #'netbsd' in _plat
isdragonflybsd = False #'dragonfly' in _plat
isbsd = False #isfreebsd or isnetbsd or isdragonflybsd
ishaiku = False #'haiku1' in _plat
islinux   = False #not (iswindows or ismacos or isbsd or ishaiku)
isfrozen  = False #hasattr(sys, 'frozen')
isunix = False #ismacos or islinux or ishaiku
ispy3 = sys.version_info.major > 2
is64bit = True
try:
    preferred_encoding = locale.getpreferredencoding()
    #codecs.lookup(preferred_encoding)
except:
    preferred_encoding = 'utf-8'

filesystem_encoding = sys.getfilesystemencoding()
if filesystem_encoding is None:
    filesystem_encoding = 'utf-8'

class Plugins(collections.abc.Mapping):
    def __iter__(self):
        return

    def __len__(self):
        return 0

    def __contains__(self, name):
        return False

    def __getitem__(self, name):
        return None, ""

plugins = Plugins()
config_dir = ""
DEBUG = False