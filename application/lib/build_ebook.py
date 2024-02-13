#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#从recipe生成对应的输出格式
#Author: cdhigh <https://github.com/cdhigh>
import io, os
from calibre.ebooks.conversion.plumber import Plumber, create_oebbook
from calibre.web.feeds.recipes import compile_recipe
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.ebooks.metadata.toc import TOC
from recipe_helper import GenerateRecipeSource

#从输入格式生成对应的输出格式
#recipes: 编译后的recipe，为一个列表
#user: KeUser对象
#output_fmt: 如果指定，则生成特定格式的书籍，否则使用user.book_type
#options: 额外的一些参数，为一个字典
# 如: options={'debug_pipeline': path, 'verbose': 1}
#返回电子书二进制内容
def recipes_to_ebook(recipes: list, user, options: dict=None, output_fmt: str=None):
    if not isinstance(recipes, list):
        recipes = [recipes]
    output = io.BytesIO()
    output_fmt=output_fmt if output_fmt else user.book_type
    plumber = Plumber(recipes, output, input_fmt='recipe', output_fmt=output_fmt)
    plumber.merge_ui_recommendations(ke_opts(user, options))
    plumber.run()
    return output.getvalue()

#仅通过一个url列表构建一本电子书
#urls: [(title, url),...]
#user: KeUser对象
#output_fmt: 如果指定，则生成特定格式的书籍，否则使用user.book_type
#options: 额外的一些参数，为一个字典
def urls_to_book(urls: list, title: str, user, options: dict=None, output_fmt: str=None):
    feeds = [(title, url) for url in urls]
    src = GenerateRecipeSource(title, feeds, user)
    try:
        ro = compile_recipe(src)
    except Exception as e:
        default_log.warning('Failed to compile recipe {}: {}'.format(title, e))
        return None

    #合并自定义css
    ro.extra_css = user.get_extra_css(ro.extra_css)

    return recipes_to_ebook(ro, user, options, output_fmt)

#将一个html文件和其图像内容转换为一本电子书，返回电子书二进制内容，格式为user.book_type
def html_to_book(html: str, title: str, imgs: list, user, options: dict=None, output_fmt: str=None):
    input_ = {'html': html, 'imgs': imgs, 'title': title}
    output = io.BytesIO()
    output_fmt=output_fmt if output_fmt else user.book_type
    plumber = Plumber(input_, output, input_fmt='html', output_fmt=output_fmt)
    plumber.merge_ui_recommendations(ke_opts(user, options))
    plumber.run()
    return output.getvalue()

#获取KindleEar定制的电子书转换参数
def ke_opts(user, options=None):
    options = options or {}
    options.setdefault('output_profile', user.device)
    options.setdefault('input_profile', 'kindle')
    options.setdefault('no_inline_toc', False)
    options.setdefault('epub_inline_toc', True)
    options.setdefault('dont_compress', True)
    options.setdefault('dont_split_on_page_breaks', True)
    options['user'] = user

    options.setdefault('debug_pipeline', os.getenv('TEMP_DIR'))
    options.setdefault('verbose', 1)
    options.setdefault('test', 1)
    return options

