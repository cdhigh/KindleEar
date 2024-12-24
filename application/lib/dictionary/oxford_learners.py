#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Oxford Advanced Learner's Dictionary <https://www.oxfordlearnersdictionaries.com/> 查词接口
#现在直接解析网页获取释义，尽管有其网站API有每天1000条免费额度，但是需要使用者申请开发者账号，提高了使用门槛
from bs4 import BeautifulSoup
from urlopener import UrlOpener

class OxfordLearners:
    name = "oxford's"
    mode = "online"
    #词典列表，键为词典缩写，值为词典描述
    databases = {"learner": "Advanced Learner's Dictionary",
        "advanced": "Advanced American Dictionary"}

    urls = {"learner": "https://www.oxfordlearnersdictionaries.com/definition/english/",
        "advanced": "https://www.oxfordlearnersdictionaries.com/definition/american_english/"}

    def __init__(self, database='', host=None):
        if database not in self.databases:
            database = 'learner'
        self.database = database
        self.host = self.urls.get(database, "https://www.oxfordlearnersdictionaries.com/definition/english/")
        self.opener = UrlOpener(host=self.host)
        
    #返回当前使用的词典名字
    def __repr__(self):
        return f"oxford's [{self.databases.get(self.database)}]"
        
    def definition(self, word, language=''):
        word = word.lower().strip()
        resp = self.opener.open(f'{self.host}{word}')
        status_code = resp.status_code
        if status_code == 200:
            return self._fetchDefinition(resp.content)
        elif status_code == 404:
            return ''
        else:
            return f'Error: {self.opener.CodeMap(status_code)}'

    #从网页中获取简短释义
    def _fetchDefinition(self, content):
        soup = BeautifulSoup(content, 'lxml')
        ret = []
        for phon in soup.find_all('span', {'class': 'phon'}):
            ret.append('<span style="margin-right:20px">' + phon.get_text().replace('//', '/') + '</span>')
            if len(ret) >= 2: #如果有很多发音的话，取前两个即可
                break

        infle = soup.find('div', {'class': 'inflections'})
        if infle:
            ret.append('<span style="margin-left:20px">[' + infle.get_text().strip() + ']</span>')
        
        ret.append('<ul style="text-align:left;list-style-position:inside;">')
        for definition in soup.find_all("span", {"class" : "def"}):
            ret.append('<li>' + definition.get_text().strip() + '</li>')
        ret.append('</ul>')
        return ''.join(ret)
