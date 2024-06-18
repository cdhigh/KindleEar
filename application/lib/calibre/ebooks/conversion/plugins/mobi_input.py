__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks import DRMError

class MOBIInput(InputFormatPlugin):

    name        = 'MOBI Input'
    author      = 'Kovid Goyal'
    description = _('Convert MOBI files (.mobi, .prc, .azw) to HTML')
    file_types  = {'mobi', 'prc', 'azw', 'azw3', 'pobi'}
    commit_name = 'mobi_input'

    #执行转换完成后返回生成的 opf 文件路径，只是路径，不包含文件名
    #recipes: 可以为文件名, StringIO, 或一个列表
    #output_dir: 输出目录
    #fs: plumber生成的FsDictStub实例
    #返回 opf文件的全路径名或传入的fs实例
    def convert(self, stream, opts, file_ext, log, output_dir, fs):
        self.user = opts.user
        self.is_kf8 = False
        self.mobi_is_joint = False

        from calibre.ebooks.mobi.reader.mobi6 import MobiReader
        from lxml import html
        parse_cache = {}
        try:
            mr = MobiReader(stream, log, opts.input_encoding, opts.debug_pipeline, fs=fs)
            if mr.kf8_type is None:
                mr.extract_content(output_dir, parse_cache)
        except DRMError:
            raise
        except:
            mr = MobiReader(stream, log, opts.input_encoding,
                        opts.debug_pipeline, try_extra_data_fix=True, fs=fs)
            if mr.kf8_type is None:
                mr.extract_content(output_dir, parse_cache)

        if mr.kf8_type is not None:
            log('Found KF8 MOBI of type %r'%mr.kf8_type)
            if mr.kf8_type == 'joint':
                self.mobi_is_joint = True
            from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
            mr = Mobi8Reader(mr, log, fs=fs)
            opf = mr(output_dir)
            self.encrypted_fonts = mr.encrypted_fonts
            self.is_kf8 = True
            return opf

        raw = parse_cache.pop('calibre_raw_mobi_markup', False)
        if raw:
            if isinstance(raw, str):
                raw = raw.encode('utf-8')
            fs.write(os.path.join(output_dir, 'debug-raw.html'), raw, 'wb')
        from calibre.ebooks.oeb.base import close_self_closing_tags
        for f, root in parse_cache.items():
            raw = html.tostring(root, encoding='utf-8', method='xml',
                    include_meta_content_type=False)
            raw = close_self_closing_tags(raw)
            fs.write(os.path.join(output_dir, f), raw, 'wb')
        #accelerators['pagebreaks'] = '//h:div[@class="mbp_pagebreak"]'
        return fs if fs else mr.created_opf_path
