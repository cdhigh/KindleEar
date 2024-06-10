#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#dict.org查词接口
import re
from .dictclient import Connection, Database

class DictOrg:
    name = "dict.org"
    #词典列表，键为词典缩写，值为词典描述
    databases = {"!": "First match",
        "gcide": "The Collaborative International Dictionary of English v.0.48",
        "wn": "WordNet (r) 3.0 (2006)",
        "moby-thesaurus": "Moby Thesaurus II by Grady Ward, 1.0",
        "elements": "The Elements (07Nov00)",
        "vera": "V.E.R.A. -- Virtual Entity of Relevant Acronyms (February 2016)",
        "jargon": "The Jargon File (version 4.4.7, 29 Dec 2003)",
        "foldoc": "The Free On-line Dictionary of Computing (30 December 2018)",
        "easton": "Easton's 1897 Bible Dictionary",
        "hitchcock": "Hitchcock's Bible Names Dictionary (late 1800's)",
        "bouvier": "Bouvier's Law Dictionary, Revised 6th Ed (1856)",
        "devil": "The Devil's Dictionary (1881-1906)",
        "world02": "CIA World Factbook 2002",
        "gaz2k-counties": "U.S. Gazetteer Counties (2000)",
        "gaz2k-places": "U.S. Gazetteer Places (2000)",
        "gaz2k-zips": "U.S. Gazetteer Zip Code Tabulation Areas (2000)",
        "fd-hrv-eng": "Croatian-English FreeDict Dictionary ver. 0.1.2",
        "fd-fin-por": "suomi-português FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-fin-bul": "suomi-български език FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-fra-bul": "français-български език FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-deu-swe": "Deutsch-Svenska FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-fin-swe": "suomi-Svenska FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-jpn-rus": "Japanese-Russian FreeDict Dictionary ver. 0.1",
        "fd-wol-fra": "Wolof - French FreeDict dictionary ver. 0.1",
        "fd-fra-pol": "français-język polski FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-deu": "English-German FreeDict Dictionary ver. 0.3.7",
        "fd-deu-nld": "German-Dutch FreeDict Dictionary ver. 0.1.4",
        "fd-por-eng": "Portuguese-English FreeDict Dictionary ver. 0.2",
        "fd-spa-deu": "Spanish-German FreeDict Dictionary ver. 0.1",
        "fd-ces-eng": "Czech-English FreeDict Dictionary ver. 0.2.3",
        "fd-swe-fin": "Svenska-suomi FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-pol": "English - Polish Piotrowski+Saloni/FreeDict dictionary ver. 0.2",
        "fd-pol-nor": "język polski-Norsk FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-rom": "English-Romanian FreeDict Dictionary ver. 0.6.3",
        "fd-eng-fra": "English-French FreeDict Dictionary ver. 0.1.6",
        "fd-fin-ell": "suomi-ελληνικά FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-lit": "English-Lithuanian FreeDict Dictionary ver. 0.7.2",
        "fd-ckb-kmr": "Sorani-Kurmanji Ferheng/FreeDict Dictionary ver. 0.2",
        "fd-ita-eng": "Italian-English FreeDict Dictionary ver. 0.2",
        "fd-pol-eng": "język polski-English FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-gle-eng": "Irish-English FreeDict Dictionary ver. 0.2",
        "fd-eng-tur": "English-Turkish FreeDict Dictionary ver. 0.3",
        "fd-gle-pol": "Irish-Polish FreeDict Dictionary ver. 0.1.2",
        "fd-pol-deu": "język polski-Deutsch FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-fra-spa": "français-español FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-lit-eng": "Lithuanian-English FreeDict Dictionary ver. 0.7.2",
        "fd-eng-jpn": "English-日本語 (にほんご) FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-ara-eng": "Arabic-English FreeDict Dictionary ver. 0.6.3",
        "fd-nld-ita": "Nederlands-italiano FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-lat": "English-Latin FreeDict Dictionary ver. 0.1.2",
        "fd-eng-hun": "English-Hungarian FreeDict Dictionary ver. 0.2.1",
        "fd-ita-jpn": "italiano-日本語 (にほんご) FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-dan-eng": "Danish-English FreeDict Dictionary ver. 0.2.2",
        "fd-hun-eng": "Hungarian-English FreeDict Dictionary ver. 0.4.1",
        "fd-pol-gle": "Polish-Irish FreeDict Dictionary ver. 0.1.2",
        "fd-fra-fin": "français-suomi FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-nld-swe": "Nederlands-Svenska FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-nld-eng": "Dutch-English Freedict Dictionary ver. 0.2",
        "fd-deu-kur": "German-Kurdish Ferheng/FreeDict Dictionary ver. 0.2.2",
        "fd-deu-spa": "Deutsch-español FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-afr": "English-Afrikaans FreeDict Dictionary ver. 0.1.3",
        "fd-eng-swe": "English-Swedish FreeDict Dictionary ver. 0.2",
        "fd-jpn-deu": "Japanese-German FreeDict Dictionary ver. 0.2.0",
        "fd-epo-eng": "Esperanto-English FreeDict dictionary ver. 1.0.1",
        "fd-pol-nld": "język polski-Nederlands FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-lat-deu": "Lateinisch-Deutsch FreeDict-Wörterbuch ver. 1.0.3",
        "fd-eng-cym": "Eurfa Saesneg, English-Welsh Eurfa/Freedict dictionary ver. 0.2.3",
        "fd-por-spa": "português-español FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-spa": "English-Spanish FreeDict Dictionary ver. 0.3",
        "fd-swe-tur": "Svenska-Türkçe FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-tur-eng": "Turkish-English FreeDict Dictionary ver. 0.3",
        "fd-tur-deu": "Turkish-German FreeDict Dictionary ver. 0.2",
        "fd-pol-fra": "język polski-français FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-por": "English-Portuguese FreeDict Dictionary ver. 0.3",
        "fd-ita-pol": "italiano-język polski FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-ces": "English-Czech dicts.info/FreeDict Dictionary ver. 0.1.3",
        "fd-deu-tur": "German-Turkish Ferheng/FreeDict Dictionary ver. 0.2.2",
        "fd-fra-jpn": "français-日本語 (にほんご) FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-cym-eng": "Eurfa Cymraeg, Welsh-English Eurfa/Freedict dictionary ver. 0.2.3",
        "fd-bre-fra": "Breton-French FreeDict Dictionary (Geriadur Tomaz) ver. 0.8.3",
        "fd-jpn-fra": "Japanese-French FreeDict Dictionary ver. 0.1",
        "fd-nld-deu": "Dutch-German FreeDict Dictionary ver. 0.2",
        "fd-eng-nld": "English-Dutch FreeDict Dictionary ver. 0.2",
        "fd-deu-por": "German-Portuguese FreeDict Dictionary ver. 0.2.2",
        "fd-eng-hrv": "English-Croatian FreeDict Dictionary ver. 0.2.2",
        "fd-mkd-bul": "Macedonian - Bulgarian FreeDict Dictionary ver. 0.1.1",
        "fd-swe-eng": "Swedish-English FreeDict Dictionary ver. 0.2",
        "fd-pol-spa": "język polski-español FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-jpn-eng": "Japanese-English FreeDict Dictionary ver. 0.1",
        "fd-eng-ell": "English - Modern Greek XDXF/FreeDict dictionary ver. 0.1.1",
        "fd-ita-por": "italiano-português FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-pol-swe": "język polski-Svenska FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-pol-fin": "język polski-suomi FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-kur-tur": "Kurdish-Turkish Ferheng/FreeDict Dictionary ver. 0.1.2",
        "fd-ita-swe": "italiano-Svenska FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-swh": "English-Swahili xFried/FreeDict Dictionary ver. 0.2.2",
        "fd-kha-eng": "Khasi-English FreeDict Dictionary ver. 0.2.2",
        "fd-fin-eng": "suomi-English FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-hin": "English-Hindi FreeDict Dictionary ver. 1.6",
        "fd-spa-eng": "Spanish-English FreeDict Dictionary ver. 0.3",
        "fd-afr-eng": "Afrikaans-English FreeDict Dictionary ver. 0.2.2",
        "fd-ita-fin": "italiano-suomi FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-fin": "English-suomi FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-fra-ita": "français-italiano FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-deu-rus": "Deutsch-Русский FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-deu-bul": "Deutsch-български език FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-deu-pol": "Deutsch-język polski FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-srp-eng": "Serbian - English FreeDict Dictionary ver. 0.2",
        "fd-kur-deu": "Kurdish-German Ferheng/FreeDict Dictionary ver. 0.1.2",
        "fd-spa-por": "Spanish-Portuguese FreeDict Dictionary ver. 0.2.1",
        "fd-swe-pol": "Svenska-język polski FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-swe-rus": "Svenska-Русский FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-nld-spa": "Nederlands-español FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-swh-pol": "Swahili-Polish SSSP/FreeDict Dictionary ver. 0.2.3",
        "fd-oci-cat": "Lenga d'òc - Català FreeDict Dictionary ver. 0.1.1",
        "fd-ita-rus": "italiano-Русский FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-fra-ell": "français-ελληνικά FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-srp": "English-Serbian FreeDict Dictionary ver. 0.1.3",
        "fd-fra-tur": "français-Türkçe FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-fra-eng": "French-English FreeDict Dictionary ver. 0.4.1",
        "fd-ita-ell": "italiano-ελληνικά FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-kur-eng": "Kurdish-English Ferheng/FreeDict Dictionary ver. 1.2",
        "fd-swe-deu": "Svenska-Deutsch FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-swe-fra": "Svenska-français FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-swe-lat": "Svenska-latine FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-swe-ell": "Svenska-ελληνικά FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-eng-rus": "English-Russian FreeDict Dictionary ver. 0.3.1",
        "fd-pol-por": "język polski-português FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-gla-deu": "Scottish Gaelic-German FreeDict Dictionary ver. 0.2",
        "fd-eng-ita": "English-Italian FreeDict Dictionary ver. 0.1.2",
        "fd-pol-ita": "język polski-italiano FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-fra-swe": "français-Svenska FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-isl-eng": "íslenska - English FreeDict Dictionary ver. 0.1.1",
        "fd-swe-spa": "Svenska-español FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-nno-nob": "Norwegian Nynorsk-Norwegian Bokmål FreeDict Dictionary ver. 0.1.1",
        "fd-swe-ita": "Svenska-italiano FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-fra-deu": "français-Deutsch FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-fin-ita": "suomi-italiano FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-nld-fra": "Nederlands-French FreeDict Dictionary ver. 0.2",
        "fd-eng-ara": "English-Arabic FreeDict Dictionary ver. 0.6.3",
        "fd-slk-eng": "Slovak-English FreeDict Dictionary ver. 0.2.1",
        "fd-fra-por": "français-português FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-spa-ast": "Spanish - Asturian FreeDict Dictionary ver. 0.1.1",
        "fd-fin-jpn": "suomi-日本語 (にほんご) FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-deu-ita": "German-Italian FreeDict Dictionary ver. 0.2",
        "fd-swh-eng": "Swahili-English xFried/FreeDict Dictionary ver. 0.4.4",
        "fd-fin-nor": "suomi-Norsk FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-fra-nld": "French-Dutch FreeDict Dictionary ver. 0.2",
        "fd-lat-eng": "Latin-English FreeDict Dictionary ver. 0.1.2",
        "fd-eng-bul": "English-български език FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-deu-fra": "Deutsch-français FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-swe-bul": "Svenska-български език FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-deu-eng": "German-English FreeDict Dictionary ver. 0.3.5",
        "fd-pol-rus": "język polski-Русский FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-ita-deu": "Italian-German FreeDict Dictionary ver. 0.2",
        "fd-eng-gle": "English-Irish FreeDict Dictionary ver. 0.3.2",
        "fd-swe-por": "Svenska-português FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-afr-deu": "Afrikaans-German FreeDict Dictionary ver. 0.3.2",
        "fd-por-deu": "Portuguese-German FreeDict Dictionary ver. 0.2",
        "fd-fra-bre": "French-Breton FreeDict Dictionary (Geriadur Tomaz) ver. 0.2.7",
        "fd-san-deu": "Sanskrit-German FreeDict Dictionary ver. 0.2.2",
        "fd-kha-deu": "Khasi - German FreeDict Dictionary ver. 0.1.3",
        "fd-fra-rus": "français-Русский FreeDict+WikDict dictionary ver. 2018.09.13",
        "fd-pol-ell": "język polski-ελληνικά FreeDict+WikDict dictionary ver. 2018.09.13",
        "english": "English Monolingual Dictionaries",
        "trans": "Translating Dictionaries",
        "all": "All Dictionaries (English-Only and Translating)",
    }

    #'*' - all result, '!' - only the first result, others - database name
    def __init__(self, database='!', host=None):
        if database not in self.databases:
            default_log.warning(f'Database "{database}" not exists, fallback to "First match"')
            database = '!'
        self.database = database
        self.host = 'dict.org'
        self.con = Connection(self.host)
        self.db = Database(self.con, database)

    #返回当前使用的词典名字
    def __repr__(self):
        return 'dict.org [{}]'.format(self.databases.get(self.database, ''))

    #查词，language - word的语种
    def definition(self, word, language=''):
        defs = self.db.define(word)
        ret = '\n'.join([item.getdefstr() for item in defs])
        ret = self.convert_to_ipa(ret) #转换音标格式
        return re.sub(r'\{(\w+)\}', r'<i>\1</i>', ret) #转换同义词为斜体

    #转换为ipa音标格式
    def convert_to_ipa(self, txt):
        #重音符号
        syllable = {'*': 'ˈ', '"': 'ˌ'}
        pattern = r'(?P<start>[^\\]*?)\\(?P<phon>[a-zA-Z`"\*=\^\.\[\]]+)\\(?P<rest>.*)'
        match = re.match(pattern, txt, re.M|re.S)
        if match:
            start = match.group('start')
            phon = match.group('phon')
            rest = match.group('rest')
            for k,v in syllable.items():
                phon = phon.replace(k, v)
            txt = f'{start}/{phon}/{rest}'

        #音标符号
        phonetic = {'[a^]': 'æ', '[e^]': 'ɛ', '[u^]': 'ʌ', '[.a]': 'ə', '[y^]': 'ɪ', '[i^]': 'i',
            '[oo^]': 'uː', '[~e]': 'ə', '[o^]': 'ɔ', '[=a]': 'eɪ', '[th]': 'ð', '[=e]': 'iː', '[=u]': 'juː',
            '[ng]': 'ŋ', '[aum]': 'ɔː', '[-o]': 'oʊ', "['e]": 'e', '[=o]': 'oʊ', '[^o]': 'ɔ',
            '[imac]': 'aɪ', '[-e]': 'iː', '[add]': 'ɔː', '[asl]': 'æ', '[^e]': 'ɪ', '[=ae]': 'eɪ',
            '[ae]': 'æ', '[ˌo]': 'əʊ', '[-u]': 'u', '[thorn]': 'θ', '[eth]': 'ð'}
        
        pattern = re.compile('|'.join(re.escape(key) for key in phonetic.keys()))
        return pattern.sub(lambda x: phonetic[x.group()], txt)


