from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Manage application-wide preferences.
'''
import os, cPickle, base64, datetime, json, plistlib
from copy import deepcopy
from optparse import OptionParser as _OptionParser, OptionGroup
from optparse import IndentedHelpFormatter

from calibre.constants import (config_dir, CONFIG_DIR_MODE, __appname__,
        __version__, __author__)

def check_config_write_access():
    return os.access(config_dir, os.W_OK) and os.access(config_dir, os.X_OK)

class CustomHelpFormatter(IndentedHelpFormatter):

    def format_usage(self, usage):
        from calibre.utils.terminal import colored
        parts = usage.split(' ')
        if parts:
            parts[0] = colored(parts[0], fg='yellow', bold=True)
        usage = ' '.join(parts)
        return colored('Usage', fg='blue', bold=True) + ': ' + usage

    def format_heading(self, heading):
        from calibre.utils.terminal import colored
        return "%*s%s:\n" % (self.current_indent, '',
                                 colored(heading, fg='blue', bold=True))

    def format_option(self, option):
        import textwrap
        from calibre.utils.terminal import colored

        result = []
        opts = self.option_strings[option]
        opt_width = self.help_position - self.current_indent - 2
        if len(opts) > opt_width:
            opts = "%*s%s\n" % (self.current_indent, "",
                                    colored(opts, fg='green'))
            indent_first = self.help_position
        else:                       # start help on same line as opts
            opts = "%*s%-*s  " % (self.current_indent, "", opt_width +
                    len(colored('', fg='green')), colored(opts, fg='green'))
            indent_first = 0
        result.append(opts)
        if option.help:
            help_text = self.expand_default(option).split('\n')
            help_lines = []

            for line in help_text:
                help_lines.extend(textwrap.wrap(line, self.help_width))
            result.append("%*s%s\n" % (indent_first, "", help_lines[0]))
            result.extend(["%*s%s\n" % (self.help_position, "", line)
                           for line in help_lines[1:]])
        elif opts[-1] != "\n":
            result.append("\n")
        return "".join(result)+'\n'


class OptionParser(_OptionParser):

    def __init__(self,
                 usage='%prog [options] filename',
                 version='%%prog (%s %s)'%(__appname__, __version__),
                 epilog=None,
                 gui_mode=False,
                 conflict_handler='resolve',
                 **kwds):
        import textwrap
        from calibre.utils.terminal import colored

        usage = textwrap.dedent(usage)
        if epilog is None:
            epilog = 'Created by '
        usage += '\n\n'
        _OptionParser.__init__(self, usage=usage, version=version, epilog=epilog,
                               formatter=CustomHelpFormatter(),
                               conflict_handler=conflict_handler, **kwds)
        self.gui_mode = gui_mode
        
    def print_usage(self, file=None):
        from calibre.utils.terminal import ANSIStream
        s = ANSIStream(file)
        _OptionParser.print_usage(self, file=s)

    def print_help(self, file=None):
        from calibre.utils.terminal import ANSIStream
        s = ANSIStream(file)
        _OptionParser.print_help(self, file=s)

    def print_version(self, file=None):
        from calibre.utils.terminal import ANSIStream
        s = ANSIStream(file)
        _OptionParser.print_version(self, file=s)

    def error(self, msg):
        if self.gui_mode:
            raise Exception(msg)
        _OptionParser.error(self, msg)

    def merge(self, parser):
        '''
        Add options from parser to self. In case of conflicts, conflicting options from
        parser are skipped.
        '''
        opts   = list(parser.option_list)
        groups = list(parser.option_groups)

        def merge_options(options, container):
            for opt in deepcopy(options):
                if not self.has_option(opt.get_opt_string()):
                    container.add_option(opt)

        merge_options(opts, self)

        for group in groups:
            g = self.add_option_group(group.title)
            merge_options(group.option_list, g)

    def subsume(self, group_name, msg=''):
        '''
        Move all existing options into a subgroup named
        C{group_name} with description C{msg}.
        '''
        opts = [opt for opt in self.options_iter() if opt.get_opt_string() not in ('--version', '--help')]
        self.option_groups = []
        subgroup = self.add_option_group(group_name, msg)
        for opt in opts:
            self.remove_option(opt.get_opt_string())
            subgroup.add_option(opt)

    def options_iter(self):
        for opt in self.option_list:
            if str(opt).strip():
                yield opt
        for gr in self.option_groups:
            for opt in gr.option_list:
                if str(opt).strip():
                    yield opt

    def option_by_dest(self, dest):
        for opt in self.options_iter():
            if opt.dest == dest:
                return opt

    def merge_options(self, lower, upper):
        '''
        Merge options in lower and upper option lists into upper.
        Default values in upper are overridden by
        non default values in lower.
        '''
        for dest in lower.__dict__.keys():
            if not dest in upper.__dict__:
                continue
            opt = self.option_by_dest(dest)
            if lower.__dict__[dest] != opt.default and \
               upper.__dict__[dest] == opt.default:
                upper.__dict__[dest] = lower.__dict__[dest]

    def add_option_group(self, *args, **kwargs):
        if isinstance(args[0], type(u'')):
            args = [OptionGroup(self, *args, **kwargs)] + list(args[1:])
        return _OptionParser.add_option_group(self, *args, **kwargs)

def to_json(obj):
    if isinstance(obj, bytearray):
        return {'__class__': 'bytearray',
                '__value__': base64.standard_b64encode(bytes(obj))}
    if isinstance(obj, datetime.datetime):
        from calibre.utils.date import isoformat
        return {'__class__': 'datetime.datetime',
                '__value__': isoformat(obj, as_utc=True)}
    raise TypeError(repr(obj) + ' is not JSON serializable')

def from_json(obj):
    if '__class__' in obj:
        if obj['__class__'] == 'bytearray':
            return bytearray(base64.standard_b64decode(obj['__value__']))
        if obj['__class__'] == 'datetime.datetime':
            from calibre.utils.date import parse_date
            return parse_date(obj['__value__'], assume_utc=True)
    return obj


