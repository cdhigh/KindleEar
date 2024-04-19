#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# 调用在线文本转语音TTS服务，将每个html转换为一个音频文件
import time, copy
from bs4 import BeautifulSoup, NavigableString
from .engines import *

#生成一个当前所有支持的TTS引擎的字典，在网页内使用
def get_tts_engines():
    info = {}
    for name, engine in builtin_tts_engines.items():
        info[name] = {'alias': engine.alias, 'need_api_key': engine.need_api_key, 
            'default_api_host': engine.default_api_host, 'api_key_hint': engine.api_key_hint,
            'languages': engine.languages}
    return info

class HtmlAudiolator:
    def __init__(self, params: dict):
        self.params = params
        self.engineName = self.params.get('engine')
        self.language = self.params.get('language', 'en')
        self.audiolator = builtin_tts_engines.get(self.engineName, GoogleTtsFree)(params)
        
    #翻译文本
    #data: 文本/字典/列表 {'text': text, ...}, [{},{}]
    #返回：{'mime':, 'audiofied': , 'text':, ..., 'error':,}
    #如果输入是列表，返回也是列表，否则返回字典
    def audiofy_text(self, data):
        retList = True
        if isinstance(data, dict):
            data = [data]
            retList = False
        elif not isinstance(data, list):
            data = [{'text': str(data)},]
            retList = False

        count = len(data)
        ret = []
        for idx, item in enumerate(data):
            text = item['text']
            item['error'] = ''
            item['audiofied'] = b''
            item['mime'] = ''
            if text:
                if 1:
                    item['mime'], item['audiofied'] = self.audiolator.tts(text)
                    #except Exception as e:
                    #default_log.warning('audiofy_text failed: ' + str(e))
                    #item['error'] = str(e)
            else:
                item['error'] = _('The input text is empty')
            ret.append(item)
            if (idx < count - 1) and (self.audiolator.request_interval > 0.01):
                time.sleep(self.audiolator.request_interval)

        if retList:
            return ret
        elif ret:
            return ret[0]
        else:
            return {'error': 'unknown error', 'audiofied': b'', 'mime':'', 'text': ''}

    #语音化BeautifulSoup实例，返回 {'error':, 'audiofied':, 'mime':, 'text':}
    def audiofy_soup(self, soup):
        text = self.extract_soup_text(soup)
        ret = {'text': text, 'error': '', 'audiofied': b'', 'mime': ''}
        if text:
            if 1:
                ret['mime'], ret['audiofied'] = self.audiolator.tts(text)
                #except Exception as e:
                #default_log.warning('audiofy_text failed: ' + str(e))
                ret['error'] = str(e)
        else:
            ret['error'] = _('The input text is empty')
        return ret

    #提取soup适合语音化的文本，直接返回文本内容
    def extract_soup_text(self, soup):
        texts = []

        #确定soup节点是否直接包含文本元素
        def _contains_text(tag):
            if (tag.name == 'table' or tag.string is not None or 
                [x for x in tag.children if isinstance(x, NavigableString) and str(x).strip()]):
                return True
            return False

        #递归函数，用于遍历BeautifulSoup元素的所有子节点并提取文本内容
        #黑名单：('pre', 'code', 'abbr', 'style', 'script', 'textarea', 'input', 'select', 'link', 'img', 'button', 'label',
        #'legend', 'optgroup', 'option', 'data', 'time', 'meter', 'progress', 'acronym', 'figure', 'figcaption', 'colgroup', 'col', 'datalist')
        tagWhiteList = ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'span', 'div', 'ul', 'ol', 'li', 
            'strong', 'em', 'b', 'i', 'blockquote', 'cite', 'q', 'address', 'sub', 'sup', 'br', 'hr', 
            'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td')
        def _extract(tag):
            for child in tag.find_all(recursive=False):
                if _contains_text(child):
                    text = child.get_text().strip()
                    if text and child.name in tagWhiteList:
                        texts.append(text)
                else:
                    _extract(child)
        _extract(soup.body)
        return '\n'.join(texts)
