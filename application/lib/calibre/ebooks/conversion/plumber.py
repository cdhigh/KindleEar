#!/usr/bin/env python3
# -*- coding:utf-8 -*-
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PIL.Image import isImageType
import os, re, sys, shutil, pprint, json, io, css_parser, logging, traceback, copy
from itertools import chain
from functools import partial
from calibre.customize.conversion import OptionRecommendation, DummyReporter, InputFormatPlugin
from calibre.customize.ui import input_profiles, output_profiles, \
        plugin_for_input_format, plugin_for_output_format, \
        available_input_formats, available_output_formats, \
        run_plugins_on_preprocess, run_plugins_on_postprocess
from calibre.ebooks.conversion.plugins.recipe_input import RecipeInput
from calibre.ebooks.conversion.preprocess import HTMLPreProcessor
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.date import parse_date
from calibre.utils.zipfile import ZipFile
from calibre.utils.filenames import ascii_filename
from calibre import (extract, walk, isbytestring, filesystem_encoding,
        get_types_map)
from calibre.constants import __version__
from polyglot.builtins import string_or_bytes

from filesystem_dict import FsDictStub
from application.ke_utils import get_directory_size, loc_exc_pos
from application.base_handler import save_delivery_log

DEBUG_README=b'''
This debug folder contains snapshots of the e-book as it passes through the
various stages of conversion. The stages are:

    1. input - This is the result of running the input plugin on the source
    file. Use this folder to debug the input plugin.

    2. parsed - This is the result of preprocessing and parsing the output of
    the input plugin. Note that for some input plugins this will be identical to
    the input sub-folder. Use this folder to debug structure detection,
    etc.

    3. structure - This corresponds to the stage in the pipeline when structure
    detection has run, but before the CSS is flattened. Use this folder to
    debug the CSS flattening, font size conversion, etc.

    4. processed - This corresponds to the e-book as it is passed to the output
    plugin. Use this folder to debug the output plugin.

'''


def supported_input_formats():
    fmts = available_input_formats()
    for x in ('zip', 'rar', 'oebzip'):
        fmts.add(x)
    return fmts


class OptionValues:
    pass


class CompositeProgressReporter:

    def __init__(self, global_min, global_max, global_reporter):
        self.global_min, self.global_max = global_min, global_max
        self.global_reporter = global_reporter

    def __call__(self, fraction, msg=''):
        global_frac = self.global_min + fraction * \
                (self.global_max - self.global_min)
        self.global_reporter(global_frac, msg)


ARCHIVE_FMTS = ('zip', 'rar', 'oebzip')

class Plumber:

    '''
    The `Plumber` manages the conversion pipeline. An UI should call the methods
    :method:`merge_ui_recommendations` and then :method:`run`. The plumber will
    take care of the rest.
    '''

    metadata_option_names = [
        'title', 'authors', 'title_sort', 'author_sort', 'cover', 'comments',
        'publisher', 'series', 'series_index', 'rating', 'isbn',
        'tags', 'book_producer', 'language', 'pubdate', 'timestamp'
        ]

    #input_: 输入，编译好的recipes列表或包含html和相关图像的一个字典
    #output: 输出文件绝对路径名，也可能是一个BytesIO
    def __init__(self, input_, output, input_fmt, output_fmt=None, options=None, abort_after_input_dump=False):
        self.input_ = input_
        self.output = output
        self.log = default_log
        self.user_options = options or {}
        self.abort_after_input_dump = abort_after_input_dump
        self.pipeline_options = _pipeline_options
        
        if not isinstance(output, io.BytesIO) and not output_fmt:
            if os.path.exists(self.output) and os.path.isdir(self.output):
                output_fmt = 'oeb'
            else:
                output_fmt = os.path.splitext(self.output)[1]
                if not output_fmt:
                    output_fmt = '.oeb'
                output_fmt = output_fmt[1:].lower()

        self.input_plugin = copy.deepcopy(plugin_for_input_format(input_fmt))
        self.output_plugin = copy.deepcopy(plugin_for_output_format(output_fmt))
        if self.output_plugin is None:
            raise ValueError(f'No plugin to handle output format: {output_fmt}')

        self.input_fmt = input_fmt
        self.output_fmt = output_fmt
        self.input_options  = self.input_plugin.options.union(self.input_plugin.common_options)
        self.output_options = self.output_plugin.options.union(self.output_plugin.common_options)
        
    @classmethod
    def unarchive(self, path, tdir):
        extract(path, tdir)
        files = list(walk(tdir))
        files = [f if isinstance(f, str) else f.decode(filesystem_encoding)
                for f in files]
        from calibre.customize.ui import available_input_formats
        fmts = set(available_input_formats())
        fmts -= {'htm', 'html', 'xhtm', 'xhtml'}
        fmts -= set(ARCHIVE_FMTS)

        for ext in fmts:
            for f in files:
                if f.lower().endswith('.'+ext):
                    if ext in ['txt', 'rtf'] and os.stat(f).st_size < 2048:
                        continue
                    return f, ext
        return self.find_html_index(files)

    @classmethod
    def find_html_index(self, files):
        '''
        Given a list of files, find the most likely root HTML file in the
        list.
        '''
        html_pat = re.compile(r'\.(x){0,1}htm(l){0,1}$', re.IGNORECASE)
        html_files = [f for f in files if html_pat.search(f) is not None]
        if not html_files:
            raise ValueError(_('Could not find an e-book inside the archive'))
        html_files = [(f, os.stat(f).st_size) for f in html_files]
        html_files.sort(key=lambda x: x[1])
        html_files = [f[0] for f in html_files]
        for q in ('toc', 'index'):
            for f in html_files:
                if os.path.splitext(os.path.basename(f))[0].lower() == q:
                    return f, os.path.splitext(f)[1].lower()[1:]
        return html_files[-1], os.path.splitext(html_files[-1])[1].lower()[1:]

    def get_all_options(self):
        ans = {}
        for rec in chain(self.input_options, self.pipeline_options, self.output_options):
            ans[rec.option] = rec.recommended_value
        return ans

    def get_option_by_name(self, name):
        for rec in chain(self.input_options, self.pipeline_options, self.output_options):
            if rec.option == name:
                return rec

    def get_option_help(self, name):
        rec = self.get_option_by_name(name)
        help = getattr(rec, 'help', None)
        if help is not None:
            return help.replace('%default', str(rec.recommended_value))

    def get_all_help(self):
        ans = {}
        for rec in chain(self.input_options, self.pipeline_options, self.output_options):
            help = getattr(rec, 'help', None)
            if help is not None:
                ans[rec.option.name] = help
        return ans

    def merge_plugin_recs(self, plugin):
        for name, val, level in plugin.recommendations:
            rec = self.get_option_by_name(name)
            if rec is not None and rec.level <= level:
                rec.recommended_value = val
                rec.level = level

    def merge_plugin_recommendations(self):
        for source in (self.input_plugin, self.output_plugin):
            self.merge_plugin_recs(source)

    def merge_ui_recommendations(self, recommendations: dict):
        '''
        Merge recommendations from the UI. As long as the UI recommendation
        level is >= the baseline recommended level, the UI value is used,
        *except* if the baseline has a recommendation level of `HIGH`.
        '''

        def eq(name, a, b):
            if name in {'sr1_search', 'sr1_replace', 'sr2_search', 'sr2_replace', 'sr3_search', 'sr3_replace', 'filter_css', 'comments'}:
                if not a and not b:
                    return True
            if name in {'transform_css_rules', 'transform_html_rules', 'search_replace'}:
                if b == '[]':
                    b = None
            return a == b

        for name, val in (recommendations or {}).items():
            rec = self.get_option_by_name(name)
            if rec is not None:
                rec.recommended_value = val
                
    def opts_to_mi(self, opts, mi):
        from calibre.ebooks.metadata import string_to_authors
        for x in self.metadata_option_names:
            val = getattr(opts, x, None)
            if val is not None:
                if x == 'authors':
                    val = string_to_authors(val)
                elif x == 'tags':
                    val = [i.strip() for i in val.split(',')]
                elif x in ('rating', 'series_index'):
                    try:
                        val = float(val)
                    except ValueError:
                        self.log.warn(_('Values of series index and rating must'
                        ' be numbers. Ignoring'), val)
                        continue
                elif x in ('timestamp', 'pubdate'):
                    try:
                        val = parse_date(val, assume_utc=x=='timestamp')
                    except:
                        self.log.exception(_('Failed to parse date/time') + ' ' + str(val))
                        continue
                setattr(mi, x, val)

    def download_cover(self, url):
        from calibre import browser
        from PIL import Image
        import io
        from calibre.ptempfile import PersistentTemporaryFile
        self.log.info('Downloading cover from %r'%url)
        br = browser()
        raw = br.open_novisit(url).read()
        buf = io.BytesIO(raw)
        pt = PersistentTemporaryFile('.jpg')
        pt.close()
        img = Image.open(buf)
        img.convert('RGB').save(pt.name)
        return pt.name

    def read_user_metadata(self, opts):
        '''
        Read all metadata specified by the user. Command line options override
        metadata from a specified OPF file.
        '''
        from calibre.ebooks.metadata import MetaInformation
        from calibre.ebooks.metadata.opf2 import OPF
        mi = MetaInformation(None, [])
        #if self.opts.read_metadata_from_opf is not None:
        #    self.opts.read_metadata_from_opf = os.path.abspath(
        #                                    self.opts.read_metadata_from_opf)
        #    with open(self.opts.read_metadata_from_opf, 'rb') as stream:
        #        opf = OPF(stream, os.path.dirname(self.opts.read_metadata_from_opf))
        #    mi = opf.to_book_metadata()
        self.opts_to_mi(opts, mi)
        #if mi.cover:
        #    if mi.cover.startswith('http:') or mi.cover.startswith('https:'):
        #        mi.cover = self.download_cover(mi.cover)
        #    ext = mi.cover.rpartition('.')[-1].lower().strip()
        #    if ext not in ('png', 'jpg', 'jpeg', 'gif'):
        #        ext = 'jpg'
        #    with open(mi.cover, 'rb') as stream:
        #        mi.cover_data = (ext, stream.read())
        #    mi.cover = None
        self.user_metadata = mi

    def setup_options(self):
        '''
        Setup the `self.opts` object.
        '''
        opts = OptionValues()
        for group in (self.input_options, self.pipeline_options, self.output_options):
            for rec in group:
                setattr(opts, rec.option.name, rec.recommended_value)

        for name, val in self.user_options.items():
            setattr(opts, name, val)

        def set_profile(profiles, which):
            attr = which + '_profile'
            sval = getattr(opts, attr)
            for x in profiles():
                if x.short_name == sval:
                    setattr(opts, attr, x)
                    return
            self.log.warn(
                'Profile (%s) %r is no longer available, using default'%(which, sval))
            for x in profiles():
                if x.short_name == 'default':
                    setattr(opts, attr, x)
                    break

        set_profile(input_profiles, 'input')
        set_profile(output_profiles, 'output')

        self.read_user_metadata(opts)

        opts.no_inline_navbars = opts.output_profile.supports_mobi_indexing \
                and self.output_fmt == 'mobi'

        if opts.verbose > 1:
            self.log.debug('Resolved conversion options')
            try:
                self.log.debug('calibre version:', __version__)
                odict = dict(opts.__dict__)
                for x in ('username', 'password'):
                    odict.pop(x, None)
                self.log.debug(pprint.pformat(odict))
            except:
                self.log.exception('Failed to get resolved conversion options')

        self.opts = opts

    def flush(self):
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass

    def dump_oeb(self, oeb, out_dir):
        from calibre.ebooks.oeb.writer import OEBWriter
        w = OEBWriter(pretty_print=self.opts.pretty_print)
        w(oeb, out_dir)

    def dump_input(self, ret, output_dir):
        out_dir = os.path.join(self.opts.debug_pipeline, 'input')
        if isinstance(ret, string_or_bytes):
            shutil.copytree(output_dir, out_dir)
        else:
            if not os.path.exists(out_dir):
                os.makedirs(out_dir)
            self.dump_oeb(ret, out_dir)
        if self.input_fmt == 'recipe':
            zf = ZipFile(os.path.join(self.opts.debug_pipeline,
                'periodical.downloaded_recipe.zip'), 'w')
            zf.add_dir(out_dir)
            with self.input_plugin:
                self.input_plugin.save_download(zf)
            zf.close()

        self.log.info('Input debug saved to:', out_dir)

    #外部调用此函数实际转换
    def run(self):
        '''
        Run the conversion pipeline
        '''
        # Setup baseline option values
        self.setup_options()

        css_parser.log.setLevel(logging.WARN) #type:ignore
        #get_types_map()  # Ensure the mimetypes module is initialized
        debug_pipeline = self.opts.debug_pipeline #type:ignore

        if debug_pipeline:
            self.opts.verbose = max(self.opts.verbose, 4)
            debug_pipeline = os.path.abspath(debug_pipeline)
            if not os.path.exists(debug_pipeline):
                os.makedirs(debug_pipeline)
            #with open(os.path.join(debug_pipeline, 'README.txt'), 'wb') as f:
            #    f.write(DEBUG_README)
            for x in ('input', '0.download', '1.parsed', '2.structure', '3.processed'):
                x = os.path.join(debug_pipeline, x)
                try:
                    shutil.rmtree(x)
                except:
                    pass
                    
        self.output_plugin.specialize_options(self.log, self.opts, self.input_fmt)
        #根据需要，创建临时目录或创建内存缓存
        system_temp_dir = os.environ.get('KE_TEMP_DIR')
        if system_temp_dir and self.input_fmt != 'html':
            tdir = PersistentTemporaryDirectory(prefix='plumber_', dir=system_temp_dir)
            fs = FsDictStub(tdir)
        else:
            tdir = '/'
            fs = FsDictStub()
        
        #调用calibre.customize.conversion.InputFormatPlugin.__call__()，然后调用输入插件的convert()在目标目录生成一大堆文件，包含opf
        #__call__()返回传入的 fs 实例，其属性 opfname 保存了opf文件的路径名
        try:
            self.oeb = self.input_plugin(self.input_, self.opts, self.input_fmt, self.log, tdir, fs)
        except Exception as e:
            if 'All feeds are empty, aborting.' in str(e):
                self.log.warning('Plumber: All feeds are empty, aborting.')
            else:
                self.log.warning('Failed to execute input plugin: {}'.format(traceback.format_exc()))
            fs.clear()
            return

        #如果只是要制作epub的话，到目前为止，工作已经完成大半
        #将self.oeb指向的目录拷贝到OEBPS目录，加一个mimetype和一个META-INF/container.xml文件，这两个文件内容是固定的
        #再将这些文件和文件夹一起打包为zip格式，就是完整的epub电子书了
        if debug_pipeline:
           fs.dump(os.path.join(debug_pipeline, '0.download'))
           if self.abort_after_input_dump:
               return
        #if debug_pipeline:
        #    self.dump_input(self.oeb, tdir)
        #    if self.abort_after_input_dump:
        #        return
        #self.opts_to_mi(self.opts, self.user_metadata)
        
        if not hasattr(self.oeb, 'manifest'): #从一堆文件里面创建OEBBook实例
            fs.find_opf_path()
            try:
                self.oeb = create_oebbook(self.log, fs, self.opts, encoding=self.input_plugin.output_encoding,
                    removed_items=getattr(self.input_plugin, 'removed_items_to_ignore', ()))
            except:
                self.log.warning(loc_exc_pos('Failed to create oebbook'))
                fs.clear()
                return
        
        self.input_plugin.postprocess_book(self.oeb, self.opts, self.log)
        self.opts.is_image_collection = self.input_plugin.is_image_collection
        self.flush()
        if debug_pipeline:
            out_dir = os.path.join(debug_pipeline, '1.parsed')
            self.dump_oeb(self.oeb, out_dir)
            self.log.info('Parsed HTML written to:{}'.format(out_dir))
        self.input_plugin.specialize(self.oeb, self.opts, self.log,
                self.output_fmt)

        self.oeb.plumber_output_format = self.output_fmt or ''

        if self.opts.transform_html_rules:
            transform_html_rules = self.opts.transform_html_rules
            if isinstance(transform_html_rules, string_or_bytes):
                transform_html_rules = json.loads(transform_html_rules)
            from calibre.ebooks.html_transform_rules import transform_conversion_book
            transform_conversion_book(self.oeb, self.opts, transform_html_rules)

        from calibre.ebooks.oeb.transforms.data_url import DataURL
        DataURL()(self.oeb, self.opts)
        from calibre.ebooks.oeb.transforms.guide import Clean
        Clean()(self.oeb, self.opts)

        self.opts.source = self.opts.input_profile
        self.opts.dest = self.opts.output_profile

        from calibre.ebooks.oeb.transforms.jacket import RemoveFirstImage
        RemoveFirstImage()(self.oeb, self.opts, self.user_metadata)
        from calibre.ebooks.oeb.transforms.metadata import MergeMetadata
        MergeMetadata()(self.oeb, self.user_metadata, self.opts, override_input_metadata=False)

        from calibre.ebooks.oeb.transforms.structure import DetectStructure
        DetectStructure()(self.oeb, self.opts)
        
        if self.output_plugin.file_type not in ('epub', 'kepub'):
            # Remove the toc reference to the html cover, if any, except for
            # epub, as the epub output plugin will do the right thing with it.
            item = getattr(self.oeb.toc, 'item_that_refers_to_cover', None)
            if item is not None and item.count() == 0:
                self.oeb.toc.remove(item)

        from calibre.ebooks.oeb.transforms.flatcss import CSSFlattener
        fbase = self.opts.base_font_size
        if fbase < 1e-4:
            fbase = float(self.opts.dest.fbase)
        fkey = self.opts.font_size_mapping
        if fkey is None:
            fkey = self.opts.dest.fkey
        else:
            try:
                fkey = list(map(float, fkey.split(',')))
            except Exception:
                self.log.error('Invalid font size key: %r ignoring'%fkey)
                fkey = self.opts.dest.fkey

        from calibre.ebooks.oeb.transforms.jacket import Jacket
        Jacket()(self.oeb, self.opts, self.user_metadata)
        
        if debug_pipeline:
            out_dir = os.path.join(debug_pipeline, '2.structure')
            self.dump_oeb(self.oeb, out_dir)
            self.log.info('Structured HTML written to:{}'.format(out_dir))

        if self.opts.extra_css and os.path.exists(self.opts.extra_css):
            with open(self.opts.extra_css, 'rb') as f:
                self.opts.extra_css = f.read().decode('utf-8')

        oibl = self.opts.insert_blank_line
        orps  = self.opts.remove_paragraph_spacing
        if self.output_plugin.file_type == 'lrf':
            self.opts.insert_blank_line = False
            self.opts.remove_paragraph_spacing = False
        line_height = self.opts.line_height
        if line_height < 1e-4:
            line_height = None

        if self.opts.linearize_tables and \
                self.output_plugin.file_type not in ('mobi', 'lrf'):
            from calibre.ebooks.oeb.transforms.linearize_tables import LinearizeTables
            LinearizeTables()(self.oeb, self.opts)

        if self.opts.unsmarten_punctuation:
            from calibre.ebooks.oeb.transforms.unsmarten import UnsmartenPunctuation
            UnsmartenPunctuation()(self.oeb, self.opts)

        mobi_file_type = getattr(self.opts, 'mobi_file_type', 'old')
        needs_old_markup = (self.output_plugin.file_type == 'lit' or (
            self.output_plugin.file_type == 'mobi' and mobi_file_type == 'old'))
        transform_css_rules = ()
        if self.opts.transform_css_rules:
            transform_css_rules = self.opts.transform_css_rules
            if isinstance(transform_css_rules, string_or_bytes):
                transform_css_rules = json.loads(transform_css_rules)
        flattener = CSSFlattener(fbase=fbase, fkey=fkey,
                lineh=line_height,
                untable=needs_old_markup,
                unfloat=needs_old_markup,
                page_break_on_body=self.output_plugin.file_type in ('mobi',
                    'lit'),
                transform_css_rules=transform_css_rules,
                specializer=partial(self.output_plugin.specialize_css_for_output,
                    self.log, self.opts))
        flattener(self.oeb, self.opts)
        self.opts._final_base_font_size = fbase

        self.opts.insert_blank_line = oibl
        self.opts.remove_paragraph_spacing = orps

        from calibre.ebooks.oeb.transforms.page_margin import RemoveFakeMargins, RemoveAdobeMargins
        RemoveFakeMargins()(self.oeb, self.log, self.opts)
        RemoveAdobeMargins()(self.oeb, self.log, self.opts)

        if self.opts.embed_all_fonts:
            from calibre.ebooks.oeb.transforms.embed_fonts import EmbedFonts
            EmbedFonts()(self.oeb, self.log, self.opts)

        if self.opts.subset_embedded_fonts and self.output_plugin.file_type != 'pdf':
            from calibre.ebooks.oeb.transforms.subset import SubsetFonts
            SubsetFonts()(self.oeb, self.log, self.opts)

        from calibre.ebooks.oeb.transforms.trimmanifest import ManifestTrimmer

        self.log.info('Cleaning up manifest...')
        trimmer = ManifestTrimmer()
        trimmer(self.oeb, self.opts)

        self.oeb.toc.rationalize_play_orders()
        
        if debug_pipeline:
            out_dir = os.path.join(debug_pipeline, '3.processed')
            self.dump_oeb(self.oeb, out_dir)
            self.log.info('Processed HTML written to:{}'.format(out_dir))

        #如果需要在线阅读，则需要保存到输出文件夹
        self.save_oeb_if_need(self.oeb)
        
        self.log.info('Creating %s...'%self.output_plugin.name)

        #创建输出临时文件缓存
        if system_temp_dir:
            prefix = self.output_plugin.commit_name or 'output_'
            tmpdir = PersistentTemporaryDirectory(prefix=prefix, dir=system_temp_dir)
            fs_out = FsDictStub(tmpdir)
        else:
            fs_out = FsDictStub()
        
        #这才是启动输出转换，生成电子书
        with self.output_plugin:
            self.output_plugin.convert(self.oeb, self.output, self.input_plugin, self.opts, self.log, fs_out)
        self.oeb.clean_temp_files()
        fs.clear()
        fs_out.clear()
        if not isinstance(self.output, io.BytesIO):
            run_plugins_on_postprocess(self.output, self.output_fmt)

    #如果需要在线阅读，则需要保存到输出文件夹
    def save_oeb_if_need(self, oeb):
        user = self.opts.user #type:ignore
        oebDir = os.environ.get('EBOOK_SAVE_DIR')
        if getattr(self.opts, 'dont_save_webshelf') or not (oebDir and ('local' in user.cfg('delivery_mode'))):
            return

        #提取字符串开头的数字
        def prefixNum(txt):
            match = re.search(r'^(\d+)', txt)
            return int(match.group(1)) if match else 0

        dateDir = os.path.join(oebDir, user.name, user.local_time('%Y-%m-%d'))
        maxIdx = max([prefixNum(item) for item in os.listdir(dateDir)] + [0]) if os.path.exists(dateDir) else 0
        title = oeb.metadata.title[0].value or 'Untitled'
        title = ascii_filename(title).replace(' ', '_')
        bookDir = os.path.join(dateDir, f'{maxIdx + 1:03}_{title}')
        
        try:
            os.makedirs(bookDir)
        except Exception as e:
            self.log.warning(f'Failed to save eBook due to dir creation error: {bookDir}: {e}')
            return

        self.dump_oeb(self.oeb, bookDir)
        size = get_directory_size(bookDir)
        save_delivery_log(user, title, size, status='ok', to=oebDir)

regex_wizard_callback = None
def set_regex_wizard_callback(f):
    global regex_wizard_callback
    regex_wizard_callback = f


#从一堆文件里面创建OEBBook实例
#fs: FsDictStub对象，其opfname属性为opf文件的路径全名
def create_oebbook(log, fs, opts, reader=None,
        encoding='utf-8', populate=True, specialize=None, removed_items=()):
    '''
    Create an OEBBook.
    '''
    from calibre.ebooks.oeb.base import OEBBook
    html_preprocessor = HTMLPreProcessor(log, opts, regex_wizard_callback=regex_wizard_callback)
    if not encoding:
        encoding = None
    oeb = OEBBook(log, html_preprocessor, pretty_print=opts.pretty_print, input_encoding=encoding)
    if not populate:
        return oeb
    if specialize is not None:
        oeb = specialize(oeb) or oeb
    # Read OEB Book into OEBBook
    log.debug('Parsing all content...')
    oeb.removed_items_to_ignore = removed_items
    if reader is None:
        from calibre.ebooks.oeb.reader import OEBReader
        reader = OEBReader

    reader()(oeb, fs)
    return oeb


def create_dummy_plumber(input_format, output_format):
    input_format = input_format.lower()
    output_format = output_format.lower()
    output_path = 'dummy.'+output_format
    log = default_log
    log.outputs = []
    input_file = 'dummy.'+input_format
    if input_format in ARCHIVE_FMTS:
        input_file = 'dummy.html'
    return Plumber(input_file, output_path, log)

#提供给Plumber的一些选项
_pipeline_options = [
OptionRecommendation(name='verbose',
            recommended_value=0, level=OptionRecommendation.LOW,
            short_switch='v',
            help=_('Level of verbosity. Specify multiple times for greater '
                   'verbosity. Specifying it twice will result in full '
                   'verbosity, once medium verbosity and zero times least verbosity.')
        ),

OptionRecommendation(name='debug_pipeline',
            recommended_value=None, level=OptionRecommendation.LOW,
            short_switch='d',
            help=_('Save the output from different stages of the conversion '
                   'pipeline to the specified '
                   'folder. Useful if you are unsure at which stage '
                   'of the conversion process a bug is occurring.')
        ),

OptionRecommendation(name='input_profile',
            recommended_value='default', level=OptionRecommendation.LOW,
            choices=[x.short_name for x in input_profiles()],
            help=_('Specify the input profile. The input profile gives the '
                   'conversion system information on how to interpret '
                   'various information in the input document. For '
                   'example resolution dependent lengths (i.e. lengths in '
                   'pixels). Choices are:') + ' ' + ', '.join([
                       x.short_name for x in input_profiles()])
        ),

OptionRecommendation(name='output_profile',
            recommended_value='default', level=OptionRecommendation.LOW,
            choices=[x.short_name for x in output_profiles()],
            help=_('Specify the output profile. The output profile '
                   'tells the conversion system how to optimize the '
                   'created document for the specified device. In some cases, '
                   'an output profile can be used to optimize the output for a particular device, but this is rarely necessary. '
                   'Choices are:') + ', '.join([
                       x.short_name for x in output_profiles()])
        ),

OptionRecommendation(name='base_font_size',
            recommended_value=0, level=OptionRecommendation.LOW,
            help=_('The base font size in pts. All font sizes in the produced book '
                   'will be rescaled based on this size. By choosing a larger '
                   'size you can make the fonts in the output bigger and vice '
                   'versa. By default, when the value is zero, the base font size is chosen based on '
                   'the output profile you chose.'
                   )
        ),

OptionRecommendation(name='font_size_mapping',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('Mapping from CSS font names to font sizes in pts. '
                   'An example setting is 12,12,14,16,18,20,22,24. '
                   'These are the mappings for the sizes xx-small to xx-large, '
                   'with the final size being for huge fonts. The font '
                   'rescaling algorithm uses these sizes to intelligently '
                   'rescale fonts. The default is to use a mapping based on '
                   'the output profile you chose.'
                   )
        ),

OptionRecommendation(name='disable_font_rescaling',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Disable all rescaling of font sizes.'
                   )
        ),

OptionRecommendation(name='minimum_line_height',
            recommended_value=120.0, level=OptionRecommendation.LOW,
            help=_(
            'The minimum line height, as a percentage of the element\'s '
            'calculated font size. calibre will ensure that every element '
            'has a line height of at least this setting, irrespective of '
            'what the input document specifies. Set to zero to disable. '
            'Default is 120%. Use this setting in preference to '
            'the direct line height specification, unless you know what '
            'you are doing. For example, you can achieve "double spaced" '
            'text by setting this to 240.'
            )
        ),


OptionRecommendation(name='line_height',
            recommended_value=0, level=OptionRecommendation.LOW,
            help=_(
            'The line height in pts. Controls spacing between consecutive '
            'lines of text. Only applies to elements that do not define '
            'their own line height. In most cases, the minimum line height '
            'option is more useful. '
            'By default no line height manipulation is performed.'
            )
        ),

OptionRecommendation(name='embed_font_family',
        recommended_value=None, level=OptionRecommendation.LOW,
        help=_(
            'Embed the specified font family into the book. This specifies '
            'the "base" font used for the book. If the input document '
            'specifies its own fonts, they may override this base font. '
            'You can use the filter style information option to remove fonts from the '
            'input document. Note that font embedding only works '
            'with some output formats, principally EPUB, AZW3 and DOCX.')
        ),

OptionRecommendation(name='embed_all_fonts',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_(
            'Embed every font that is referenced in the input document '
            'but not already embedded. This will search your system for the '
            'fonts, and if found, they will be embedded. Embedding will only work '
            'if the format you are converting to supports embedded fonts, such as '
            'EPUB, AZW3, DOCX or PDF. Please ensure that you have the proper license for embedding '
            'the fonts used in this document.'
        )),

OptionRecommendation(name='subset_embedded_fonts',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_(
            'Subset all embedded fonts. Every embedded font is reduced '
            'to contain only the glyphs used in this document. This decreases '
            'the size of the font files. Useful if you are embedding a '
            'particularly large font with lots of unused glyphs.')
        ),

OptionRecommendation(name='linearize_tables',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Some badly designed documents use tables to control the '
                'layout of text on the page. When converted these documents '
                'often have text that runs off the page and other artifacts. '
                'This option will extract the content from the tables and '
                'present it in a linear fashion.'
                )
        ),

OptionRecommendation(name='level1_toc',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('XPath expression that specifies all tags that '
            'should be added to the Table of Contents at level one. If '
            'this is specified, it takes precedence over other forms '
            'of auto-detection.'
            ' See the XPath Tutorial in the calibre User Manual for examples.'
                )
        ),

OptionRecommendation(name='level2_toc',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('XPath expression that specifies all tags that should be '
            'added to the Table of Contents at level two. Each entry is added '
            'under the previous level one entry.'
            ' See the XPath Tutorial in the calibre User Manual for examples.'
                )
        ),

OptionRecommendation(name='level3_toc',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('XPath expression that specifies all tags that should be '
            'added to the Table of Contents at level three. Each entry '
            'is added under the previous level two entry.'
            ' See the XPath Tutorial in the calibre User Manual for examples.'
                )
        ),

OptionRecommendation(name='use_auto_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Normally, if the source file already has a Table of '
            'Contents, it is used in preference to the auto-generated one. '
            'With this option, the auto-generated one is always used.'
                )
        ),

OptionRecommendation(name='no_chapters_in_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_("Don't add auto-detected chapters to the Table of "
            'Contents.'
                )
        ),

OptionRecommendation(name='toc_threshold',
            recommended_value=6, level=OptionRecommendation.LOW,
            help=_(
        'If fewer than this number of chapters is detected, then links '
        'are added to the Table of Contents. Default: %default')
        ),

OptionRecommendation(name='max_toc_links',
            recommended_value=50, level=OptionRecommendation.LOW,
            help=_('Maximum number of links to insert into the TOC. Set to 0 '
                'to disable. Default is: %default. Links are only added to the '
                'TOC if less than the threshold number of chapters were detected.'
                )
        ),

OptionRecommendation(name='toc_filter',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('Remove entries from the Table of Contents whose titles '
            'match the specified regular expression. Matching entries and all '
            'their children are removed.'
                )
        ),

OptionRecommendation(name='duplicate_links_in_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('When creating a TOC from links in the input document, '
                'allow duplicate entries, i.e. allow more than one entry '
                'with the same text, provided that they point to a '
                'different location.')
        ),


OptionRecommendation(name='chapter',
        recommended_value="//*[((name()='h1' or name()='h2') and "
              r"re:test(., '\s*((chapter|book|section|part)\s+)|((prolog|prologue|epilogue)(\s+|$))', 'i')) or @class "
              "= 'chapter']", level=OptionRecommendation.LOW,
            help=_('An XPath expression to detect chapter titles. The default '
                'is to consider <h1> or <h2> tags that contain the words '
                '"chapter", "book", "section", "prologue", "epilogue" or "part" as chapter titles as '
                'well as any tags that have class="chapter". The expression '
                'used must evaluate to a list of elements. To disable chapter '
                'detection, use the expression "/". See the XPath Tutorial '
                'in the calibre User Manual for further help on using this '
                'feature.'
                )
        ),

OptionRecommendation(name='chapter_mark',
            recommended_value='pagebreak', level=OptionRecommendation.LOW,
            choices=['pagebreak', 'rule', 'both', 'none'],
            help=_('Specify how to mark detected chapters. A value of '
                    '"pagebreak" will insert page breaks before chapters. '
                    'A value of "rule" will insert a line before chapters. '
                    'A value of "none" will disable chapter marking and a '
                    'value of "both" will use both page breaks and lines '
                    'to mark chapters.')
        ),

OptionRecommendation(name='start_reading_at',
        recommended_value=None, level=OptionRecommendation.LOW,
        help=_('An XPath expression to detect the location in the document'
            ' at which to start reading. Some e-book reading programs'
            ' (most prominently the Kindle) use this location as the'
            ' position at which to open the book. See the XPath tutorial'
            ' in the calibre User Manual for further help using this'
            ' feature.')
        ),

OptionRecommendation(name='extra_css',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('Either the path to a CSS stylesheet or raw CSS. '
                'This CSS will be appended to the style rules from '
                'the source file, so it can be used to override those '
                'rules.')
        ),

OptionRecommendation(name='transform_css_rules',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('Rules for transforming the styles in this book. These'
                   ' rules are applied after all other CSS processing is done.')
        ),

OptionRecommendation(name='transform_html_rules',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('Rules for transforming the HTML in this book. These'
                   ' rules are applied after the HTML is parsed, but before any other transformations.')
        ),

OptionRecommendation(name='filter_css',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('A comma separated list of CSS properties that '
                'will be removed from all CSS style rules. This is useful '
                'if the presence of some style information prevents it '
                'from being overridden on your device. '
                'For example: '
                'font-family,color,margin-left,margin-right')
        ),

OptionRecommendation(name='expand_css',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_(
                'By default, calibre will use the shorthand form for various'
                ' CSS properties such as margin, padding, border, etc. This'
                ' option will cause it to use the full expanded form instead.'
                ' Note that CSS is always expanded when generating EPUB files'
                ' with the output profile set to one of the Nook profiles'
                ' as the Nook cannot handle shorthand CSS.')
        ),

OptionRecommendation(name='page_breaks_before',
            #commented by cdhigh
            #recommended_value="//*[name()='h1' or name()='h2']",
            recommended_value=None,
            level=OptionRecommendation.LOW,
            help=_('An XPath expression. Page breaks are inserted '
                'before the specified elements. To disable use the expression: /')
        ),

OptionRecommendation(name='remove_fake_margins',
            recommended_value=True, level=OptionRecommendation.LOW,
            help=_('Some documents specify page margins by '
                'specifying a left and right margin on each individual '
                'paragraph. calibre will try to detect and remove these '
                'margins. Sometimes, this can cause the removal of '
                'margins that should not have been removed. In this '
                'case you can disable the removal.')
        ),


OptionRecommendation(name='margin_top',
        recommended_value=5.0, level=OptionRecommendation.LOW,
        help=_('Set the top margin in pts. Default is %default. '
            'Setting this to less than zero will cause no margin to be set '
            '(the margin setting in the original document will be preserved). '
            'Note: Page oriented formats such as PDF and DOCX have their own'
            ' margin settings that take precedence.')),

OptionRecommendation(name='margin_bottom',
        recommended_value=5.0, level=OptionRecommendation.LOW,
        help=_('Set the bottom margin in pts. Default is %default. '
            'Setting this to less than zero will cause no margin to be set '
            '(the margin setting in the original document will be preserved). '
            'Note: Page oriented formats such as PDF and DOCX have their own'
            ' margin settings that take precedence.')),

OptionRecommendation(name='margin_left',
        recommended_value=5.0, level=OptionRecommendation.LOW,
        help=_('Set the left margin in pts. Default is %default. '
            'Setting this to less than zero will cause no margin to be set '
            '(the margin setting in the original document will be preserved). '
            'Note: Page oriented formats such as PDF and DOCX have their own'
            ' margin settings that take precedence.')),

OptionRecommendation(name='margin_right',
        recommended_value=5.0, level=OptionRecommendation.LOW,
        help=_('Set the right margin in pts. Default is %default. '
            'Setting this to less than zero will cause no margin to be set '
            '(the margin setting in the original document will be preserved). '
            'Note: Page oriented formats such as PDF and DOCX have their own'
            ' margin settings that take precedence.')),

OptionRecommendation(name='change_justification',
        recommended_value='original', level=OptionRecommendation.LOW,
        choices=['left','justify','original'],
        help=_('Change text justification. A value of "left" converts all'
            ' justified text in the source to left aligned (i.e. '
            'unjustified) text. A value of "justify" converts all '
            'unjustified text to justified. A value of "original" '
            '(the default) does not change justification in the '
            'source file. Note that only some output formats support '
            'justification.')),

OptionRecommendation(name='remove_paragraph_spacing',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Remove spacing between paragraphs. Also sets an indent on '
        'paragraphs of 1.5em. Spacing removal will not work '
        'if the source file does not use paragraphs (<p> or <div> tags).')
        ),

OptionRecommendation(name='remove_paragraph_spacing_indent_size',
        recommended_value=1.5, level=OptionRecommendation.LOW,
        help=_('When calibre removes blank lines between paragraphs, it automatically '
            'sets a paragraph indent, to ensure that paragraphs can be easily '
            'distinguished. This option controls the width of that indent (in em). '
            'If you set this value negative, then the indent specified in the input '
            'document is used, that is, calibre does not change the indentation.')
        ),

OptionRecommendation(name='prefer_metadata_cover',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Use the cover detected from the source file in preference '
        'to the specified cover.')
        ),

OptionRecommendation(name='insert_blank_line',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Insert a blank line between paragraphs. Will not work '
            'if the source file does not use paragraphs (<p> or <div> tags).'
            )
        ),

OptionRecommendation(name='insert_blank_line_size',
        recommended_value=0.5, level=OptionRecommendation.LOW,
        help=_('Set the height of the inserted blank lines (in em).'
            ' The height of the lines between paragraphs will be twice the value'
            ' set here.')
        ),

OptionRecommendation(name='remove_first_image',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Remove the first image from the input e-book. Useful if the '
        'input document has a cover image that is not identified as a cover. '
        'In this case, if you set a cover in calibre, the output document will '
        'end up with two cover images if you do not specify this option.'
            )
        ),

OptionRecommendation(name='insert_metadata',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Insert the book metadata at the start of '
            'the book. This is useful if your e-book reader does not support '
            'displaying/searching metadata directly.'
            )
        ),

OptionRecommendation(name='smarten_punctuation',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Convert plain quotes, dashes and ellipsis to their '
            'typographically correct equivalents. For details, see '
            'https://daringfireball.net/projects/smartypants.'
            )
        ),

OptionRecommendation(name='unsmarten_punctuation',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Convert fancy quotes, dashes and ellipsis to their '
               'plain equivalents.'
            )
        ),

OptionRecommendation(name='read_metadata_from_opf',
            recommended_value=None, level=OptionRecommendation.LOW,
            short_switch='m',
            help=_('Read metadata from the specified OPF file. Metadata read '
                   'from this file will override any metadata in the source '
                   'file.')
        ),

OptionRecommendation(name='asciiize',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=(_('Transliterate Unicode characters to an ASCII '
            'representation. Use with care because this will replace '
            'Unicode characters with ASCII. For instance it will replace "{0}" '
            'with "{1}". Also, note that in '
            'cases where there are multiple representations of a character '
            '(characters shared by Chinese and Japanese for instance) the '
            'representation based on the current calibre interface language will be '
            'used.').format('Pelé', 'Pele'))
        ),

OptionRecommendation(name='keep_ligatures',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Preserve ligatures present in the input document. '
                'A ligature is a special rendering of a pair of '
                'characters like ff, fi, fl et cetera. '
                'Most readers do not have support for '
                'ligatures in their default fonts, so they are '
                'unlikely to render correctly. By default, calibre '
                'will turn a ligature into the corresponding pair of normal '
                'characters. This option will preserve them instead.')
        ),

OptionRecommendation(name='title',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the title.')),

OptionRecommendation(name='authors',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the authors. Multiple authors should be separated by '
    'ampersands.')),

OptionRecommendation(name='title_sort',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('The version of the title to be used for sorting. ')),

OptionRecommendation(name='author_sort',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('String to be used when sorting by author. ')),

OptionRecommendation(name='cover',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the cover to the specified file or URL')),

OptionRecommendation(name='comments',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the e-book description.')),

OptionRecommendation(name='publisher',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the e-book publisher.')),

OptionRecommendation(name='series',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the series this e-book belongs to.')),

OptionRecommendation(name='series_index',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the index of the book in this series.')),

OptionRecommendation(name='rating',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the rating. Should be a number between 1 and 5.')),

OptionRecommendation(name='isbn',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the ISBN of the book.')),

OptionRecommendation(name='tags',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the tags for the book. Should be a comma separated list.')),

OptionRecommendation(name='book_producer',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the book producer.')),

OptionRecommendation(name='language',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the language.')),

OptionRecommendation(name='pubdate',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the publication date (assumed to be in the local timezone, unless the timezone is explicitly specified)')),

OptionRecommendation(name='timestamp',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the book timestamp (no longer used anywhere)')),

OptionRecommendation(name='enable_heuristics',
    recommended_value=False, level=OptionRecommendation.LOW,
    help=_('Enable heuristic processing. This option must be set for any '
           'heuristic processing to take place.')),

OptionRecommendation(name='markup_chapter_headings',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Detect unformatted chapter headings and sub headings. Change '
           'them to h2 and h3 tags.  This setting will not create a TOC, '
           'but can be used in conjunction with structure detection to create '
           'one.')),

OptionRecommendation(name='italicize_common_cases',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Look for common words and patterns that denote '
           'italics and italicize them.')),

OptionRecommendation(name='fix_indents',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Turn indentation created from multiple non-breaking space entities '
           'into CSS indents.')),

OptionRecommendation(name='html_unwrap_factor',
    recommended_value=0.40, level=OptionRecommendation.LOW,
    help=_('Scale used to determine the length at which a line should '
            'be unwrapped. Valid values are a decimal between 0 and 1. The '
            'default is 0.4, just below the median line length.  If only a '
            'few lines in the document require unwrapping this value should '
            'be reduced')),

OptionRecommendation(name='unwrap_lines',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Unwrap lines using punctuation and other formatting clues.')),

OptionRecommendation(name='delete_blank_paragraphs',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Remove empty paragraphs from the document when they exist between '
           'every other paragraph')),

OptionRecommendation(name='format_scene_breaks',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Left aligned scene break markers are center aligned. '
           'Replace soft scene breaks that use multiple blank lines with '
           'horizontal rules.')),

OptionRecommendation(name='replace_scene_breaks',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Replace scene breaks with the specified text. By default, the '
        'text from the input document is used.')),

OptionRecommendation(name='dehyphenate',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Analyze hyphenated words throughout the document.  The '
           'document itself is used as a dictionary to determine whether hyphens '
           'should be retained or removed.')),

OptionRecommendation(name='renumber_headings',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Looks for occurrences of sequential <h1> or <h2> tags. '
           'The tags are renumbered to prevent splitting in the middle '
           'of chapter headings.')),

OptionRecommendation(name='sr1_search',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Search pattern (regular expression) to be replaced with '
           'sr1-replace.')),

OptionRecommendation(name='sr1_replace',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Replacement to replace the text found with sr1-search.')),

OptionRecommendation(name='sr2_search',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Search pattern (regular expression) to be replaced with '
           'sr2-replace.')),

OptionRecommendation(name='sr2_replace',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Replacement to replace the text found with sr2-search.')),

OptionRecommendation(name='sr3_search',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Search pattern (regular expression) to be replaced with '
           'sr3-replace.')),

OptionRecommendation(name='sr3_replace',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Replacement to replace the text found with sr3-search.')),

OptionRecommendation(name='search_replace',
    recommended_value=None, level=OptionRecommendation.LOW, help=_(
        'Path to a file containing search and replace regular expressions. '
        'The file must contain alternating lines of regular expression '
        'followed by replacement pattern (which can be an empty line). '
        'The regular expression must be in the Python regex syntax and '
        'the file must be UTF-8 encoded.')),
]
