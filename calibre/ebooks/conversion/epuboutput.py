#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, zipfile, re
from calibre.utils.img import rescale_image

block_level_tags = (
      'address',
      'body',
      'blockquote',
      'center',
      'dir',
      'div',
      'dl',
      'fieldset',
      'form',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'hr',
      'isindex',
      'menu',
      'noframes',
      'noscript',
      'ol',
      'p',
      'pre',
      'table',
      'ul',
      )

def getepubOpts():
    opts = OptionValues()
    setattr(opts, "extract_to", False)
    setattr(opts, "dont_split_on_page_breaks", False)
    setattr(opts, "flow_size", 260)
    setattr(opts, "no_default_epub_cover", True)
    setattr(opts, "no_svg_cover", True)
    setattr(opts, "preserve_cover_aspect_ratio", True)
    setattr(opts, "epub_flatten", False)
    setattr(opts, "output_profile", KindleOutput(None))
    setattr(opts, "pretty_print", True)
    
    return opts
    
class EPUBOutput:
    name = 'EPUB Output'
    author = 'Kovid Goyal'
    file_type = 'epub'

    def workaround_webkit_quirks(self): # {{{
        from calibre.ebooks.oeb.base import XPath
        for x in self.oeb.spine:
            root = x.data
            body = XPath('//h:body')(root)
            if body:
                body = body[0]

            if not hasattr(body, 'xpath'):
                continue

            for pre in XPath('//h:pre')(body):
                if not pre.text and len(pre) == 0:
                    pre.tag = 'div'
    # }}}

    def upshift_markup(self): # {{{
        'Upgrade markup to comply with XHTML 1.1 where possible'
        from calibre.ebooks.oeb.base import XPath, XML
        for x in self.oeb.spine:
            root = x.data
            if (not root.get(XML('lang'))) and (root.get('lang')):
               root.set(XML('lang'), root.get('lang'))
            body = XPath('//h:body')(root)
            if body:
                body = body[0]

            if not hasattr(body, 'xpath'):
                continue
            for u in XPath('//h:u')(root):
                u.tag = 'span'
                u.set('style', 'text-decoration:underline')

            seen_ids, seen_names = set(), set()
            for x in XPath('//*[@id or @name]')(root):
                eid, name = x.get('id', None), x.get('name', None)
                if eid:
                    if eid in seen_ids:
                        del x.attrib['id']
                    else:
                        seen_ids.add(eid)
                if name:
                    if name in seen_names:
                        del x.attrib['name']
                    else:
                        seen_names.add(name)


    # }}}

    def convert(self, oeb, output_path, opts, log):
        self.log, self.opts, self.oeb = log, opts, oeb

        if self.opts.epub_flatten:
            from calibre.ebooks.oeb.transforms.filenames import FlatFilenames
            FlatFilenames()(oeb, opts)
        else:
            from calibre.ebooks.oeb.transforms.filenames import UniqueFilenames
            UniqueFilenames()(oeb, opts)

        self.workaround_ade_quirks()
        self.workaround_webkit_quirks()
        self.upshift_markup()
        #from calibre.ebooks.oeb.transforms.rescale import RescaleImages
        #RescaleImages()(oeb, opts)

        from calibre.ebooks.oeb.transforms.split import Split
        split = Split(not self.opts.dont_split_on_page_breaks,
                max_flow_size=self.opts.flow_size*1024
                )
        split(self.oeb, self.opts)

        #from calibre.ebooks.oeb.transforms.cover import CoverManager
        #cm = CoverManager(
        #        no_default_cover=self.opts.no_default_epub_cover,
        #        no_svg_cover=self.opts.no_svg_cover,
        #        preserve_aspect_ratio=self.opts.preserve_cover_aspect_ratio)
        #cm(self.oeb, self.opts, self.log)

        self.workaround_sony_quirks()

        if self.oeb.toc.count() == 0:
            self.log.warn('This EPUB file has no Table of Contents. '
                    'Creating a default TOC')
            first = iter(self.oeb.spine).next()
            self.oeb.toc.add(_('Start'), first.href)

        from calibre.ebooks.oeb.base import OPF_MIME, NCX_MIME, PAGE_MAP_MIME
        results = oeb.to_opf2(page_map=True)
        
        epub = zipfile.ZipFile(output_path, "w", zipfile.ZIP_STORED)
        epub.writestr('mimetype', "application/epub+zip")
        
        CONTAINER = u'''\
<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
   <rootfiles>
      <rootfile full-path="{0}" media-type="application/oebps-package+xml"/>
   </rootfiles>
</container>
    '''
        if hasattr(self.opts,"epub_dont_compress") and self.opts.epub_dont_compress:
            compress = zipfile.ZIP_STORED
        else:
            compress = zipfile.ZIP_DEFLATED
        from lxml import etree
        for key in (OPF_MIME, NCX_MIME, PAGE_MAP_MIME):
            href, root = results.pop(key, [None, None])
            if root is not None:
                if key == OPF_MIME:
                    epub.writestr('META-INF/container.xml', CONTAINER.format('OEBPS/%s'%href).encode('utf-8'),
                        compress_type=compress)
                raw = etree.tostring(root, pretty_print=True,encoding='utf-8', xml_declaration=True)
                epub.writestr('OEBPS/%s' % href, raw)
        
        from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES
        for item in oeb.manifest:
            if item.media_type in OEB_RASTER_IMAGES:
                try:
                    img = self.process_image(str(item))
                except:
                    self.log.warn('Bad image file %r.' % item.href)
                else:
                    epub.writestr('OEBPS/%s' % item.href, img, compress_type=compress)
            else:
                epub.writestr('OEBPS/%s' % item.href, str(item), compress_type=compress)
    
    def process_image(self, data):
        if not self.opts.process_images or self.opts.process_images_immediately:
            return data
        if self.opts.mobi_keep_original_images:
            return mobify_image(data)
        else:
            return rescale_image(data, png2jpg=self.opts.image_png_to_jpg,
                            graying=self.opts.graying_image,
                            reduceto=self.opts.reduce_image_to)
    
    def workaround_ade_quirks(self):
        """
        Perform various markup transforms to get the output to render correctly
        in the quirky ADE.
        """
        from calibre.ebooks.oeb.base import XPath, XHTML, barename, urlunquote

        stylesheet = self.oeb.manifest.main_stylesheet

        # ADE cries big wet tears when it encounters an invalid fragment
        # identifier in the NCX toc.
        frag_pat = re.compile(r'[-A-Za-z0-9_:.]+$')
        for node in self.oeb.toc.iter():
            href = getattr(node, 'href', None)
            if hasattr(href, 'partition'):
                base, _, frag = href.partition('#')
                frag = urlunquote(frag)
                if frag and frag_pat.match(frag) is None:
                    self.log.warn(
                            'Removing invalid fragment identifier %r from TOC'%frag)
                    node.href = base

        for x in self.oeb.spine:
            root = x.data
            body = XPath('//h:body')(root)
            if body:
                body = body[0]

            if hasattr(body, 'xpath'):
                # remove <img> tags with empty src elements
                bad = []
                for x in XPath('//h:img')(body):
                    src = x.get('src', '').strip()
                    if src in ('', '#') or src.startswith('http:'):
                        bad.append(x)
                for img in bad:
                    img.getparent().remove(img)

                # Add id attribute to <a> tags that have name
                for x in XPath('//h:a[@name]')(body):
                    if not x.get('id', False):
                        x.set('id', x.get('name'))

                # Replace <br> that are children of <body> as ADE doesn't handle them
                for br in XPath('./h:br')(body):
                    if br.getparent() is None:
                        continue
                    try:
                        prior = br.itersiblings(preceding=True).next()
                        priortag = barename(prior.tag)
                        priortext = prior.tail
                    except:
                        priortag = 'body'
                        priortext = body.text
                    if priortext:
                        priortext = priortext.strip()
                    br.tag = XHTML('p')
                    br.text = u'\u00a0'
                    style = br.get('style', '').split(';')
                    style = filter(None, map(lambda x: x.strip(), style))
                    style.append('margin:0pt; border:0pt')
                    # If the prior tag is a block (including a <br> we replaced)
                    # then this <br> replacement should have a 1-line height.
                    # Otherwise it should have no height.
                    if not priortext and priortag in block_level_tags:
                        style.append('height:1em')
                    else:
                        style.append('height:0pt')
                    br.set('style', '; '.join(style))

            for tag in XPath('//h:embed')(root):
                tag.getparent().remove(tag)
            for tag in XPath('//h:object')(root):
                if tag.get('type', '').lower().strip() in ('image/svg+xml',):
                    continue
                tag.getparent().remove(tag)

            for tag in XPath('//h:title|//h:style')(root):
                if not tag.text:
                    tag.getparent().remove(tag)
            for tag in XPath('//h:script')(root):
                if (not tag.text and not tag.get('src', False) and
                        tag.get('type', None) != 'text/x-mathjax-config'):
                    tag.getparent().remove(tag)
            for tag in XPath('//h:body/descendant::h:script')(root):
                tag.getparent().remove(tag)

            formchildren = XPath('./h:input|./h:button|./h:textarea|'
                    './h:label|./h:fieldset|./h:legend')
            for tag in XPath('//h:form')(root):
                if formchildren(tag):
                    tag.getparent().remove(tag)
                else:
                    # Not a real form
                    tag.tag = XHTML('div')

            for tag in XPath('//h:center')(root):
                tag.tag = XHTML('div')
                tag.set('style', 'text-align:center')
            # ADE can't handle &amp; in an img url
            for tag in XPath('//h:img[@src]')(root):
                tag.set('src', tag.get('src', '').replace('&', ''))

            # ADE whimpers in fright when it encounters a <td> outside a
            # <table>
            in_table = XPath('ancestor::h:table')
            for tag in XPath('//h:td|//h:tr|//h:th')(root):
                if not in_table(tag):
                    tag.tag = XHTML('div')

            special_chars = re.compile(u'[\u200b\u00ad]')
            for elem in root.iterdescendants():
                if getattr(elem, 'text', False):
                    elem.text = special_chars.sub('', elem.text)
                    elem.text = elem.text.replace(u'\u2011', '-')
                if getattr(elem, 'tail', False):
                    elem.tail = special_chars.sub('', elem.tail)
                    elem.tail = elem.tail.replace(u'\u2011', '-')

            if stylesheet is not None:
                # ADE doesn't render lists correctly if they have left margins
                from cssutils.css import CSSRule
                for lb in XPath('//h:ul[@class]|//h:ol[@class]')(root):
                    sel = '.'+lb.get('class')
                    for rule in stylesheet.data.cssRules.rulesOfType(CSSRule.STYLE_RULE):
                        if sel == rule.selectorList.selectorText:
                            rule.style.removeProperty('margin-left')
                            # padding-left breaks rendering in webkit and gecko
                            rule.style.removeProperty('padding-left')
                # Change whitespace:pre to pre-wrap to accommodate readers that
                # cannot scroll horizontally
                for rule in stylesheet.data.cssRules.rulesOfType(CSSRule.STYLE_RULE):
                    style = rule.style
                    ws = style.getPropertyValue('white-space')
                    if ws == 'pre':
                        style.setProperty('white-space', 'pre-wrap')

    # }}}

    def workaround_sony_quirks(self): # {{{
        '''
        Perform toc link transforms to alleviate slow loading.
        '''
        from calibre.ebooks.oeb.base import urldefrag, XPath

        def frag_is_at_top(root, frag):
            body = XPath('//h:body')(root)
            if body:
                body = body[0]
            else:
                return False
            tree = body.getroottree()
            elem = XPath('//*[@id="%s" or @name="%s"]'%(frag, frag))(root)
            if elem:
                elem = elem[0]
            else:
                return False
            path = tree.getpath(elem)
            for el in body.iterdescendants():
                epath = tree.getpath(el)
                if epath == path:
                    break
                if el.text and el.text.strip():
                    return False
                if not path.startswith(epath):
                    # Only check tail of non-parent elements
                    if el.tail and el.tail.strip():
                        return False
            return True

        def simplify_toc_entry(toc):
            if toc.href:
                href, frag = urldefrag(toc.href)
                if frag:
                    for x in self.oeb.spine:
                        if x.href == href:
                            if frag_is_at_top(x.data, frag):
                                self.log.debug('Removing anchor from TOC href:',
                                        href+'#'+frag)
                                toc.href = href
                            break
            for x in toc:
                simplify_toc_entry(x)

        if self.oeb.toc:
            simplify_toc_entry(self.oeb.toc)

    # }}}

