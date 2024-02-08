#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import numbers
import os
import re
import traceback
from collections import defaultdict
from contextlib import suppress
from copy import deepcopy
from functools import partial

from calibre.constants import (config_dir, filesystem_encoding, iswindows,
    preferred_encoding,
)
from calibre.utils.localization import _
from calibre.utils.resources import get_path as P
from polyglot.builtins import iteritems

plugin_dir = os.path.join(config_dir, 'plugins')


def parse_old_style(src):
    import pickle as cPickle
    options = {'cPickle':cPickle}
    try:
        if not isinstance(src, str):
            src = src.decode('utf-8')
        src = re.sub(r'PyQt(?:4|5).QtCore', r'PyQt6.QtCore', src)
        src = re.sub(r'cPickle\.loads\(([\'"])', r'cPickle.loads(b\1', src)
        exec(src, options)
    except Exception as err:
        try:
            print(f'Failed to parse old style options string with error: {err}')
        except Exception:
            pass
    return options


def to_json(obj):
    import datetime
    if isinstance(obj, bytearray):
        from base64 import standard_b64encode
        return {'__class__': 'bytearray',
                '__value__': standard_b64encode(bytes(obj)).decode('ascii')}
    if isinstance(obj, datetime.datetime):
        from calibre.utils.date import isoformat
        return {'__class__': 'datetime.datetime',
                '__value__': isoformat(obj, as_utc=True)}
    if isinstance(obj, (set, frozenset)):
        return {'__class__': 'set', '__value__': tuple(obj)}
    if isinstance(obj, bytes):
        return obj.decode('utf-8')
    if hasattr(obj, 'toBase64'):  # QByteArray
        return {'__class__': 'bytearray',
                '__value__': bytes(obj.toBase64()).decode('ascii')}
    v = getattr(obj, 'value', None)
    if isinstance(v, int):  # Possibly an enum with integer values like all the Qt enums
        return v
    raise TypeError(repr(obj) + ' is not JSON serializable')


def safe_to_json(obj):
    try:
        return to_json(obj)
    except Exception:
        pass


def from_json(obj):
    custom = obj.get('__class__')
    if custom is not None:
        if custom == 'bytearray':
            from base64 import standard_b64decode
            return bytearray(standard_b64decode(obj['__value__'].encode('ascii')))
        if custom == 'datetime.datetime':
            from calibre.utils.iso8601 import parse_iso8601
            return parse_iso8601(obj['__value__'], assume_utc=True)
        if custom == 'set':
            return set(obj['__value__'])
    return obj


def force_unicode(x):
    try:
        return x.decode('mbcs' if iswindows else preferred_encoding)
    except UnicodeDecodeError:
        try:
            return x.decode(filesystem_encoding)
        except UnicodeDecodeError:
            return x.decode('utf-8', 'replace')


def force_unicode_recursive(obj):
    if isinstance(obj, bytes):
        return force_unicode(obj)
    if isinstance(obj, (list, tuple)):
        return type(obj)(map(force_unicode_recursive, obj))
    if isinstance(obj, dict):
        return {force_unicode_recursive(k): force_unicode_recursive(v) for k, v in iteritems(obj)}
    return obj


def json_dumps(obj, ignore_unserializable=False):
    import json
    try:
        ans = json.dumps(obj, indent=2, default=safe_to_json if ignore_unserializable else to_json, sort_keys=True, ensure_ascii=False)
    except UnicodeDecodeError:
        obj = force_unicode_recursive(obj)
        ans = json.dumps(obj, indent=2, default=safe_to_json if ignore_unserializable else to_json, sort_keys=True, ensure_ascii=False)
    if not isinstance(ans, bytes):
        ans = ans.encode('utf-8')
    return ans


def json_loads(raw):
    import json
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    return json.loads(raw, object_hook=from_json)

class Option:

    def __init__(self, name, switches=[], help='', type=None, choices=None,
                 check=None, group=None, default=None, action=None, metavar=None):
        if choices:
            type = 'choice'

        self.name     = name
        self.switches = switches
        self.help     = help.replace('%default', repr(default)) if help else None
        self.type     = type
        if self.type is None and action is None and choices is None:
            if isinstance(default, float):
                self.type = 'float'
            elif isinstance(default, numbers.Integral) and not isinstance(default, bool):
                self.type = 'int'

        self.choices  = choices
        self.check    = check
        self.group    = group
        self.default  = default
        self.action   = action
        self.metavar  = metavar

    def __eq__(self, other):
        return self.name == getattr(other, 'name', other)

    def __repr__(self):
        return 'Option: '+self.name

    def __str__(self):
        return repr(self)


class OptionValues:

    def copy(self):
        return deepcopy(self)


class OptionSet:

    OVERRIDE_PAT = re.compile(r'#{3,100} Override Options #{15}(.*?)#{3,100} End Override #{3,100}',
                              re.DOTALL|re.IGNORECASE)

    def __init__(self, description=''):
        self.description = description
        self.defaults = {}
        self.preferences = []
        self.group_list  = []
        self.groups      = {}
        self.set_buffer  = {}
        self.loads_pat = None

    def has_option(self, name_or_option_object):
        if name_or_option_object in self.preferences:
            return True
        for p in self.preferences:
            if p.name == name_or_option_object:
                return True
        return False

    def get_option(self, name_or_option_object):
        idx = self.preferences.index(name_or_option_object)
        if idx > -1:
            return self.preferences[idx]
        for p in self.preferences:
            if p.name == name_or_option_object:
                return p

    def add_group(self, name, description=''):
        if name in self.group_list:
            raise ValueError('A group by the name %s already exists in this set'%name)
        self.groups[name] = description
        self.group_list.append(name)
        return partial(self.add_opt, group=name)

    def update(self, other):
        for name in other.groups.keys():
            self.groups[name] = other.groups[name]
            if name not in self.group_list:
                self.group_list.append(name)
        for pref in other.preferences:
            if pref in self.preferences:
                self.preferences.remove(pref)
            self.preferences.append(pref)

    def smart_update(self, opts1, opts2):
        '''
        Updates the preference values in opts1 using only the non-default preference values in opts2.
        '''
        for pref in self.preferences:
            new = getattr(opts2, pref.name, pref.default)
            if new != pref.default:
                setattr(opts1, pref.name, new)

    def remove_opt(self, name):
        if name in self.preferences:
            self.preferences.remove(name)

    def add_opt(self, name, switches=[], help=None, type=None, choices=None,
                 group=None, default=None, action=None, metavar=None):
        '''
        Add an option to this section.

        :param name:       The name of this option. Must be a valid Python identifier.
                           Must also be unique in this OptionSet and all its subsets.
        :param switches:   List of command line switches for this option
                           (as supplied to :module:`optparse`). If empty, this
                           option will not be added to the command line parser.
        :param help:       Help text.
        :param type:       Type checking of option values. Supported types are:
                           `None, 'choice', 'complex', 'float', 'int', 'string'`.
        :param choices:    List of strings or `None`.
        :param group:      Group this option belongs to. You must previously
                           have created this group with a call to :method:`add_group`.
        :param default:    The default value for this option.
        :param action:     The action to pass to optparse. Supported values are:
                           `None, 'count'`. For choices and boolean options,
                           action is automatically set correctly.
        '''
        pref = Option(name, switches=switches, help=help, type=type, choices=choices,
                 group=group, default=default, action=action, metavar=None)
        if group is not None and group not in self.groups.keys():
            raise ValueError('Group %s has not been added to this section'%group)
        if pref in self.preferences:
            raise ValueError('An option with the name %s already exists in this set.'%name)
        self.preferences.append(pref)
        self.defaults[name] = default

    def retranslate_help(self):
        t = _
        for opt in self.preferences:
            if opt.help:
                opt.help = t(opt.help)
                if opt.name == 'use_primary_find_in_search':
                    opt.help = opt.help.format('ñ')

    def option_parser(self, user_defaults=None, usage='', gui_mode=False):
        from calibre.utils.config import OptionParser
        parser = OptionParser(usage, gui_mode=gui_mode)
        groups = defaultdict(lambda : parser)
        for group, desc in self.groups.items():
            groups[group] = parser.add_option_group(group.upper(), desc)

        for pref in self.preferences:
            if not pref.switches:
                continue
            g = groups[pref.group]
            action = pref.action
            if action is None:
                action = 'store'
                if pref.default is True or pref.default is False:
                    action = 'store_' + ('False' if pref.default else 'True')
            args = dict(
                        dest=pref.name,
                        help=pref.help,
                        metavar=pref.metavar,
                        type=pref.type,
                        choices=pref.choices,
                        default=getattr(user_defaults, pref.name, pref.default),
                        action=action,
                        )
            g.add_option(*pref.switches, **args)

        return parser

    def get_override_section(self, src):
        match = self.OVERRIDE_PAT.search(src)
        if match:
            return match.group()
        return ''

    def parse_string(self, src):
        options = {}
        if src:
            is_old_style = (isinstance(src, bytes) and src.startswith(b'#')) or (isinstance(src, str) and src.startswith('#'))
            if is_old_style:
                options = parse_old_style(src)
            else:
                try:
                    options = json_loads(src)
                    if not isinstance(options, dict):
                        raise Exception('options is not a dictionary')
                except Exception as err:
                    try:
                        print(f'Failed to parse options string with error: {err}')
                    except Exception:
                        pass
        opts = OptionValues()
        for pref in self.preferences:
            val = options.get(pref.name, pref.default)
            formatter = __builtins__.get(pref.type, None)
            if callable(formatter):
                val = formatter(val)
            setattr(opts, pref.name, val)

        return opts

    def serialize(self, opts, ignore_unserializable=False):
        data = {pref.name: getattr(opts, pref.name, pref.default) for pref in self.preferences}
        return json_dumps(data, ignore_unserializable=ignore_unserializable)


class ConfigInterface:

    def __init__(self, description):
        self.option_set       = OptionSet(description=description)
        self.add_opt          = self.option_set.add_opt
        self.add_group        = self.option_set.add_group
        self.remove_opt       = self.remove = self.option_set.remove_opt
        self.parse_string     = self.option_set.parse_string
        self.get_option       = self.option_set.get_option
        self.preferences      = self.option_set.preferences

    def update(self, other):
        self.option_set.update(other.option_set)

    def option_parser(self, usage='', gui_mode=False):
        return self.option_set.option_parser(user_defaults=self.parse(),
                                             usage=usage, gui_mode=gui_mode)

    def smart_update(self, opts1, opts2):
        self.option_set.smart_update(opts1, opts2)

def read_data(file_path):
    with open(file_path, 'rb') as f:
        return f.read()

class Config(ConfigInterface):
    '''
    A file based configuration.
    '''

    def __init__(self, basename, description=''):
        ConfigInterface.__init__(self, description)
        self.filename_base = basename

    @property
    def config_file_path(self):
        return os.path.join(config_dir, self.filename_base + '.py.json')

    def parse(self):
        return OptionSet()
        src = ''
        migrate = False
        path = self.config_file_path
        with suppress(FileNotFoundError):
            src_bytes = read_data(path)
            try:
                src = src_bytes.decode('utf-8')
            except ValueError:
                print("Failed to parse", path)
                traceback.print_exc()
        if not src:
            path = path.rpartition('.')[0]
            try:
                with open(path, 'rb') as f:
                    src = f.read().decode('utf-8')
            except Exception:
                pass
            else:
                migrate = bool(src)
        ans = self.option_set.parse_string(src)
        #return ans

    def set(self, name, val):
        pass
        

class StringConfig(ConfigInterface):
    '''
    A string based configuration
    '''

    def __init__(self, src, description=''):
        ConfigInterface.__init__(self, description)
        self.set_src(src)

    def set_src(self, src):
        self.src = src
        if isinstance(self.src, bytes):
            self.src = self.src.decode('utf-8')

    def parse(self):
        return self.option_set.parse_string(self.src)

    def set(self, name, val):
        if not self.option_set.has_option(name):
            raise ValueError('The option %s is not defined.'%name)
        opts = self.option_set.parse_string(self.src)
        setattr(opts, name, val)
        self.set_src(self.option_set.serialize(opts))


class ConfigProxy:
    '''
    A Proxy to minimize file reads for widely used config settings
    '''

    def __init__(self, config):
        self.__config = config
        self.__opts   = None

    @property
    def defaults(self):
        return self.__config.option_set.defaults

    def refresh(self):
        self.__opts = self.__config.parse()

    def retranslate_help(self):
        self.__config.option_set.retranslate_help()

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, val):
        return self.set(key, val)

    def __delitem__(self, key):
        self.set(key, self.defaults[key])

    def get(self, key):
        if self.__opts is None:
            self.refresh()
        return getattr(self.__opts, key, None)

    def set(self, key, val):
        if self.__opts is None:
            self.refresh()
        setattr(self.__opts, key, val)
        return self.__config.set(key, val)

    def help(self, key):
        return self.__config.get_option(key).help


def create_global_prefs(conf_obj=None):
    c = Config('global', 'calibre wide preferences') if conf_obj is None else conf_obj
    c.add_opt('database_path',
              default=os.path.expanduser('~/library1.db'),
              help=_('Path to the database in which books are stored'))
    c.add_opt('filename_pattern', default='(?P<title>.+) - (?P<author>[^_]+)',
              help=_('Pattern to guess metadata from filenames'))
    c.add_opt('isbndb_com_key', default='',
              help=_('Access key for isbndb.com'))
    c.add_opt('network_timeout', default=5,
              help=_('Default timeout for network operations (seconds)'))
    c.add_opt('library_path', default=None,
              help=_('Path to folder in which your library of books is stored'))
    c.add_opt('language', default=None,
              help=_('The language in which to display the user interface'))
    c.add_opt('output_format', default='EPUB',
              help=_('The default output format for e-book conversions. When auto-converting'
                  ' to send to a device this can be overridden by individual device preferences.'
                  ' These can be changed by right clicking the device icon in calibre and'
                  ' choosing "Configure".'))
    c.add_opt('input_format_order', default=['EPUB', 'AZW3', 'MOBI', 'LIT', 'PRC',
        'FB2', 'HTML', 'HTM', 'XHTM', 'SHTML', 'XHTML', 'ZIP', 'DOCX', 'ODT', 'RTF', 'PDF',
        'TXT'],
              help=_('Ordered list of formats to prefer for input.'))
    c.add_opt('read_file_metadata', default=True,
              help=_('Read metadata from files'))
    c.add_opt('worker_process_priority', default='normal',
              help=_('The priority of worker processes. A higher priority '
                  'means they run faster and consume more resources. '
                  'Most tasks like conversion/news download/adding books/etc. '
                  'are affected by this setting.'))
    c.add_opt('swap_author_names', default=False,
            help=_('Swap author first and last names when reading metadata'))
    c.add_opt('add_formats_to_existing', default=False,
            help=_('Add new formats to existing book records'))
    c.add_opt('check_for_dupes_on_ctl', default=False,
            help=_('Check for duplicates when copying to another library'))
    c.add_opt('installation_uuid', default=None, help='Installation UUID')
    c.add_opt('new_book_tags', default=[], help=_('Tags to apply to books added to the library'))
    c.add_opt('mark_new_books', default=False, help=_(
        'Mark newly added books. The mark is a temporary mark that is automatically removed when calibre is restarted.'))

    # these are here instead of the gui preferences because calibredb and
    # calibre server can execute searches
    c.add_opt('saved_searches', default={}, help=_('List of named saved searches'))
    c.add_opt('user_categories', default={}, help=_('User-created Tag browser categories'))
    c.add_opt('manage_device_metadata', default='manual',
        help=_('How and when calibre updates metadata on the device.'))
    c.add_opt('limit_search_columns', default=False,
            help=_('When searching for text without using lookup '
            'prefixes, as for example, Red instead of title:Red, '
            'limit the columns searched to those named below.'))
    c.add_opt('limit_search_columns_to',
            default=['title', 'authors', 'tags', 'series', 'publisher'],
            help=_('Choose columns to be searched when not using prefixes, '
                'as for example, when searching for Red instead of '
                'title:Red. Enter a list of search/lookup names '
                'separated by commas. Only takes effect if you set the option '
                'to limit search columns above.'))
    c.add_opt('use_primary_find_in_search', default=True,
            help=_('Characters typed in the search box will match their '
                   'accented versions, based on the language you have chosen '
                   'for the calibre interface. For example, in '
                   'English, searching for n will match both {} and n, but if '
                   'your language is Spanish it will only match n. Note that '
                   'this is much slower than a simple search on very large '
                   'libraries. Also, this option will have no effect if you turn '
                   'on case-sensitive searching.'))
    c.add_opt('case_sensitive', default=False, help=_(
        'Make searches case-sensitive'))
    c.add_opt('numeric_collation', default=False,
            help=_('Recognize numbers inside text when sorting. Setting this '
                   'means that when sorting on text fields like title the text "Book 2"'
                   'will sort before the text "Book 100". Note that setting this '
                   'can cause problems with text that starts with numbers and is '
                   'a little slower.'))

    c.add_opt('migrated', default=False, help='For Internal use. Don\'t modify.')
    return c


prefs = ConfigProxy(create_global_prefs())
if prefs['installation_uuid'] is None:
    import uuid
    prefs['installation_uuid'] = str(uuid.uuid4())

tweaks = {"series_index_auto_increment": "next",
  "use_series_auto_increment_tweak_when_importing": False,
  "authors_completer_append_separator": False,
  "author_sort_copy_method": "comma",
  "author_name_suffixes": [
    "Jr",
    "Sr",
    "Inc",
    "Ph.D",
    "Phd",
    "MD",
    "M.D",
    "I",
    "II",
    "III",
    "IV",
    "Junior",
    "Senior"
  ],
  "author_name_prefixes": [
    "Mr",
    "Mrs",
    "Ms",
    "Dr",
    "Prof"
  ],
  "author_name_copywords": [
    "Corporation",
    "Company",
    "Co.",
    "Agency",
    "Council",
    "Committee",
    "Inc.",
    "Institute",
    "Society",
    "Club",
    "Team"
  ],
  "authors_split_regex": "(?i),?\\s+(and|with)\\s+",
  "categories_use_field_for_author_name": "author",
  "categories_collapsed_name_template": "{first.sort:shorten(4,,0)} - {last.sort:shorten(4,,0)}",
  "categories_collapsed_rating_template": "{first.avg_rating:4.2f:ifempty(0)} - {last.avg_rating:4.2f:ifempty(0)}",
  "categories_collapsed_popularity_template": "{first.count:d} - {last.count:d}",
  "tag_browser_category_order": {
    "*": 1
  },
  "sort_columns_at_startup": None,
  "gui_pubdate_display_format": "MMM yyyy",
  "gui_timestamp_display_format": "dd MMM yyyy",
  "gui_last_modified_display_format": "dd MMM yyyy",
  "title_series_sorting": "library_order",
  "save_template_title_series_sorting": "library_order",
  "per_language_title_sort_articles": {
    "eng": [
      "A\\s+",
      "The\\s+",
      "An\\s+"
    ],
    "epo": [
      "La\\s+",
      "L'",
      "L\u00b4"
    ],
    "spa": [
      "El\\s+",
      "La\\s+",
      "Lo\\s+",
      "Los\\s+",
      "Las\\s+",
      "Un\\s+",
      "Una\\s+",
      "Unos\\s+",
      "Unas\\s+"
    ],
    "fra": [
      "Le\\s+",
      "La\\s+",
      "L'",
      "L\u00b4",
      "L\u2019",
      "Les\\s+",
      "Un\\s+",
      "Une\\s+",
      "Des\\s+",
      "De\\s+La\\s+",
      "De\\s+",
      "D'",
      "D\u00b4",
      "L\u2019"
    ],
    "ita": [
      "Lo\\s+",
      "Il\\s+",
      "L'",
      "L\u00b4",
      "La\\s+",
      "Gli\\s+",
      "I\\s+",
      "Le\\s+",
      "Uno\\s+",
      "Un\\s+",
      "Una\\s+",
      "Un'",
      "Un\u00b4",
      "Dei\\s+",
      "Degli\\s+",
      "Delle\\s+",
      "Del\\s+",
      "Della\\s+",
      "Dello\\s+",
      "Dell'",
      "Dell\u00b4"
    ],
    "por": [
      "A\\s+",
      "O\\s+",
      "Os\\s+",
      "As\\s+",
      "Um\\s+",
      "Uns\\s+",
      "Uma\\s+",
      "Umas\\s+"
    ],
    "ron": [
      "Un\\s+",
      "O\\s+",
      "Ni\u015fte\\s+"
    ],
    "deu": [
      "Der\\s+",
      "Die\\s+",
      "Das\\s+",
      "Den\\s+",
      "Ein\\s+",
      "Eine\\s+",
      "Einen\\s+",
      "Dem\\s+",
      "Des\\s+",
      "Einem\\s+",
      "Eines\\s+"
    ],
    "nld": [
      "De\\s+",
      "Het\\s+",
      "Een\\s+",
      "'n\\s+",
      "'s\\s+",
      "Ene\\s+",
      "Ener\\s+",
      "Enes\\s+",
      "Den\\s+",
      "Der\\s+",
      "Des\\s+",
      "'t\\s+"
    ],
    "swe": [
      "En\\s+",
      "Ett\\s+",
      "Det\\s+",
      "Den\\s+",
      "De\\s+"
    ],
    "tur": [
      "Bir\\s+"
    ],
    "afr": [
      "'n\\s+",
      "Die\\s+"
    ],
    "ell": [
      "O\\s+",
      "I\\s+",
      "To\\s+",
      "Ta\\s+",
      "Tus\\s+",
      "Tis\\s+",
      "'Enas\\s+",
      "'Mia\\s+",
      "'Ena\\s+",
      "'Enan\\s+"
    ],
    "hun": [
      "A\\s+",
      "Az\\s+",
      "Egy\\s+"
    ]
  },
  "default_language_for_title_sort": None,
  "title_sort_articles": "^(A|The|An)\\s+",
  "auto_connect_to_folder": "",
  "sony_collection_renaming_rules": {},
  "sony_collection_name_template": "{value}{category:| (|)}",
  "sony_collection_sorting_rules": [],
  "add_new_book_tags_when_importing_books": False,
  "content_server_will_display": [
    "*"
  ],
  "content_server_wont_display": [],
  "maximum_resort_levels": 5,
  "sort_dates_using_visible_fields": False,
  "cover_trim_fuzz_value": 10,
  "doubleclick_on_library_view": "open_viewer",
  "enter_key_behavior": "do_nothing",
  "horizontal_scrolling_per_column": True,
  "locale_for_sorting": "",
  "metadata_single_use_2_cols_for_custom_fields": True,
  "metadata_edit_custom_column_order": [],
  "public_smtp_relay_delay": 301,
  "public_smtp_relay_host_suffixes": [
    "gmail.com",
    "live.com",
    "gmx.com"
  ],
  "maximum_cover_size": [
    1650,
    2200
  ],
  "send_news_to_device_location": "main",
  "unified_title_toolbar_on_osx": False,
  "save_original_format": True,
  "save_original_format_when_polishing": True,
  "gui_view_history_size": 15,
  "change_book_details_font_size_by": 0,
  "default_tweak_format": None,
  "preselect_first_completion": False,
  "completion_mode": "prefix",
  "numeric_collation": False,
  "many_libraries": 10,
  "restrict_output_formats": None,
  "content_server_thumbnail_compression_quality": 75,
  "cover_drop_exclude": [],
  "show_saved_search_box": False,
  "exclude_fields_on_paste": [],
  "skip_network_check": False
}

class Tweak:

    def __init__(self, name, value):
        self.name, self.value = name, value

    def __enter__(self):
        self.origval = tweaks[self.name]
        tweaks[self.name] = self.value

    def __exit__(self, *args):
        tweaks[self.name] = self.origval
