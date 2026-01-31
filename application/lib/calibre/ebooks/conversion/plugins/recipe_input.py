#!/usr/bin/env python3
# -*- coding:utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, io, uuid, traceback
from bs4 import BeautifulSoup
from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre import strftime, force_unicode
from calibre.web.feeds import templates
from calibre.web.feeds.news import BasicNewsRecipe, DEFAULT_MASTHEAD_IMAGE
from calibre.utils.localization import canonicalize_lang
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.ebooks.metadata.toc import TOC
from application.ke_utils import loc_exc_pos

class RecipeDisabled(Exception):
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

    def __init__(self, *args):
        super().__init__(*args)
        self.user = None
        self.feeds = []
        self.aborted_articles = []
        self.failed_downloads = []
        self.index_htmls = []
        self.recipe_objects = []

    #执行转换完成后返回生成的 opf 文件路径，只是路径，不包含文件名
    #recipes: 可以为文件名, StringIO, 或一个列表
    #output_dir: 输出目录
    #fs: plumber生成的FsDictStub实例
    #返回 opf文件的全路径名或传入的fs实例
    def convert(self, recipes, opts, file_ext, log, output_dir, fs):
        self.user = opts.user
        opts.output_profile.flow_size = 0
        orig_no_inline_navbars = opts.no_inline_navbars
        if not isinstance(recipes, list):
            recipes = [recipes]
        
        #生成 BasicNewsRecipe 对象并执行下载任务
        feed_index_start = 0
        recipeNum = len(recipes)
        recipe_objects = [] #如果直接使用self.recipe_objects=[]，经常出现两次执行分配同一地址的情况
        feeds = []
        index_htmls = []
        aborted_articles = []
        failed_downloads = []
        for recipe in recipes:
            indexFile = None
            try:
                ro = recipe(opts, log, output_dir, fs, feed_index_start=feed_index_start)
                if recipeNum > 1: #只有单独推送才使用recipe的封面或报头
                    ro.cover_url = None
                    ro.masthead_url = None
                indexFile = ro.download()
            except Exception as e:
                log.warning(loc_exc_pos(f'Failed to execute recipe "{recipe.title}"'))
                #log.debug(traceback.format_exc())
                continue

            if indexFile and ro.feed_objects and (len(ro.feed_objects) > 0):
                feed_index_start += len(ro.feed_objects)
                feeds.extend(ro.feed_objects)
                aborted_articles.extend(ro.aborted_articles)
                failed_downloads.extend(ro.failed_downloads)
                index_htmls.append((ro.title, ro.get_root_index_html_name()))
                recipe_objects.append(ro)

            #可能会有些副作用，前面的conversion_options会影响后面的recipe
            #for key, val in ro.conversion_options.items():
            #    setattr(opts, key, val)

        if not feeds: #让上层处理
            raise Exception('All feeds are empty, aborting.')

        self.feeds = feeds
        self.aborted_articles = aborted_articles
        self.failed_downloads = failed_downloads
        self.index_htmls = index_htmls
        self.recipe_objects = recipe_objects

        self.build_top_index(output_dir, fs, self.user)
        self.create_opf(output_dir, fs, self.user)
        self.create_feed_navbar(output_dir, fs, self.user)
        self.create_article_navbar(output_dir, fs, self.user)

        opts.no_inline_navbars = orig_no_inline_navbars
        
        fs.find_opf_path()
        return fs

    #将所有Feed标题合并，覆盖原先的index.html
    def build_top_index(self, dir_, fs, user):
        if len(self.recipe_objects) <= 1:
            return

        recipe1 = self.recipe_objects[0]
        lang = user.book_cfg('language', 'en')
        templ = templates.IndexTemplate(lang=lang)
        css = recipe1.template_css + '\n\n' + user.get_extra_css()
        timefmt = recipe1.timefmt
        src = templ.generate('KindleEar', DEFAULT_MASTHEAD_IMAGE, timefmt, self.feeds, extra_css=css).render(doctype='xhtml')
        fileName = os.path.join(dir_, 'index.html')
        fs.write(fileName, src, 'wb')

    #通过Feed对象列表构建一个opf文件，将这个函数从 BasicNewsRecipe 里面移出来，方便一次处理多个Recipe
    def create_opf(self, dir_, fs, user):
        recipe1 = self.recipe_objects[0]
        onlyRecipe = True if len(self.recipe_objects) == 1 else False
        mi = self.build_meta(recipe1, onlyRecipe)
        cover_data, cPath, mPath = self.get_cover_masthead(dir_, recipe1, onlyRecipe, user, fs)
        mi.cover = cPath
        mi.cover_data = ('jpg', cover_data) if cover_data else (None, None)

        opf = OPFCreator(dir_, mi, fs)
        opf.cover = None
        # Add mastheadImage entry to <guide> section
        mp = getattr(recipe1, 'masthead_path', None)
        if mp is not None: # and os.access(mp, os.R_OK):
            from calibre.ebooks.metadata.opf2 import Guide
            ref = Guide.Reference(os.path.basename(recipe1.masthead_path), dir_)
            ref.type = 'masthead'
            ref.title = 'Masthead Image'
            opf.guide.append(ref)

        #manifest 资源列表
        manifest = [mPath]
        if cPath:
            manifest.append(cPath)
        manifest.append(os.path.join(dir_, 'index.html'))
        manifest.extend([os.path.join(dir_, 'feed_%d'% (i)) for i in range(len(self.feeds))])
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
        entries = ['index.html']
        toc = TOC(base_path=dir_)
        self.play_order = 0
        for feedIdx, feed in enumerate(self.feeds):
            feedIndexFile = f'feed_{feedIdx}/index.html'
            entries.append(feedIndexFile)
            author = getattr(feed, 'author', None) or None
            desc = getattr(feed, 'description', None) or None
            self.play_order += 1
            item = toc.add_item(feedIndexFile, None, feed.title, play_order=self.play_order, description=desc, author=author)
            self.add_article_toc(item, entries, feed, feedIdx)

        for i, p in enumerate(entries):
            entries[i] = os.path.join(dir_, p)
        opf.create_spine(entries)
        opf.set_toc(toc)

    #创建下级toc，包括文章toc或可能的文章内toc
    #parent: 本级toc的父目录
    #entries: 列表，输出参数，用于保存所有添加到toc的html内容，用于之后创建spine
    #feed: Recipe内的某一个Feed实例
    #feedIdx: 在本书内的Feed索引号
    def add_article_toc(self, parent, entries, feed, feedIdx):
        for idx, article in enumerate(feed):
            if not getattr(article, 'downloaded', False):
                continue

            aDir = f'feed_{feedIdx}/article_{idx}/'
            author = article.author or None
            desc = BasicNewsRecipe.description_limiter(article.text_summary) or None
            tt = article.toc_thumbnail or None
            artiFile = f'{aDir}index.html'
            entries.append(artiFile)
            artiTitle = article.title or _('Untitled article')
            self.play_order += 1
            artiTocEntry = parent.add_item(artiFile, None, artiTitle, play_order=self.play_order, author=author, description=desc, toc_thumbnail=tt)
            for entry in article.internal_toc_entries: #如果文章(html)内还有子目录
                if entry.get('anchor'):
                    self.play_order += 1
                    artiTocEntry.add_item(artiFile, entry['anchor'], entry['title'] or _('Unknown section'), play_order=self.play_order)

    #创建Feed的导航条，不受user配置影响，直接创建
    def create_feed_navbar(self, dir_, fs, user):
        #内嵌函数
        feedFileName = lambda dir_, idx: os.path.join(dir_, f'feed_{idx}/index.html')
        feedNum = len(self.feeds)

        for idx, feed in enumerate(self.feeds):
            fileName = feedFileName(dir_, idx)
            if not fs.isfile(fileName):
                continue

            src = fs.read(fileName).decode('utf-8')
            if not src:
                continue
            soup = BeautifulSoup(src, 'lxml')
            body = soup.find('body')
            if body is None:
                continue

            #内嵌函数
            sepAdded = False
            def add_separator(soup, div):
                nonlocal sepAdded
                if not sepAdded:
                    sepAdded = True
                    return
                span = soup.new_tag('span')
                span.string = ' | '
                div.append(span)

            #内嵌函数
            def add_navitem(soup, div, text, link):
                a = soup.new_tag('a', href=link)
                a.string = text
                div.append(a)

            div = soup.new_tag('div', attrs={'class': 'calibre_navbar', 
                'style': f'text-align:center', 'data-calibre-rescale': '70'})
            
            #前一个Feed的链接
            prevIdx = next((i for i in range(idx - 1, -1, -1) if fs.isfile(feedFileName(dir_, i))), -1)
            if prevIdx >= 0:
                PrevLink = f'../feed_{prevIdx}/index.html'
                add_separator(soup, div)
                add_navitem(soup, div, 'Previous', PrevLink)
            
            add_separator(soup, div)    
            add_navitem(soup, div, 'Main menu', f'../index.html#feed_{idx}')
            
            #下一个Feed的链接
            nextIdx = next((i for i in range(idx + 1, feedNum) if fs.isfile(feedFileName(dir_, i))), -1)
            if nextIdx >= 0:
                nextLink = f'../feed_{nextIdx}/index.html'
                add_separator(soup, div)
                add_navitem(soup, div, 'Next', nextLink)
                
            bottomDiv = BeautifulSoup(str(div), 'lxml').find('div') #复制一个tag用于插入末尾
            div.append(soup.new_tag('hr'))
            body.insert(0, div)
            bottomDiv.insert(0, soup.new_tag('hr'))
            bottomDiv.append(soup.new_tag('br'))
            body.append(bottomDiv)
            
            try:
                fs.write(fileName, str(soup).encode('utf-8'))
            except:
                pass

    #需要时创建文章内的导航条
    def create_article_navbar(self, dir_, fs, user):
        navbarSetting = user.book_cfg('navbar') or ''
        if not navbarSetting:
            return

        align = 'left' if 'left' in navbarSetting else 'center'
        pos = 'bottom' if 'bottom' in navbarSetting else 'top'

        feedFileName = lambda dir_, idx: os.path.join(dir_, f'feed_{idx}/index.html')
        feedNum = len(self.feeds)

        for feedIdx, feed in enumerate(self.feeds):
            feedIndexFile = f'feed_{feedIdx}/index.html'
            articleNum = len(feed)
            for idx, article in enumerate(feed):
                fileName = os.path.join(dir_, f'feed_{feedIdx}/article_{idx}/index.html')
                if not article.downloaded or not fs.isfile(fileName):
                    continue

                src = fs.read(fileName).decode('utf-8')
                if not src:
                    continue
                soup = BeautifulSoup(src, 'lxml')
                body = soup.find('body')
                if body is None:
                    continue

                #内嵌函数
                sepAdded = False
                def add_separator(soup, div):
                    nonlocal sepAdded
                    if not sepAdded:
                        sepAdded = True
                        return
                    span = soup.new_tag('span')
                    span.string = ' | '
                    div.append(span)

                #内嵌函数
                def add_navitem(soup, div, text, link):
                    a = soup.new_tag('a', href=link)
                    a.string = text
                    div.append(a)

                div = soup.new_tag('div', attrs={'class': 'calibre_navbar', 
                    'style': f'text-align:{align}', 'data-calibre-rescale': '70'})
                if pos == 'bottom':
                    div.append(soup.new_tag('hr'))
                
                #前一个Feed的链接
                prevIdx = next((i for i in range(feedIdx - 1, -1, -1) if fs.isfile(feedFileName(dir_, i))), -1)
                if prevIdx >= 0:
                    PrevLink = f'../../feed_{prevIdx}/index.html'
                    add_separator(soup, div)
                    add_navitem(soup, div, '<<', PrevLink)

                #前一篇文章的链接
                fId = feedIdx
                prevIdx = next((i for i in range(idx - 1, -1, -1) if feed.articles[i].downloaded), -1)
                if prevIdx < 0:
                    for fId in range(feedIdx - 1, -1, -1): #跳过没有文章的Feed或没有下载的文章
                        lst = self.feeds[fId]
                        prevIdx = next((i for i in range(len(lst) - 1, -1, -1) if lst.articles[i].downloaded), -1)
                        if prevIdx >= 0:
                            break
                if prevIdx >= 0:
                    PrevLink = f'../../feed_{fId}/article_{prevIdx}/index.html'
                    add_separator(soup, div)
                    add_navitem(soup, div, 'Prev', PrevLink)
                
                add_separator(soup, div)
                add_navitem(soup, div, 'Sec', f'../index.html#article_{idx}')
                add_separator(soup, div)
                add_navitem(soup, div, 'Main', f'../../index.html#feed_{feedIdx}')

                #下一篇文章的链接
                fId = feedIdx
                nextIdx = next((i for i in range(idx + 1, articleNum) if feed.articles[i].downloaded), -1)
                if nextIdx < 0:
                    for fId in range(feedIdx + 1, feedNum): #跳过没有文章的Feed或没有下载的文章
                        lst = self.feeds[fId]
                        nextIdx = next((i for i in range(len(lst)) if lst.articles[i].downloaded), -1)
                        if nextIdx >= 0:
                            break
                if nextIdx >= 0:
                    nextLink = f'../../feed_{fId}/article_{nextIdx}/index.html'
                    add_separator(soup, div)
                    add_navitem(soup, div, 'Next', nextLink)

                #后一个Feed的链接
                nextIdx = next((i for i in range(feedIdx + 1, feedNum) if fs.isfile(feedFileName(dir_, i))), -1)
                if nextIdx >= 0:
                    nextLink = f'../../feed_{nextIdx}/index.html'
                    add_separator(soup, div)
                    add_navitem(soup, div, '>>', nextLink)
                
                if pos == 'bottom':
                    div.append(soup.new_tag('br'))
                    body.append(div)
                else:
                    div.append(soup.new_tag('hr'))
                    body.insert(0, div)

                try:
                    fs.write(fileName, str(soup).encode('utf-8'))
                except:
                    pass


    #通过Feed列表和一些选项构建Meta信息
    #recipe1: 第一个BasicNewsRecipe实例
    #onlyRecipe: 如果一本书仅包含一个BasicNewRecipe，则为True
    def build_meta(self, recipe1, onlyRecipe):
        title = recipe1.short_title() if onlyRecipe else self.user.book_cfg('title')
        try:
            pdate = recipe1.publication_date()
        except Exception as e:
            default_log.warning(f'recipe1.publication_date error: {e}')
            pdate = self.user.local_time()
        timefmt = recipe1.timefmt.strip()
        if timefmt and self.user.book_cfg('title_fmt'):
            title = f'{title} {strftime(timefmt, pdate)}'
        mi = MetaInformation(title, ['KindleEar'])
        mi.publisher = 'KindleEar'
        #修正Kindle固件5.9.x将作者显示为日期的BUG
        authorFmt = self.user.book_cfg('author_fmt')
        now = self.user.local_time()
        if authorFmt:
            snow = now.strftime(authorFmt)
            mi.author_sort = snow
            mi.authors = [snow]
        else:
            mi.author_sort = 'KindleEar'
            mi.authors = ['KindleEar']
        if recipe1.publication_type == 'magazine':
            mi.publication_type = f'periodical:magazine:{title}'
        elif recipe1.publication_type:
            mi.publication_type = f'book:{recipe1.publication_type}:{title}'
        mi.timestamp = now
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
        mi.comments = (_('Articles in this issue:') + '\n' + '\n'.join(article_titles)) + '\n\n' + desc
        mi.languages = [recipe1.language]
        mi.pubdate = pdate
        mi.identifier = str(uuid.uuid4())
        return mi

    #生成并写入默认的用户封面, 返回封面二进制数据和封面文件路径
    def _generate_default_cover(self, dir_, user, fs):
        cPath = os.path.join(dir_, 'cover.jpg')
        cData = user.get_cover_data()
        fs.write(cPath, cData)
        return cData, cPath

    #获取单recipe模式的封面
    def _get_recipe_cover(self, dir_, recipe, user, fs):
        cData = cPath = None
        try:
            #False-不使用封面, None-使用默认封面, 其他值-自定义封面
            if recipe.get_cover_url() != False:
                cPath = getattr(recipe, 'cover_path', None) #之前已经下载了
                if cPath and fs.exists(cPath):
                    cData = fs.read(cPath, 'rb')
                else:
                    cData, cPath = self._generate_default_cover(dir_, user, fs)
        except Exception:
            pass
            
        return cData, cPath

    #获取封面和报头路径，如果没有，使用默认图像
    def get_cover_masthead(self, dir_, recipe1, onlyRecipe, user, fs):
        mPath = cData = cPath = None
        if onlyRecipe:
            mPath = getattr(recipe1, 'masthead_path', None)
            cData, cPath = self._get_recipe_cover(dir_, recipe1, user, fs)
        elif user.covers.get('enable', ''):
            cData, cPath = self._generate_default_cover(dir_, user, fs)
            
        if not mPath: #默认报头
            mPath = os.path.join(dir_, DEFAULT_MASTHEAD_IMAGE)
            mhData = BasicNewsRecipe.default_masthead_image()
            fs.write(mPath, mhData, 'wb')
        return cData, cPath, mPath

    def postprocess_book(self, oeb, opts, log):
        for ro in self.recipe_objects:
            ro.internal_postprocess_book(oeb, opts, log)
            ro.postprocess_book(oeb, opts, log)

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
