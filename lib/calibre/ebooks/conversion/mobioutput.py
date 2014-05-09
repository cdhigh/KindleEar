#!/usr/bin/env python
# -*- coding:utf-8 -*-
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

def remove_html_cover(oeb, log):
    from calibre.ebooks.oeb.base import OEB_DOCS

    if not oeb.metadata.cover \
        or 'cover' not in oeb.guide:
        return
    href = oeb.guide['cover'].href
    del oeb.guide['cover']
    item = oeb.manifest.hrefs[href]
    if item.spine_position is not None:
        log.warn('Found an HTML cover: ', item.href, 'removing it.',
                'If you find some content missing from the output MOBI, it '
                'is because you misidentified the HTML cover in the input '
                'document')
        oeb.spine.remove(item)
        if item.media_type in OEB_DOCS:
            oeb.manifest.remove(item)

def extract_mobi(output_path, opts):
    if opts.extract_to is not None:
        from calibre.ebooks.mobi.debug.main import inspect_mobi
        ddir = opts.extract_to
        inspect_mobi(output_path, ddir=ddir)

class MOBIOutput:
    name = 'MOBI Output'
    author = 'Kovid Goyal'
    file_type = 'mobi'
    
    @property
    def is_periodical(self):
        return self.oeb.metadata.publication_type and \
            unicode(self.oeb.metadata.publication_type[0]).startswith('periodical:')

    def check_for_periodical(self):
        if self.is_periodical:
            self.periodicalize_toc()
            self.check_for_masthead()
            self.opts.mobi_periodical = True
        else:
            self.opts.mobi_periodical = False

    def check_for_masthead(self):
        found = 'masthead' in self.oeb.guide
        if not found:
            from calibre.ebooks import generate_masthead
            self.oeb.log.debug('No masthead found in manifest, generating default mastheadImage...')
            raw = generate_masthead(unicode(self.oeb.metadata['title'][0]))
            id, href = self.oeb.manifest.generate('masthead', 'masthead')
            self.oeb.manifest.add(id, href, 'image/gif', data=raw)
            self.oeb.guide.add('masthead', 'Masthead Image', href)
        #else:
        #    self.oeb.log.debug('Using mastheadImage supplied in manifest...')

    def periodicalize_toc(self):
        #return #commit by arroz, you have to create a toc hiberarchy youself.
        
        from calibre.ebooks.oeb.base import TOC
        toc = self.oeb.toc
        if not toc: # or len(self.oeb.spine) < 3:
            return
        if toc and toc[0].klass != 'periodical':
            #spine[0]为index.html
            #one, two = self.oeb.spine[0], self.oeb.spine[1]
            self.log.info('Converting TOC for MOBI periodical indexing...')

            articles = {}
            if toc.depth() < 3:
                # single section periodical
                #self.oeb.manifest.remove(one) #manifest删除的同时也会将spine项删除
                #self.oeb.manifest.remove(two)
                #新增一个节点，将之前的所有节点归于此节点下
                sections = [TOC(klass='section', title=_('All articles'),
                    href=self.oeb.spine[0].href)]
                for x in toc:
                    sections[0].nodes.append(x)
            else:
                # multi-section periodical
                #self.oeb.manifest.remove(one)
                sections = list(toc) # 顶节点和第一层节点的列表
                for x in sections:
                    x.klass = 'section'
                    articles_ = list(x) #第二层节点
                    if articles_: #去掉原先节点的链接，改变链接到第一篇文章
                        #self.oeb.manifest.remove(self.oeb.manifest.hrefs[x.href])
                        x.href = articles_[0].href


            for sec in sections:
                articles[id(sec)] = []
                for a in list(sec):
                    a.klass = 'article'
                    articles[id(sec)].append(a)
                    sec.nodes.remove(a)

            root = TOC(klass='periodical', href=self.oeb.spine[0].href, play_order=0, id='periodical',
                    title=unicode(self.oeb.metadata.title[0]))
            #建立 root/Sections/artcicles三层结构
            for s in sections:
                if articles[id(s)]:
                    for a in articles[id(s)]:
                        s.nodes.append(a)
                    root.nodes.append(s)

            for x in list(toc.nodes):
                toc.nodes.remove(x)

            toc.nodes.append(root)

            # Fix up the periodical href to point to first section href
            toc.nodes[0].href = toc.nodes[0].nodes[0].href

    def convert(self, oeb, output_path, opts, log):
        from calibre.ebooks.mobi.writer2.resources import Resources
        self.log, self.opts, self.oeb = log, opts, oeb

        mobi_type = opts.mobi_file_type
        if self.is_periodical:
            mobi_type = 'old' # Amazon does not support KF8 periodicals
        create_kf8 = mobi_type in ('new', 'both')

        remove_html_cover(self.oeb, self.log)
        resources = Resources(oeb, opts, self.is_periodical,
                add_fonts=create_kf8, process_images=opts.process_images)
        self.check_for_periodical()
        
        if create_kf8:
            # Split on pagebreaks so that the resulting KF8 works better with
            # calibre's viewer, which does not support CSS page breaks
            from calibre.ebooks.oeb.transforms.split import Split
            Split()(self.oeb, self.opts)


        kf8 = self.create_kf8(resources, for_joint=mobi_type=='both'
                ) if create_kf8 else None
        if mobi_type == 'new':
            kf8.write(output_path)
            extract_mobi(output_path, opts)
            return

        self.log.info('Creating MOBI 6 output')
        self.write_mobi(output_path, kf8, resources)

    def create_kf8(self, resources, for_joint=False):
        from calibre.ebooks.mobi.writer8.main import create_kf8_book
        return create_kf8_book(self.oeb, self.opts, resources,
                for_joint=for_joint)

    def write_mobi(self, output_path, kf8, resources):
        from calibre.ebooks.mobi.mobiml import MobiMLizer
        from calibre.ebooks.oeb.transforms.manglecase import CaseMangler
        from calibre.ebooks.oeb.transforms.htmltoc import HTMLTOCAdder
        
        opts, oeb = self.opts, self.oeb
        if not opts.no_inline_toc:
            tocadder = HTMLTOCAdder(title=opts.toc_title, position='start' if
                    opts.mobi_toc_at_start else 'end')
            tocadder(oeb, opts)
        mangler = CaseMangler()
        mangler(oeb, opts)
        
        if hasattr(self.oeb, 'inserted_metadata_jacket'):
            self.workaround_fire_bugs(self.oeb.inserted_metadata_jacket)
        mobimlizer = MobiMLizer(ignore_tables=opts.linearize_tables)
        mobimlizer(oeb, opts)
        write_page_breaks_after_item = True
        from calibre.ebooks.mobi.writer2.main import MobiWriter
        writer = MobiWriter(opts, resources, kf8,
                        write_page_breaks_after_item=write_page_breaks_after_item)
        writer(oeb, output_path)
        extract_mobi(output_path, opts)

    def specialize_css_for_output(self, log, opts, item, stylizer):
        from calibre.ebooks.mobi.writer8.cleanup import CSSCleanup
        CSSCleanup(log, opts)(item, stylizer)

    def workaround_fire_bugs(self, jacket):
        # The idiotic Fire crashes when trying to render the table used to
        # layout the jacket
        from calibre.ebooks.oeb.base import XHTML
        for table in jacket.data.xpath('//*[local-name()="table"]'):
            table.tag = XHTML('div')
            for tr in table.xpath('descendant::*[local-name()="tr"]'):
                cols = tr.xpath('descendant::*[local-name()="td"]')
                tr.tag = XHTML('div')
                for td in cols:
                    td.tag = XHTML('span' if cols else 'div')

