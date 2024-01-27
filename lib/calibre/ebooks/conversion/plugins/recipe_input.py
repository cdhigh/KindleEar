#!/usr/bin/env python3
# -*- coding:utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, io

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.constants import numeric_version
from calibre import walk

class RecipeDisabled(Exception):
    pass

def report_progress(progress, message=None):
    pass

class RecipeInput(InputFormatPlugin):

    name        = 'Recipe Input'
    author      = 'Kovid Goyal'
    description = _('Download periodical content from the Internet')
    file_types  = {'recipe', 'downloaded_recipe'}
    commit_name = 'recipe_input'

    recommendations = {
        ('chapter', None, OptionRecommendation.HIGH),
        ('dont_split_on_page_breaks', True, OptionRecommendation.HIGH),
        ('use_auto_toc', False, OptionRecommendation.HIGH),
        ('input_encoding', None, OptionRecommendation.HIGH),
        ('input_profile', 'default', OptionRecommendation.HIGH),
        ('page_breaks_before', None, OptionRecommendation.HIGH),
        ('insert_metadata', False, OptionRecommendation.HIGH),
        }

    options = {
        OptionRecommendation(name='test', recommended_value=False,
            help=_(
            'Useful for recipe development. Forces'
            ' max_articles_per_feed to 2 and downloads at most 2 feeds.'
            ' You can change the number of feeds and articles by supplying optional arguments.'
            ' For example: --test 3 1 will download at most 3 feeds and only 1 article per feed.')),
        OptionRecommendation(name='username', recommended_value=None,
            help=_('Username for sites that require a login to access '
                'content.')),
        OptionRecommendation(name='password', recommended_value=None,
            help=_('Password for sites that require a login to access '
                'content.')),
        OptionRecommendation(name='dont_download_recipe',
            recommended_value=False,
            help=_('Do not download latest version of builtin recipes from the calibre server')),
        OptionRecommendation(name='lrf', recommended_value=False,
            help='Optimize fetching for subsequent conversion to LRF.'),
        }

    #执行转换完成后返回生成的 opf 文件路径，只是路径，不包含文件名
    #recipe_or_file: 可以为文件名, BytesIO, BasicNewsRecipe
    #output_dir: 输出目录
    #fs: plumber生成的FsDictStub实例
    #返回 opf文件的全路径名或传入的fs实例
    def convert(self, recipe_or_file, opts, file_ext, log, accelerators, output_dir, fs):
        from calibre.web.feeds.recipes import compile_recipe
        from calibre.web.feeds.news import BasicNewsRecipe
        opts.output_profile.flow_size = 0
        orig_no_inline_navbars = opts.no_inline_navbars
        if not isinstance(recipe_or_file, BasicNewsRecipe):
            if isinstance(recipe_or_file, io.BytesIO):
                self.recipe_source = recipe_source.getvalue()
            else:
                with open(recipe_or_file, 'rb') as f:
                    self.recipe_source = f.read()
            try:
                recipe = compile_recipe(self.recipe_source)
            except Exception as e:
                raise ValueError('Failed to compile recipe "{}": {}'.format(recipe_or_file, e))
        else:
            recipe = recipe_or_file
            
        #try:
        #生成 BasicNewsRecipe 对象并执行下载任务
        ro = recipe(opts, log, report_progress, output_dir, fs)
        ro.download()
        #except Exception as e:
        #    raise ValueError('Failed to execute recipe "{}": {}'.format(recipe_or_file, e))
        
        self.recipe_object = ro
        for key, val in self.recipe_object.conversion_options.items():
            setattr(opts, key, val)
        opts.no_inline_navbars = orig_no_inline_navbars
        
        fs.find_opf_path()
        return fs
        
    def postprocess_book(self, oeb, opts, log):
        if self.recipe_object is not None:
            self.recipe_object.internal_postprocess_book(oeb, opts, log)
            self.recipe_object.postprocess_book(oeb, opts, log)

    def specialize(self, oeb, opts, log, output_fmt):
        if opts.no_inline_navbars:
            from calibre.ebooks.oeb.base import XPath
            for item in oeb.spine:
                for div in XPath('//h:div[contains(@class, "calibre_navbar")]')(item.data):
                    div.getparent().remove(div)

    def save_download(self, zf):
        return
        raw = self.recipe_source
        if isinstance(raw, str):
            raw = raw.encode('utf-8')
        zf.writestr('download.recipe', raw)
