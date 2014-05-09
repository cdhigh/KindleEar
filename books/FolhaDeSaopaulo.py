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
    oldest_article        = 1
    fulltext_by_readability = False
    fulltext_by_instapaper = False
    host = r'http://www.folha.uol.com.br/'
    keep_only_tags = [dict(name='article', attrs={'class':'news'})]
    remove_classes = ['toolbar','advertising']
    
    feeds = [
            (u'Em cima da hora', u'http://feeds.folha.uol.com.br/emcimadahora/rss091.xml'),
            (u'Cotidiano', u'http://feeds.folha.uol.com.br/folha/cotidiano/rss091.xml'),
            (u'Brasil', u'http://feeds.folha.uol.com.br/folha/brasil/rss091.xml'),
            (u'Mundo', u'http://feeds.folha.uol.com.br/mundo/rss091.xml'),
            (u'Poder', u'http://feeds.folha.uol.com.br/poder/rss091.xml'),
            (u'Mercado', u'http://feeds.folha.uol.com.br/folha/dinheiro/rss091.xml'),
            (u'Saber', u'http://feeds.folha.uol.com.br/folha/educacao/rss091.xml'),
            (u'Tec', u'http://feeds.folha.uol.com.br/folha/informatica/rss091.xml'),
            (u'Ilustrada', u'http://feeds.folha.uol.com.br/folha/ilustrada/rss091.xml'),
            #(u'Ambiente', u'http://feeds.folha.uol.com.br/ambiente/rss091.xml'),
            #(u'Bichos', u'http://feeds.folha.uol.com.br/bichos/rss091.xml'),
            (u'Ciencia', u'http://feeds.folha.uol.com.br/ciencia/rss091.xml'),
            (u'Equilibrio e Saude', u'http://feeds.folha.uol.com.br/equilibrioesaude/rss091.xml'),
            #(u'Turismo', u'http://feeds.folha.uol.com.br/folha/turismo/rss091.xml'),
            #(u'Esporte', u'http://feeds.folha.uol.com.br/folha/esporte/rss091.xml'),
           ]
    
    #def fetcharticle(self, url, opener, decoder):
    #    url = 'http://tools.folha.com.br/print?url=' + url
    #    return BaseFeedBook.fetcharticle(self, url, opener, decoder)
        
    def processtitle(self, title):
        pn = re.compile(r'^(.*?) - \d\d/\d\d/\d\d\d\d - .*? - (Folha de S\.Paulo|F5)$', re.I)
        mt = pn.match(title)
        if mt:
            title = mt.group(1)
        elif title.endswith('Folha de S.Paulo'):
            title = title.replace('Folha de S.Paulo', '')
        return title
    