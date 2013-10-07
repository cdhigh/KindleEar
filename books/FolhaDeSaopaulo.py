#!/usr/bin/env python
# -*- coding:utf-8 -*-

import re
from base import BaseFeedBook

def getBook():
    return FolhaDeSaopaulo

class FolhaDeSaopaulo(BaseFeedBook):
    title                 = 'Folha'
    description           = 'Folha de Sao paulo'
    language = 'pt-br'
    feed_encoding = "ISO-8859-1"
    page_encoding = "ISO-8859-1"
    mastheadfile = "mh_folha.gif"
    coverfile =  'cv_folha.jpg'
    fulltext_by_readability = False
    fulltext_by_instapaper = False
    host = r'http://www.folha.uol.com.br/'
    keep_only_tags = []
    remove_tags = []
    remove_ids = ['articleBy','ad-180x150-1','editing_controls']
    remove_classes = ['adLabel','gallery','mediaIcons','hide','navigation',
                'logo sprite','toolbar','breadcrumb']
    remove_attrs = []
    
    feeds = [
            (u'Em cima da hora', u'http://feeds.folha.uol.com.br/emcimadahora/rss091.xml'),
            #(u'Cotidiano', u'http://feeds.folha.uol.com.br/folha/cotidiano/rss091.xml'),
            (u'Brasil', u'http://feeds.folha.uol.com.br/folha/brasil/rss091.xml'),
            (u'Mundo', u'http://feeds.folha.uol.com.br/mundo/rss091.xml'),
            (u'Poder', u'http://feeds.folha.uol.com.br/poder/rss091.xml'),
            (u'Mercado', u'http://feeds.folha.uol.com.br/folha/dinheiro/rss091.xml'),
            (u'Saber', u'http://feeds.folha.uol.com.br/folha/educacao/rss091.xml'),
            (u'Tec', u'http://feeds.folha.uol.com.br/folha/informatica/rss091.xml'),
            #(u'Ilustrada', u'http://feeds.folha.uol.com.br/folha/ilustrada/rss091.xml'),
            (u'Ambiente', u'http://feeds.folha.uol.com.br/ambiente/rss091.xml'),
            #(u'Bichos', u'http://feeds.folha.uol.com.br/bichos/rss091.xml'),
            (u'Ciencia', u'http://feeds.folha.uol.com.br/ciencia/rss091.xml'),
            #(u'Equilibrio e Saude', u'http://feeds.folha.uol.com.br/equilibrioesaude/rss091.xml'),
            (u'Turismo', u'http://feeds.folha.uol.com.br/folha/turismo/rss091.xml'),
            (u'Esporte', u'http://feeds.folha.uol.com.br/folha/esporte/rss091.xml'),
           ]
           
    def preprocess(self, content):
        astart = content.find("<h1>") # start of article
        if astart > 0:
            aend = content.find('<div id="articleEnd">', astart)
            if aend > 0:
                title = self.FetchTitle(content)
                content = content[astart:aend]
                content = self.FragToXhtml(content, title, self.page_encoding)
        return content
    
    def processtitle(self, title):
        pn = re.compile(r'^(Folha de S\.Paulo|F5) - .+? - (.+?) - \d\d/\d\d/\d\d\d\d$', re.I)
        mt = pn.match(title)
        if mt:
            title = mt.group(2)
        return title
    