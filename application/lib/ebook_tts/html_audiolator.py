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
            'languages': engine.languages, 'engine_url': engine.engine_url,
            'region_url': engine.region_url, 'voice_url': engine.voice_url, 
            'language_url': engine.language_url, 'regions': engine.regions}
    return info

class HtmlAudiolator:
    def __init__(self, params: dict):
        self.params = params
        self.engineName = self.params.get('engine')
        self.language = self.params.get('language', 'en')
        self.audiolator = builtin_tts_engines.get(self.engineName, GoogleWebTTSFree)(params)
        
    #语音化文本，注意文本不要太长，一般几百个字符以内
    #data: 文本/字典/列表 {'text': text, ...}, [{},{}]
    #返回：{'mime':, 'audio': , 'text':, ..., 'error':,}
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
        for idx, item in enumerate(data, 1):
            text = item['text']
            item['error'] = ''
            item['audio'] = ''
            item['mime'] = ''
            if text:
                try:
                    item['mime'], item['audio'] = self.audiolator.tts(text)
                except Exception as e:
                    default_log.warning('audiofy_text failed: ' + str(e))
                    item['error'] = str(e)
            else:
                item['error'] = _('The input text is empty')
            ret.append(item)
            if (idx < count) and (self.audiolator.request_interval > 0.01):
                time.sleep(self.audiolator.request_interval)

        if retList:
            return ret
        elif ret:
            return ret[0]
        else:
            return {'error': 'unknown error', 'audio': '', 'mime':'', 'text': ''}

    #语音化BeautifulSoup实例，返回 {'error':, 'mime':, 'audio':[], 'texts':[]}
    def audiofy_soup(self, soup):
        ret = {'error': '', 'audios': [], 'mime': '', 'texts':[]}
        texts = self.extract_soup_text(soup)
        if not texts:
            ret['error'] = _('The input text is empty')
            return ret

        try:
            title = soup.find('title').string
        except:
            title = 'Untitled'

        for text in self.split_strings(texts, self.audiolator.max_len_per_request):
            try:
                mime, audio = self.audiolator.tts(text)
                ret['mime'] = ret['mime'] or mime
                if audio:
                    ret['texts'].append(text)
                    ret['audios'].append(audio)
                else:
                    default_log.warning(f'audiofy_soup got empty audio for "{title}": {text[:30]}')
            except Exception as e:
                ret['error'] = str(e)
        return ret

    #提取soup适合语音化的文本，返回文本内容列表
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
        return texts

    #将字符串数组合并或拆分重组为每个字符串不超过max_len的新数组
    def split_strings(self, strings, max_len):
        step1 = []
        current = []
        currLen = 0
        for text in strings: #第一步，先合并短字符串
            thisLen = len(text)
            if current and (currLen + thisLen + 1 >= max_len):
                step1.append(' '.join(current))
                current = [text]
                currLen = thisLen
            else:
                current.append(text)
                currLen += thisLen + 1

        if current:
            step1.append(' '.join(current))

        #第二步，拆分超长字符串
        result = []
        for item in step1:
            if len(item) > max_len + 1: #拆分
                subItems = []
                for line in item.split('\n'): #按照回车进行分割
                    if len(line) > max_len:
                        #再按照空格进行分割
                        words = line.split()
                        current_line = ''
                        current = []
                        currLen = 0
                        for word in words:
                            thisLen = len(word)
                            if current and (currLen + thisLen + 1 >= max_len):
                                subItems.append(' '.join(current))
                                current = [word]
                                currLen = thisLen
                            else:
                                current.append(word)
                                currLen += thisLen + 1
                        if current:
                            subItems.append(' '.join(current))
                    else:
                        subItems.append(line)
                result.extend(subItems)
            else:
                result.append(item)
            
        return result

    