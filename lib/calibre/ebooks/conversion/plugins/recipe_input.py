#!/usr/bin/env python3
# -*- coding:utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, io
from collections import defaultdict
from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.constants import numeric_version
from calibre import walk, relpath, unicode_path, strftime, force_unicode
from calibre.web.feeds.recipes import compile_recipe
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.utils.date import now as nowf
from calibre.utils.localization import canonicalize_lang
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.ebooks.metadata.toc import TOC
from default_cv_mh import get_default_cover_data, get_default_masthead_data

class RecipeDisabled(Exception):
    pass

TOP_INDEX_TMPL = """<?xml version='1.0' encoding='utf-8'?><html lang="{lang}"><head><title>{title}</title>
<style type="text/css">
.article_date {{color: gray; font-family: monospace;}}
.article_description {{text-indent: 0pt;}}
a.article {{font-weight: bold; text-align:left;}}
a.feed {{font-weight: bold;}}
.calibre_navbar {{font-family:monospace;}}
</style></head><body>
<div data-calibre-rescale="100"><p style="text-align:center"><img src="{masthead}" alt="masthead"/></p>
<p style="text-align:right"> [{date}]</p>
<ul class="calibre_feed_list">
{toc}
</ul></div></body></html>"""

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
    #recipe_or_file: 可以为文件名, StringIO, 或一个列表
    #output_dir: 输出目录
    #fs: plumber生成的FsDictStub实例
    #user: 数据库 KeUser 实例
    #返回 opf文件的全路径名或传入的fs实例
    def convert(self, recipe_or_file, opts, file_ext, log, accelerators, output_dir, fs, user):
        self.user = user
        opts.output_profile.flow_size = 0
        orig_no_inline_navbars = opts.no_inline_navbars
        if not isinstance(recipe_or_file, list):
            recipe_or_file = [recipe_or_file]

        recipes = []
        for idx in range(len(recipe_or_file)):
            item = recipe_or_file[idx]
            if isinstance(item, io.StringIO):
                source = item.getvalue()
            else:
                try:
                    with open(item, 'rb') as f:
                        source = f.read()
                except:
                    continue

            try:
                recipes.append(compile_recipe(source))
            except Exception as e:
                log.warning('Failed to compile recipe: {}'.format(e))
            
        #生成 BasicNewsRecipe 对象并执行下载任务
        feed_index_start = 0
        self.recipe_objects = []
        self.feeds = []
        self.index_htmls = []
        self.aborted_articles = []
        self.failed_downloads = []
        for recipe in recipes:
            if 1:
                ro = recipe(opts, log, output_dir, fs, user=user, feed_index_start=feed_index_start)
                ro.download()
            #except Exception as e: #这个地方最好只做记录
            #    raise ValueError('Failed to execute recipe "{}": {}'.format(ro.title, e))
            feed_index_start += len(ro.feed_objects)
            self.feeds.extend(ro.feed_objects)
            self.aborted_articles.extend(ro.aborted_articles)
            self.failed_downloads.extend(ro.failed_downloads)
            self.index_htmls.append((ro.title, ro.get_root_index_html_name()))
            self.recipe_objects.append(ro)

        if not self.feeds: #让上层处理
            raise Exception('All feeds are empty, aborting.')

        self.build_top_index(self.recipe_objects[0], output_dir, fs)
        self.create_opf(output_dir, fs, user)

        #for key, val in ro.conversion_options.items():
        #    setattr(opts, key, val)
        opts.no_inline_navbars = orig_no_inline_navbars
        
        fs.find_opf_path()
        return fs

    #创建顶层的toc.html
    def build_top_index(self, recipe1, output_dir, fs):
        if len(self.index_htmls) > 1: #如果只有一个Recipe，则直接使用index.html
            recipe1 = self.recipe_objects[0]
            toc = []
            for idx, (title, indexName) in self.index_htmls:
                fileName = unicode_path(relpath(indexName, output_dir).replace(os.sep, '/'))
                toc.append(f'<li id="recipe_{idx}"><a href="{fileName}" data-calibre-rescale="120" class="feed">{title}</a></li>')

            html = TOP_INDEX_TMPL.format(lang=recipe1.lang_for_html, title=self.user.book_title, date=strftime(recipe1.datefmt),
                masthead=os.path.basename(recipe1.masthead_path), toc='\n'.join(toc)).encode('utf-8')
            index = os.path.join(self.output_dir, 'toc.html')
            fs.write(index, html, 'wb')
            self.top_index_file = 'toc.html'
        else:
            self.top_index_file = 'index.html'

    #通过Feed对象列表构建一个opf文件，将这个函数从 BasicNewsRecipe 里面移出来，方便一次处理多个Recipe
    def create_opf(self, dir_, fs, user):
        recipe1 = self.recipe_objects[0]
        onlyRecipe = True if len(self.recipe_objects) == 1 else False
        mi = self.build_meta(recipe1, onlyRecipe)
        
        opf = OPFCreator(dir_, mi, fs)
        # Add mastheadImage entry to <guide> section
        mp = getattr(recipe1, 'masthead_path', None)
        if mp is not None: # and os.access(mp, os.R_OK):
            from calibre.ebooks.metadata.opf2 import Guide
            ref = Guide.Reference(os.path.basename(recipe1.masthead_path), dir_)
            ref.type = 'masthead'
            ref.title = 'Masthead Image'
            opf.guide.append(ref)

        #manifest只是资源列表，所有的文件都出现就行，没有顺序之分
        manifest = [os.path.join(dir_, 'feed_%d'% (i)) for i in range(len(self.feeds))]
        for title, indexFile in self.index_htmls:
            manifest.append(os.path.join(dir_, indexFile))
        if not onlyRecipe:
            manifest.append(os.path.join(dir_, self.top_index_file))
        
        cPath, mPath = self.get_cover_masthead(dir_, recipe1, user, fs)
        opf.cover = cPath
        manifest.append(cPath)
        manifest.append(mPath)

        opf.create_manifest_from_files_in(manifest)

        #上面的语句执行时ncx还没有生成，要在函数末才生成，需要手动添加
        opf.manifest.add_item(os.path.join(dir_, 'index.ncx'), mime_type="application/x-dtbncx+xml")

        for mani in opf.manifest:
            if mani.path.endswith('.ncx'):
                mani.id = 'ncx'
            if mani.path.endswith('mastheadImage.gif'):
                mani.id = 'masthead-image'

        self.create_toc_spine(opf, dir_)

        opf_file = io.BytesIO()
        ncx_file = io.BytesIO()
        opf.render(opf_file, ncx_file)
        fs.write(os.path.join(dir_, 'index.opf'), opf_file.getvalue(), 'wb')
        fs.write(os.path.join(dir_, 'index.ncx'), ncx_file.getvalue(), 'wb')
    
    #创建多级TOC和书脊
    def create_toc_spine(self, opf, dir_):
        #创建顶层toc
        onlyRecipe = True if len(self.recipe_objects) == 1 else False
        entries = [self.top_index_file]
        toc = TOC(base_path=dir_)
        self.top_toc = []
        self.play_order = 0
        if not onlyRecipe:
            for title, indexFile in self.index_htmls:
                ro = self.recipe_objects[po]
                self.play_order += 1
                self.top_toc.append(toc.add_item(indexFile, None, title, play_order=self.play_order, description=ro.desc, author=ro.__author__))
                entries.append(indexFile)
        else:
            self.top_toc.append(toc)
        
        if len(self.feeds) == 1: #只有一个Feed时，直接将Article做为顶层目录
            entries.append('feed_0/index.html')
            self.add_article_toc(toc, entries, feedIdx=0)
        else:
            feedIdx = 0
            for recipeIdx, recipe in enumerate(self.recipe_objects):
                for feed in recipe.feed_objects:
                    feedIndexFile = f'feed_{feedIdx}/index.html'
                    entries.append(feedIndexFile)
                    author = getattr(feed, 'author', None) or None
                    desc = getattr(feed, 'description', None) or None
                    self.play_order += 1
                    item = self.top_toc[recipeIdx].add_item(feedIndexFile, None, feed.title, play_order=self.play_order, description=desc, author=author)
                    self.add_article_toc(item, entries, feedIdx=feedIdx)
                    feedIdx += 1

        for i, p in enumerate(entries):
            entries[i] = os.path.join(dir_, p.replace('/', os.sep))
        opf.create_spine(entries)
        opf.set_toc(toc)

    #创建下级toc，包括文章toc或可能的文章内toc
    def add_article_toc(self, parent, entries, feedIdx):
        recipe1 = self.recipe_objects[0]
        feed = self.feeds[feedIdx]
        for idx, arti in enumerate(feed):
            if not getattr(arti, 'downloaded', False):
                continue

            aDir = f'feed_{feedIdx}/article_{idx}/'
            author = arti.author or None
            desc = arti.text_summary
            if desc:
                desc = BasicNewsRecipe.description_limiter(desc)
            else:
                desc = None
            tt = arti.toc_thumbnail or None
            artiFile = f'{aDir}index.html'
            entries.append(artiFile)
            artiTitle = arti.title or _('Untitled article')
            self.play_order += 1
            artiTocEntry = parent.add_item(artiFile, None, artiTitle, play_order=self.play_order, author=author, description=desc, toc_thumbnail=tt)
            for entry in arti.internal_toc_entries: #如果文章(html)内还有子目录
                if entry.get('anchor'):
                    self.play_order += 1
                    artiTocEntry.add_item(artiFile, entry['anchor'], entry['title'] or _('Unknown section'), play_order=self.play_order)

            #这段注释后的代码是添加navbar的
            #last = os.path.join(aDir, 'index.html')
            #src = None
            #last = os.path.join(self.output_dir, last)
            #for sp in arti.sub_pages:
            #    prefix = os.path.commonprefix([opf_path, sp])
            #    relp = sp[len(prefix):]
            #    entries.append(relp.replace(os.sep, '/'))
            #    last = sp
            #if os.path.exists(last):
            #    with open(last, 'rb') as fi:
            #        src = fi.read().decode('utf-8')
            #if src:
                #soup = BeautifulSoup(src)
                #body = soup.find('body')
                #if body is not None:
                    #prefix = '/'.join('..'for i in range(2*len(re.findall(r'link\d+', last))))
                    #templ = self.navbar.generate(True, num, idx, len(f),
                    #                not self.has_single_feed,
                    #                arti.orig_url, __appname__, prefix=prefix,
                    #                center=self.center_navbar)
                    #elem = BeautifulSoup(templ.render(doctype='xhtml').decode('utf-8')).find('div')
                    #body.insert(len(body.contents), elem)
                #    with open(last, 'wb') as fi:
                #        fi.write(str(soup).encode('utf-8'))

    #通过Feed列表和一些选项构建Meta信息
    #recipe1: 第一个BasicNewsRecipe实例
    #onlyRecipe: 如果一本书仅包含一个BasicNewRecipe，则为True
    def build_meta(self, recipe1, onlyRecipe):
        title = recipe1.short_title()
        pdate = recipe1.publication_date()
        if recipe1.output_profile.periodical_date_in_title:
            title += strftime(recipe1.timefmt, pdate)
        mi = MetaInformation(title, ['KindleEar'])
        mi.publisher = 'KindleEar'
        mi.author_sort = 'KindleEar'
        if recipe1.publication_type:
            mi.publication_type = f'periodical:{recipe1.publication_type}:{recipe1.short_title()}'
        mi.timestamp = nowf()
        article_titles = []
        aseen = set()
        for (af, aa) in self.aborted_articles:
            aseen.add(aa.title)
        for (ff, fa, tb) in self.failed_downloads:
            aseen.add(fa.title)
        for f in self.feeds:
            for a in f:
                if a.title and a.title not in aseen:
                    aseen.add(a.title)
                    article_titles.append(force_unicode(a.title, 'utf-8'))

        desc = recipe1.description if onlyRecipe else 'KindleEar'
        if not isinstance(desc, str):
            desc = desc.decode('utf-8', 'replace')
        mi.comments = (_('Articles in this issue:') + '\n\n' + '\n\n'.join(article_titles)) + '\n\n' + desc

        language = canonicalize_lang(recipe1.language if onlyRecipe else user.book_language)
        if language is not None:
            mi.language = language
        mi.pubdate = pdate
        return mi

    #获取封面路径，如果没有，生成一个
    def get_cover_masthead(self, dir_, recipe1, user, fs):
        cPath = getattr(recipe1, 'cover_path', None)
        if cPath is None:
            cover_data = user.cover if user.cover else get_default_cover_data()
            cPath = os.path.join(dir_, 'cover.jpg')
            self.cover_path = cPath
            fs.write(cPath, cover_data, 'wb')

        mPath = getattr(recipe1, 'masthead_path', None)
        return cPath, mPath

    def postprocess_book(self, oeb, opts, log):
        return
        #for recipe in self.recipe_object:
        #    recipe.internal_postprocess_book(oeb, opts, log)
        #    recipe.postprocess_book(oeb, opts, log)

    def specialize(self, oeb, opts, log, output_fmt):
        if opts.no_inline_navbars:
            from calibre.ebooks.oeb.base import XPath
            for item in oeb.spine:
                for div in XPath('//h:div[contains(@class, "calibre_navbar")]')(item.data):
                    div.getparent().remove(div)

    def save_download(self, zf):
        return
        #raw = self.recipe_source
        #if isinstance(raw, str):
        #    raw = raw.encode('utf-8')
        #zf.writestr('download.recipe', raw)
