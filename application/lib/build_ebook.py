#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#从recipe生成对应的输出格式
#Author: cdhigh <https://github.com/cdhigh>
import io, os, re
import clogging
from calibre.ptempfile import PersistentTemporaryFile
from calibre.ebooks.conversion.plumber import Plumber
from calibre.web.feeds.recipes import compile_recipe
from recipe_helper import GenerateRecipeSource
from urlopener import UrlOpener
from application.utils import loc_exc_pos

#从输入格式生成对应的输出格式
#input_: 如果是recipe，为编译后的recipe(或列表)，或者是一个输入文件名，或一个BytesIO
#input_fmt: 输入格式， recipe, mobi, ...
#user: KeUser对象
#output_fmt: 如果指定，则生成特定格式的书籍，否则使用user.book_cfg('type')
#options: 额外的一些参数，为一个字典
# 如: options={'debug_pipeline': path, 'verbose': 1}
#返回电子书二进制内容
def convert_book(input_, input_fmt, user, options=None, output_fmt=''):
    output = io.BytesIO()
    output_fmt = output_fmt if output_fmt else user.book_cfg('type')
    options = ke_opts(user, options)
    plumber = Plumber(input_, output, input_fmt=input_fmt, output_fmt=output_fmt, options=options)
    try:
        plumber.run()
        return output.getvalue()
    except:
        default_log.warning(loc_exc_pos('convert_book failed'))
        return b''
    
#仅通过一个url列表构建一本电子书
#urls: [(title, url),...] or [url,url,...]
#title: 书籍标题
#user: KeUser对象
#output_fmt: 如果指定，则生成特定格式的书籍，否则使用 user.book_cfg('type')
#options: 额外的一些参数，为一个字典
def urls_to_book(urls: list, title: str, user, options=None, output_fmt='', language=''):
    #提前下载html，获取其title
    sysTmpDir = os.environ.get('KE_TEMP_DIR')
    prevDownloads = []
    def clearPrevDownloads(): #退出时清理临时文件
        for item in prevDownloads:
            try:
                os.remove(item)
            except Exception as e:
                print(f'Delete failed: {item}: {e}')
                pass

    for idx, url in enumerate(urls[:]):
        if not sysTmpDir or not isinstance(url, str): #如果没有使用临时目录则无法提取下载
            urls[idx] = (title, url) if isinstance(url, str) else url
            continue

        resp = UrlOpener().open(url)
        if resp.status_code != 200:
            urls[idx] = (title, url)
            continue

        with PersistentTemporaryFile(suffix='.html', dir=sysTmpDir) as pt:
            prevDownloads.append(pt.name)
            try:
                pt.write(resp.content)
            except Exception as e:
                urls[idx] = (title, url)
                default_log.warning(f'Prev download html failed: {url}: {e}')
            else: #提取标题
                match = re.search(r'<title[^>]*>(.*?)</title>', resp.text, re.I|re.M|re.S)
                uTitle = match.group(1).strip() if match else title
                urls[idx] = (uTitle, 'file://' + pt.name)

    src = GenerateRecipeSource(title, urls, user, base='UrlNewsRecipe', max_articles=100, 
        cover_url=False, language=language)
    try:
        ro = compile_recipe(src)
    except Exception as e:
        default_log.warning('Failed to compile recipe {}: {}'.format(title, e))
        clearPrevDownloads()
        return None
    if not ro:
        default_log.warning('Failed to compile recipe {}: {}'.format(title, 'Cannot find any subclass of BasicNewsRecipe.'))
        clearPrevDownloads()
        return None
        
    #合并自定义css
    userCss = user.get_extra_css()
    ro.extra_css = f'{ro.extra_css}\n\n{userCss}' if ro.extra_css else userCss #type:ignore

    book = convert_book(ro, 'recipe', user, options, output_fmt)
    clearPrevDownloads()
    return book

#将一个html文件和其图像内容转换为一本电子书，返回电子书二进制内容，格式为user.book_cfg('type')
#html: html文本内容
#title: 书籍标题
#user: KeUser实例
#imgs: 图像内容列表，[(fileName, content), ...]
#options: 电子书制作的额外参数
#output_fmt: 输出格式，这个参数会覆盖user的原本设置
def html_to_book(html: str, title: str, user, imgs=None, options=None, output_fmt='', language=''):
    input_ = {'html': html, 'imgs': imgs, 'title': title, 'language': language}
    output = io.BytesIO()
    output_fmt = output_fmt if output_fmt else user.book_cfg('type')
    options = ke_opts(user, options)
    plumber = Plumber(input_, output, input_fmt='html', output_fmt=output_fmt, options=options)
    plumber.run()
    return output.getvalue()

#获取KindleEar定制的电子书转换参数
def ke_opts(user, options=None):
    opt = user.custom.get('calibre_options')
    opt = opt.copy() if isinstance(opt, dict) else {}
    opt.update(options or {})
    opt.setdefault('output_profile', user.book_cfg('device'))
    opt.setdefault('input_profile', 'kindle')
    opt.setdefault('no_inline_toc', False)
    opt.setdefault('epub_inline_toc', True)
    opt.setdefault('dont_compress', True)
    opt.setdefault('dont_split_on_page_breaks', True)
    opt.setdefault('dont_save_webshelf', False)
    opt.setdefault('keep_images', True)
    opt.setdefault('keep_svg', False)
    opt['user'] = user

    #opt.setdefault('debug_pipeline', os.getenv('KE_TEMP_DIR'))
    #opt.setdefault('verbose', 1)
    #opt.setdefault('test', 1)

    #网页上的log_level可以覆盖全局配置
    level = opt.get('log_level') or os.environ.get('LOG_LEVEL')
    opt.pop('log_level', None)
    clogging.set_log_level(level)
    if opt.get('verbose'):
        clogging.set_log_level('DEBUG', only='calibre')
        
    return opt

