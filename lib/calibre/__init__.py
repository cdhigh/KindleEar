''' E-book management software'''
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, re, time, builtins
from polyglot.builtins import codepoint_to_chr, hasenv, native_string_type
from math import floor
from functools import partial

from calibre.constants import (preferred_encoding, __appname__, __version__, __author__,
        plugins, filesystem_encoding, config_dir)
import calibre.utils.resources #这个模块也有初始化代码
from calibre.utils.icu import safe_chr
from calibre.prints import prints
from calibre.utils.resources import get_path as P
from calibre.utils.icu import lower as icu_lower, title_case, upper as icu_upper
builtins.__dict__['icu_lower'] = icu_lower
builtins.__dict__['icu_upper'] = icu_upper
builtins.__dict__['icu_title'] = title_case

_mt_inited = False

def _init_mimetypes():
    global _mt_inited
    import mimetypes
    mimetypes.init()#[P('mime.types')])
    mimetypes.add_type("application/epub+zip", ".epub")
    mimetypes.add_type("application/xhtml+xml", ".xhtml")
    mimetypes.add_type("text/html", ".html")
    mimetypes.add_type("text/html", ".htm")
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("text/plain", ".txt")
    mimetypes.add_type("application/x-dtbncx+xml", ".ncx")
    mimetypes.add_type("application/oebps-package+xml", ".opf")
    mimetypes.add_type("application/vnd.ms-opentype", ".otf")
    mimetypes.add_type("image/svg+xml", ".svg")
    mimetypes.add_type("image/jpeg", ".jpg")
    mimetypes.add_type("image/jpeg", ".jpeg")
    mimetypes.add_type("image/png", ".png")
    mimetypes.add_type("image/gif", ".gif")
    mimetypes.add_type("image/bmp", ".bmp")
    mimetypes.add_type("image/webp", ".webp")
    _mt_inited = True

def guess_type(*args, **kwargs):
    import mimetypes
    if not _mt_inited:
        _init_mimetypes()
    return mimetypes.guess_type(*args, **kwargs)


def guess_all_extensions(*args, **kwargs):
    import mimetypes
    if not _mt_inited:
        _init_mimetypes()
    return mimetypes.guess_all_extensions(*args, **kwargs)


def guess_extension(*args, **kwargs):
    import mimetypes
    if not _mt_inited:
        _init_mimetypes()
    ext = mimetypes.guess_extension(*args, **kwargs)
    if not ext and args and args[0] == 'application/x-palmreader':
        ext = '.pdb'
    return ext


def get_types_map():
    import mimetypes
    if not _mt_inited:
        _init_mimetypes()
    return mimetypes.types_map


def to_unicode(raw, encoding='utf-8', errors='strict'):
    if isinstance(raw, str):
        return raw
    return raw.decode(encoding, errors)


def unicode_path(path, abs=False):
    if isinstance(path, bytes):
        path = path.decode(filesystem_encoding)
    if abs:
        path = os.path.abspath(path)
    return path

def confirm_config_name(name):
    return name + '_again'


_filename_sanitize_unicode = frozenset(('\\', '|', '?', '*', '<',        # no2to3
    '"', ':', '>', '+', '/') + tuple(map(codepoint_to_chr, range(32))))  # no2to3


def sanitize_file_name(name, substitute='_'):
    '''
    Sanitize the filename `name`. All invalid characters are replaced by `substitute`.
    The set of invalid characters is the union of the invalid characters in Windows,
    macOS and Linux. Also removes leading and trailing whitespace.
    **WARNING:** This function also replaces path separators, so only pass file names
    and not full paths to it.
    '''
    if isbytestring(name):
        name = name.decode(filesystem_encoding, 'replace')
    if isbytestring(substitute):
        substitute = substitute.decode(filesystem_encoding, 'replace')
    chars = (substitute if c in _filename_sanitize_unicode else c for c in name)
    one = ''.join(chars)
    one = re.sub(r'\s', ' ', one).strip()
    bname, ext = os.path.splitext(one)
    one = re.sub(r'^\.+$', '_', bname)
    one = one.replace('..', substitute)
    one += ext
    # Windows doesn't like path components that end with a period or space
    if one and one[-1] in ('.', ' '):
        one = one[:-1]+'_'
    # Names starting with a period are hidden on Unix
    if one.startswith('.'):
        one = '_' + one[1:]
    return one


sanitize_file_name2 = sanitize_file_name_unicode = sanitize_file_name


class CommandLineError(Exception):
    pass

def extract(path, dir):
    extractor = None
    # First use the file header to identify its type
    with open(path, 'rb') as f:
        id_ = f.read(3)
    if id_ == b'Rar':
        from calibre.utils.unrar import extract as rarextract
        extractor = rarextract
    elif id_.startswith(b'PK'):
        from calibre.libunzip import extract as zipextract
        extractor = zipextract
    elif id_.startswith(b'7z'):
        from calibre.utils.seven_zip import extract as seven_extract
        extractor = seven_extract
    if extractor is None:
        # Fallback to file extension
        ext = os.path.splitext(path)[1][1:].lower()
        if ext in ('zip', 'cbz', 'epub', 'oebzip'):
            from calibre.libunzip import extract as zipextract
            extractor = zipextract
        elif ext in ('cbr', 'rar'):
            from calibre.utils.unrar import extract as rarextract
            extractor = rarextract
        elif ext in ('cb7', '7z'):
            from calibre.utils.seven_zip import extract as seven_extract
            extractor = seven_extract
    if extractor is None:
        raise Exception('Unknown archive type')
    extractor(path, dir)

def fit_image(width, height, pwidth, pheight):
    '''
    Fit image in box of width pwidth and height pheight.
    @param width: Width of image
    @param height: Height of image
    @param pwidth: Width of box
    @param pheight: Height of box
    @return: scaled, new_width, new_height. scaled is True iff new_width and/or new_height is different from width or height.
    '''
    if height < 1 or width < 1:
        return False, int(width), int(height)
    scaled = height > pheight or width > pwidth
    if height > pheight:
        corrf = pheight / float(height)
        width, height = floor(corrf*width), pheight
    if width > pwidth:
        corrf = pwidth / float(width)
        width, height = pwidth, floor(corrf*height)
    if height > pheight:
        corrf = pheight / float(height)
        width, height = floor(corrf*width), pheight

    return scaled, int(width), int(height)


class CurrentDir:

    def __init__(self, path):
        self.path = path
        self.cwd = None

    def __enter__(self, *args):
        self.cwd = os.getcwd()
        os.chdir(self.path)
        return self.cwd

    def __exit__(self, *args):
        try:
            os.chdir(self.cwd)
        except OSError:
            # The previous CWD no longer exists
            pass


_ncpus = None


def detect_ncpus():
    global _ncpus
    if _ncpus is None:
        _ncpus = max(1, os.cpu_count() or 1)
    return _ncpus


relpath = os.path.relpath


def walk(dir):
    ''' A nice interface to os.walk '''
    for record in os.walk(dir):
        for f in record[-1]:
            yield os.path.join(record[0], f)


def strftime(fmt, t=None):
    ''' A version of strftime that returns unicode strings and tries to handle dates
    before 1900 '''
    if not fmt:
        return ''
    if t is None:
        t = time.localtime()
    if hasattr(t, 'timetuple'):
        t = t.timetuple()
    early_year = t[0] < 1900
    if early_year:
        replacement = 1900 if t[0]%4 == 0 else 1901
        fmt = fmt.replace('%Y', '_early year hack##')
        t = list(t)
        orig_year = t[0]
        t[0] = replacement
        t = time.struct_time(t)
    ans = None
    if isinstance(fmt, bytes):
        fmt = fmt.decode('utf-8', 'replace')
    ans = time.strftime(fmt, t)
    if early_year:
        ans = ans.replace('_early year hack##', str(orig_year))
    return ans


def my_unichr(num):
    try:
        return safe_chr(num)
    except (ValueError, OverflowError):
        return '?'


def entity_to_unicode(match, exceptions=[], encoding='cp1252',
        result_exceptions={}):
    '''
    :param match: A match object such that '&'+match.group(1)';' is the entity.

    :param exceptions: A list of entities to not convert (Each entry is the name of the entity, e.g. 'apos' or '#1234'

    :param encoding: The encoding to use to decode numeric entities between 128 and 256.
    If None, the Unicode UCS encoding is used. A common encoding is cp1252.

    :param result_exceptions: A mapping of characters to entities. If the result
    is in result_exceptions, result_exception[result] is returned instead.
    Convenient way to specify exception for things like < or > that can be
    specified by various actual entities.
    '''
    def check(ch):
        return result_exceptions.get(ch, ch)

    ent = match.group(1)
    if ent in exceptions:
        return '&'+ent+';'
    if ent in {'apos', 'squot'}:  # squot is generated by some broken CMS software
        return check("'")
    if ent == 'hellips':
        ent = 'hellip'
    if ent.startswith('#'):
        try:
            if ent[1] in ('x', 'X'):
                num = int(ent[2:], 16)
            else:
                num = int(ent[1:])
        except:
            return '&'+ent+';'
        if encoding is None or num > 255:
            return check(my_unichr(num))
        try:
            return check(bytes(bytearray((num,))).decode(encoding))
        except UnicodeDecodeError:
            return check(my_unichr(num))
    from calibre.ebooks.html_entities import html5_entities
    try:
        return check(html5_entities[ent])
    except KeyError:
        pass
    from polyglot.html_entities import name2codepoint
    try:
        return check(my_unichr(name2codepoint[ent]))
    except KeyError:
        return '&'+ent+';'


_ent_pat = re.compile(r'&(\S+?);')
xml_entity_to_unicode = partial(entity_to_unicode, result_exceptions={
    '"' : '&quot;',
    "'" : '&apos;',
    '<' : '&lt;',
    '>' : '&gt;',
    '&' : '&amp;'})


def replace_entities(raw, encoding='cp1252'):
    return _ent_pat.sub(partial(entity_to_unicode, encoding=encoding), raw)


def xml_replace_entities(raw, encoding='cp1252'):
    return _ent_pat.sub(partial(xml_entity_to_unicode, encoding=encoding), raw)


def prepare_string_for_xml(raw, attribute=False):
    raw = _ent_pat.sub(entity_to_unicode, raw)
    raw = raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if attribute:
        raw = raw.replace('"', '&quot;').replace("'", '&apos;')
    return raw


def isbytestring(obj):
    return isinstance(obj, bytes)


def force_unicode(obj, enc=preferred_encoding):
    if isbytestring(obj):
        try:
            obj = obj.decode(enc)
        except Exception:
            try:
                obj = obj.decode(filesystem_encoding if enc ==
                        preferred_encoding else preferred_encoding)
            except Exception:
                try:
                    obj = obj.decode('utf-8')
                except Exception:
                    obj = repr(obj)
                    if isbytestring(obj):
                        obj = obj.decode('utf-8')
    return obj


def as_unicode(obj, enc=preferred_encoding):
    if not isbytestring(obj):
        try:
            obj = str(obj)
        except Exception:
            try:
                obj = native_string_type(obj)
            except Exception:
                obj = repr(obj)
    return force_unicode(obj, enc=enc)

def human_readable(size, sep=' '):
    """ Convert a size in bytes into a human readable form """
    divisor, suffix = 1, "B"
    for i, candidate in enumerate(('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB')):
        if size < (1 << ((i + 1) * 10)):
            divisor, suffix = (1 << (i * 10)), candidate
            break
    size = str(float(size)/divisor)
    if size.find(".") > -1:
        size = size[:size.find(".")+2]
    if size.endswith('.0'):
        size = size[:-2]
    return size + sep + suffix

