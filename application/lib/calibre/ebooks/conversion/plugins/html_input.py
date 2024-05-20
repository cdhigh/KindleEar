#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, io, datetime
from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.ebooks.metadata.toc import TOC

class HTMLInput(InputFormatPlugin):
    name        = 'HTML Input'
    author      = 'Kovid Goyal'
    description = _('Convert HTML and OPF files to an OEB')
    file_types  = {'opf', 'html', 'htm', 'xhtml', 'xhtm', 'shtm', 'shtml'}
    commit_name = 'html_input'
    
    options = {
        OptionRecommendation(name='breadth_first',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Traverse links in HTML files breadth first. Normally, '
                    'they are traversed depth first.'
                   )
        ),

        OptionRecommendation(name='max_levels',
            recommended_value=5, level=OptionRecommendation.LOW,
            help=_('Maximum levels of recursion when following links in '
                   'HTML files. Must be non-negative. 0 implies that no '
                   'links in the root HTML file are followed. Default is '
                   '%default.'
                   )
        ),

        OptionRecommendation(name='dont_package',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Normally this input plugin re-arranges all the input '
                'files into a standard folder hierarchy. Only use this option '
                'if you know what you are doing as it can result in various '
                'nasty side effects in the rest of the conversion pipeline.'
                )
        ),

        OptionRecommendation(name='allow_local_files_outside_root',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Normally, resources linked to by the HTML file or its children will only be allowed'
                   ' if they are in a sub-folder of the original HTML file. This option allows including'
                   ' local files from any location on your computer. This can be a security risk if you'
                   ' are converting untrusted HTML and expecting to distribute the result of the conversion.'
                )
        ),


    }

    #执行转换完成后返回生成的 opf 文件路径，只是路径，不包含文件名
    #input_: 输入html和相关图像的一个字典 {'html':, 'title':, 'imgs':[(filename, content),...]}
    #output_dir: 输出目录
    #fs: plumber生成的FsDictStub实例
    #返回 opf文件的全路径名或传入的fs实例
    def convert(self, input_, opts, file_ext, log, output_dir, fs):
        user = opts.user
        fs.write('/index.html', input_.get('html', ''))
        title = input_.get('title', 'KindleEar')
        mi = MetaInformation(title, ['KindleEar'])
        mi.publisher = 'KindleEar'
        mi.author_sort = 'KindleEar'
        mi.authors = ['KindleEar']
        mi.publication_type = f'book:book:{title}'
        mi.timestamp = user.local_time()
        mi.language = input_.get('language') or user.book_cfg('language')
        opf = OPFCreator(fs.path, mi, fs)
        
        #manifest 资源列表
        manifest = ['/index.html']
        for fileName, content in (input_.get('imgs', None) or []):
            fileName = os.path.join(fs.path, fileName)
            fs.write(fileName, content)
            manifest.append(fileName)
        opf.create_manifest_from_files_in(manifest)
        ncx_id = opf.manifest.add_item(os.path.join(fs.path, 'index.ncx'), mime_type="application/x-dtbncx+xml")
        opf.manifest.item(ncx_id).id = 'ncx'

        toc = TOC(base_path=fs.path)
        toc.add_item('/index.html', None, title, play_order=1, author='KindleEar', description='KindleEar', toc_thumbnail=None)
        opf.create_spine(['/index.html'])
        opf.set_toc(toc)

        opf_file = io.BytesIO()
        ncx_file = io.BytesIO()
        opf.render(opf_file, ncx_file)
        fs.write('/index.opf', opf_file.getvalue())
        fs.write('/index.ncx', ncx_file.getvalue())
        fs.find_opf_path()
        return fs
