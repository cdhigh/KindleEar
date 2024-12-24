#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#dict.cn查词接口
from bs4 import BeautifulSoup
from urlopener import UrlOpener

class DictCn:
    name = "dict.cn"
    mode = "online"
    #词典列表，键为词典缩写，值为词典描述
    databases = {"english": "English-Chinese Translation Dictionary"}

    def __init__(self, database='!', host=None):
        self.database = database
        self.host = 'https://dict.cn'
        self.opener = UrlOpener(host=self.host)
    
    #返回当前使用的词典名字
    def __repr__(self):
        return 'dict.cn [English-Chinese]'
        
    def definition(self, word, language=''):
        word = word.lower().strip()
        resp = self.opener.open(f'{self.host}/{word}')
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            ret = []
            phonetic = soup.find('div', attrs={'class': 'phonetic'})
            if phonetic:
                for tag in phonetic.find_all('bdo'): #type:ignore
                    tag.name = 'span'
                for tag in phonetic.find_all('i'): #type:ignore
                    tag.extract()
                ret.append(phonetic.decode_contents().replace('\n', '')) #type:ignore
            basic = soup.find(attrs={'class': 'dict-basic-ul'})
            li = basic.find('li') if basic else None
            if li:
                ret.append(li.decode_contents().replace('\n', '')) #type:ignore
            return '<br/>'.join(ret)
        else:
            return f'Error: {self.opener.CodeMap(resp.status_code)}'
