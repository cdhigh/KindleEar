#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Merriam-Webster <https://www.merriam-webster.com/> 查词接口
#现在直接解析网页获取释义，尽管有其网站API有每天1000条免费额度，但是需要使用者申请开发者账号，提高了使用门槛
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
        #self.pat1 = re.compile(br'<(head|script|style|svg|footer|header)\b[^<]*(?:(?!</\1>)<[^<]*)*</\1>', re.IGNORECASE)
        #self.pat2 = re.compile(br'[\s\r\n]+<')
        #self.pat3 = re.compile(br'>[\s\r\n]+')
        self.sylPat1 = re.compile(br'<span class="word-syllables-entry.*?">(.*?)</span>', re.DOTALL)
        self.sylPat2 = re.compile(br'<span class="prons-entries-list-inline.*?">(.*?)</span>', re.DOTALL)
        self.removePat = re.compile(br'<[^>]+>')
        self.dtPat = re.compile(br'<span class="dt.*?">(.*?)</span>', re.DOTALL)

    #返回当前使用的词典名字
    def __repr__(self):
        return "webster's [English]"
        
    def definition(self, word, language=''):
        word = word.strip()
        resp = self.opener.open(f'{self.host}/dictionary/{word}')
        if resp.status_code == 200:
            return self._fetchDefinition(resp.content)
        else:
            return f'Error: {self.opener.CodeMap(resp.status_code)}'

    #使用最简单的字符串搜索，快，但是没有任何鲁棒性，网站随便修改一点代码可能就会失效，反正以后再说
    def _fetchDefinition(self, content):
        ret = []
        match = self.sylPat1.search(content)
        if match:
            syl = match.group(1).decode('utf-8').replace('\n', '').strip()
            if syl:
                ret.append(f'<span>/{syl}/</span>')
        match = self.sylPat2.search(content)
        if match:
            #去掉所有标签，仅保留文本内容
            syl = self.removePat.sub(b'', match.group(1)).decode('utf-8').replace('\n', '').strip()
            if syl:
                ret.append(f'<span style="margin-left:20px">[{syl}]</span>')
        matches = self.dtPat.findall(content)
        if matches:
            ret.append('<ul style="text-align:left;list-style-position:inside;">')
            for match in matches: #去掉所有标签，仅保留文本内容
                dt = self.removePat.sub(b'', match).decode('utf-8').replace('\n', '').lstrip(': ').strip()
                if dt:
                    ret.append(f'<li>{dt}</li>')
            ret.append('</ul')
        return ''.join(ret)

    #从网页中获取简短释义(因为网页内容太庞杂，导致解释时间过长，已废弃)
    def _fetchDefinition1(self, content):
        #因为网页内容太庞杂，BeautifulSoup解释耗时太久，使用正则先去掉一些内容
        #同时内容不太规范，如果直接使用lxml经常导致获取不到释义
        content = re.sub(self.pat1, b'', content)
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
