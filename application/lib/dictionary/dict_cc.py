#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#dict.cc查词接口，基于 <https://github.com/rbaron/dict.cc.py> 修改
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from urlopener import UrlOpener

AVAILABLE_LANGUAGES = {
    "en": "english",
    "de": "german",
    "fr": "french",
    "sv": "swedish",
    "no": "norwegian (bokmål)",
    "es": "spanish",
    "nl": "dutch",
    "bg": "bulgarian",
    "ro": "romanian",
    "it": "italian",
    "pt": "portuguese",
    "ru": "russian"
}


class UnavailableLanguageError(Exception):
    def __str__(self):
        return "Languages have to be in the following list: {}".format(
            ", ".join(AVAILABLE_LANGUAGES.keys()))


class Result(object):
    def __init__(self, from_lang=None, to_lang=None, translation_tuples=None):
        self.from_lang = from_lang
        self.to_lang = to_lang
        self.translation_tuples = list(translation_tuples) \
                                  if translation_tuples else []

    @property
    def n_results(self):
        return len(self.translation_tuples)


class DictCc:
    name = "dict.cc"
    #词典列表，键为词典缩写，值为词典描述
    databases = {"en": "English",
        "de": "German",
        "fr": "French",
        "sv": "Swedish",
        "no": "Norwegian",
        "es": "Spanish",
        "nl": "Dutch",
        "bg": "Bulgarian",
        "ro": "Romanian",
        "it": "Italian",
        "pt": "Portuguese",
        "ru": "Russian",
        "sk": "Slovak",
        "is": "Icelandic",
        "hu": "Hungarian",
        "pl": "Polish",
        "fi": "Finnish",
        "sq": "Albanian",
        "da": "Danish",
        "cs": "Czech",
        "hr": "Croatian",
        "la": "Latin",
        "eo": "Esperanto",
        "sr": "Serbian",
        "bs": "Bosnian",
        "tr": "Turkish",
        "el": "Greek",
    }

    def __init__(self, database='', host=None):
        if database not in self.databases:
            default_log.warning(f'Database "{database}" not exists, fallback to "english"')
            database = 'en'
        self.database = database
        self.destLang = self.databases[database]
        self.host = 'dict.cc'
        self.opener = UrlOpener()

    #返回当前使用的词典名字
    def __repr__(self):
        return f'dict.cc [{self.database}]'
        
    def definition(self, word, language=''):
        word = word.strip()
        if language not in self.databases:
            default_log.info(f'Database "{language}" not exists, fallback to "english"')
            language = 'en'
        if language == self.database:
            raise Exception(f'The source and destination languages cannot be the same: {language}.')
        url = f"https://{language}{self.database}.dict.cc"
        resp = self.opener.open(url, data={"s": word.encode("utf-8")})
        if resp.status_code == 200:
            return self.parse_resp(resp.text)
        else:
            return f'Error: {self.opener.CodeMap(resp.status_code)}'

    def parse_resp(self, text):
        soup = BeautifulSoup(text, "lxml")
        trans = list(soup.find_all('td', attrs={'class': 'td7nl', 'dir': 'ltr'}))
        if len(trans) >= 2:
            langs = [e.get_text() for e in soup.find_all('td', attrs={'class': 'td2', 'dir': 'ltr'})]
            if len(langs) != 2:
                raise Exception("dict.cc results page layout change, please raise an issue.")

            #只返回目标语种的解释，源语种和目标语种一左一右间隔分布
            startIdx = 0 if self.destLang in langs[0] else 1
            ret = []
            for td in trans[startIdx::2]:
                ret.append(' '.join([item.get_text() for item in td.find_all(["a", "var"])]))
            if len(ret) > 1:
                return ('<ul style="text-align:left;list-style-position:inside;">' + 
                    ''.join([f'<li>{e}</li>' for e in ret]) + '</ul>')
            else:
                return ''.join(ret)
        else:
            return ''
