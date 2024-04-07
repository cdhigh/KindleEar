#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# 调用在线翻译服务，翻译html文件，移植了calibre的 Ebook Translator 插件的在线翻译接口实现
import time, copy
from bs4 import BeautifulSoup, NavigableString
from ebook_translator.engines import *

#生成一个当前所有支持的翻译引擎的字典，在网页内使用
def get_trans_engines():
    info = {}
    for engine in builtin_translate_engines:
        info[engine.name] = {'alias': engine.alias, 'need_api_key': engine.need_api_key, 
            'default_api_host': engine.default_api_host, 'api_key_hint': engine.api_key_hint,
            'source': engine.lang_codes.get('source', {}),
            'target': engine.lang_codes.get('target', {}),}
    return info

class HtmlTranslator:
    def __init__(self, params: dict, thread_num: int=1):
        params.setdefault('stream', False)
        self.thread_num = thread_num
        self.params = params
        self.engineName = self.params.get('engine')
        self.src = self.params.get('src_lang', '')
        self.dst = self.params.get('dst_lang', 'en')
        self.translator = self.create_engine(self.engineName, params)
        self.translator.set_source_code(self.src)
        self.translator.set_target_code(self.dst)
        
    def create_engine(self, name, params):
        engines = {engine.name: engine for engine in builtin_translate_engines}
        if name in engines:
            engine_class = engines.get(name)
        else:
            engine_class = GoogleFreeTranslate
        return engine_class(params)

    #翻译文本
    #data: 文本/字典/列表 {'text': text, ...}, [{},{}]
    #返回：{'translated': , 'text':, ..., 'error':,}
    #如果输入是列表，返回也是列表，否则返回字典
    def translate_text(self, data):
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
            item['translated'] = ''
            if text:
                if 1:
                    item['translated'] = self.translator.translate(text)
                    #except Exception as e:
                    #default_log.warning('translate_text() failed: ' + str(e))
                    #item['error'] = str(e)
            else:
                item['error'] = _('The input text is empty')
            ret.append(item)
            if (idx < count - 1) and (self.translator.request_interval > 0.01):
                time.sleep(self.translator.request_interval)

        if retList:
            return ret
        elif ret:
            return ret[0]
        else:
            return {'error': 'unknown error', 'translated': '', 'text': ''}

    #翻译BeautifulSoup实例，直接在soup上修改
    #返回 (translated num, failed num)
    def translate_soup(self, soup):
        success = 0
        failed = 0
        elements = self.extract_soup_text(soup)
        count = len(elements)
        for idx, (tag, text) in enumerate(elements):
            try:
                trans = self.translator.translate(text)
                if trans:
                    self.add_translation_soup(soup, tag, trans, self.dst)
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                default_log.warning('translate_soup failed: ' + str(e))
                failed += 1
            if (idx < count - 1) and (self.translator.request_interval > 0.01):
                time.sleep(self.translator.request_interval)
        return (success, failed)

    #提取soup包含文本的节点，返回一个列表 [(tag, text),...]
    def extract_soup_text(self, soup):
        elements = []

        #确定soup节点是否直接包含文本元素
        def _contains_text(tag):
            if (tag.name == 'table' or tag.string is not None or 
                [x for x in tag.children if isinstance(x, NavigableString) and str(x).strip()]):
                return True
            return False

        #递归函数，用于遍历BeautifulSoup元素的所有子节点并提取文本内容
        def _extract(tag):
            for child in tag.find_all(recursive=False):
                if _contains_text(child):
                    text = str(child).strip()
                    if text and child.name not in ('pre', 'code', 'abbr'):
                        elements.append((child, text))
                else:
                    _extract(child)
        _extract(soup.body)
        return elements

    #将翻译结果添加到DOM树
    #tag: 原文的tag
    #trans: 译文文本字符串
    #dst: 目标语种代码
    def add_translation_soup(self, soup, tag, trans, dst):
        position = self.params.get('position', 'below')
        origStyle = self.params.get('orig_style', '')
        transStyle = self.params.get('trans_style', '')
        trans = trans.replace('&lt;', '<').replace('&gt;', '>')
        transTag = BeautifulSoup(trans, 'html.parser') #'html.parser'解析器不会自动添加<html><body>
        if not transTag.contents:
            return
        transTag = transTag.contents[0]
        if isinstance(transTag, NavigableString):
            oldTxt = str(transTag)
            transTag = soup.new_tag('span')
            transTag.string = oldTxt
        
        if origStyle:
            old = tag.get('style')
            tag['style'] = f'{old};{origStyle}' if old else origStyle
        if transStyle:
            old = transTag.get('style')
            transTag['style'] = f'{old};{transStyle}' if old else transStyle
        transTag['lang'] = dst

        if tag.name == 'title': #title单独处理
            self.add_translation_soup_title(soup, position, tag, transTag)
        elif position == 'below': #翻译字符在原文之下
            if tag.name in ('td', 'th'): #避免把table结构搞乱，提取出里面的字符串
                tag.string = '{}<br/>{}'.format(tag.string or '', transTag.string or '')
            else:
                tag.insert_after(transTag)
        elif position == 'above':
            if tag.name in ('td', 'th'):
                tag.string = '{}<br/>{}'.format(transTag.string or '', tag.string or '')
            else:
                tag.insert_before(transTag)
        elif position in ('left', 'right'):
            self.create_table_soup(soup, position, tag, transTag)
        else: #replace
            tag.replace_with(transTag)

    #实现左右对照翻译，返回一个table tag
    #position: left|right，译文放在左边还是右边
    #tag: 原文的tag
    #transTag: 译文的tag
    def create_table_soup(self, soup, position, tag, transTag):
        column_gap = self.params.get('column_gap', None) or ('percentage', 10)
        unit, value = column_gap
        if unit == 'percentage': #之后的值是表示中间空白宽度的比率
            width = f"{(100 - value) // 2}%"
            midWidth = f"{value}%"
        else: #space_count，表示中间间隔的空格数
            width = '50%'
            midWidth = int(value)

        table = soup.new_tag('table', attrs={'xmlns': 'http://www.w3.org/1999/xhtml', 'width': '100%'})
        tr = soup.new_tag('tr')
        table.append(tr)
        tdLeft = soup.new_tag('td', attrs={'valign': 'top', 'width': width})
        tdRight = soup.new_tag('td', attrs={'valign': 'top', 'width': width})
        tdMid = soup.new_tag('td')
        tr.extend([tdLeft, tdMid, tdRight])
        if isinstance(midWidth, str):
            tdMid['width'] = midWidth
        else:
            tdMid.string = '&nbsp;' * value

        if position == 'left':
            tdLeft.append(transTag)
            tdRight.append(copy.copy(tag))
        if position == 'right':
            tdLeft.append(copy.copy(tag))
            tdRight.append(transTag)
        tag.replace_with(table)

    #html的标题翻译
    #position: 译文放在左边还是右边
    #tag: 原文的tag
    #transTag: 译文的tag
    def add_translation_soup_title(self, soup, position, tag, transTag):
        origTxt = tag.string or ''
        transTxt = transTag.string or ''
        if position in ('below', 'right'):
            tag.string = '{} {}'.format(origTxt, transTxt)
        elif position in ('above', 'left'):
            tag.string = '{} {}'.format(transTxt, origTxt)
        else: #replace
            tag.string = transTxt or origTxt

