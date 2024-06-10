#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Merriam-Webster <https://www.merriam-webster.com/> 查词接口
import re
from bs4 import BeautifulSoup
from urlopener import UrlOpener

class MerriamWebster:
    name = "webster's"
    #词典列表，键为词典缩写，值为词典描述
    databases = {"english": "Webster's New International Dictionary"}

    def __init__(self, database='', host=None):
        self.database = database
        self.host = 'https://www.merriam-webster.com'
        self.opener = UrlOpener(host=self.host)
        self.pat1 = re.compile(br'<(head|script|style|svg|footer|header)\b[^<]*(?:(?!</\1>)<[^<]*)*</\1>', re.IGNORECASE)
        self.pat2 = re.compile(br'[\s\r\n]+<')
        self.pat3 = re.compile(br'>[\s\r\n]+')

    #返回当前使用的词典名字
    def __repr__(self):
        return "webster's [English]"
        
    def definition(self, word, language=''):
        resp = self.opener.open(f'{self.host}/dictionary/{word}')
        if resp.status_code == 200:
            #因为网页内容太庞杂，BeautifulSoup解释耗时太久，使用正则先去掉一些内容
            #同时内容不太规范，如果直接使用lxml经常导致获取不到释义
            content = re.sub(self.pat1, b'', resp.content)
            content = re.sub(self.pat2, b'<', content)
            content = re.sub(self.pat3, b'>', content)
            soup = BeautifulSoup(content, 'lxml')
            ret = []
            phonetic = soup.find('span', {'class': 'word-syllables-entry'})
            if phonetic:
                ret.append('<span>/' + phonetic.get_text() + '/</span>')
            phonetic = soup.find('span', {'class': 'prons-entries-list-inline'})
            if phonetic:
                ret.append('<span style="margin-left:20px">[' + phonetic.get_text().strip() + ']</span>')
            ret.append('<ul style="text-align:left;list-style-position:inside;">')
            hasDef = False
            for definition in soup.find_all("span", {"class" : "dt"}):
                tag = definition.findChild()
                if tag:
                    ret.append('<li>' + tag.get_text().lstrip(' :') + '</li>')
                    hasDef = True
            if hasDef:
                ret.append('</ul>')
                return ''.join(ret)
            else:
                return ''
        else:
            return f'Error: {self.opener.CodeMap(resp.status_code)}'
