#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# 调用在线翻译服务，翻译html文件，移植了calibre的 Ebook Translator 插件的在线翻译接口实现
import re, time, copy
from bs4 import BeautifulSoup, NavigableString, Tag
from ebook_translator.engines import *
from application.ke_utils import loc_exc_pos

DEBUG_SPLITED_TRANS_SOUP = False #是否保存分割后的soup，用于调试优化

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
    #常见的基本不影响布局的行内元素标签集合
    INLINE_TAGS = {'a', 'abbr', 'b', 'bdo', 'cite', 'dfn', 'em', 'i', 'img', 'kbd', 'mark', 
        'q', 's', 'samp', 'small', 'span', 'strong', 'sub', 'sup', 'u', 'var', 'wbr'}

    #不需要翻译的标签
    NO_TRANS_TAGS = {'pre', 'code', 'abbr', 'style', 'script', 'textarea', 'input', 'select',
        'link', 'img', 'option', 'datalist'}

    def __init__(self, params: dict, thread_num: int=1):
        #params.setdefault('stream', False)
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
        interval = self.translator.request_interval
        for idx, item in enumerate(data, 1):
            text = item['text']
            item['error'] = ''
            item['translated'] = ''
            if text:
                try:
                    item['translated'] = self.translator.translate(text) #type:ignore
                except:
                    msg = loc_exc_pos('translate_text failed')
                    default_log.warning(msg)
                    item['error'] = msg
            else:
                item['error'] = _('The input text is empty')
            ret.append(item)
            #if (idx < count) and (interval > 0.01):
            #最后一个请求还是需要延时，否则下一篇文章的首次请求可能失败
            if interval > 0.01:
                time.sleep(interval)

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
        self.debugSave(soup, elements)
        for idx, (tag, text, needTrans) in enumerate(elements, 1):
            try:
                if needTrans and not DEBUG_SPLITED_TRANS_SOUP:
                    trans = self.translator.translate(text)
                else:
                    trans = text
                if trans:
                    self.add_translation_soup(soup, tag, trans, self.dst)
                    success += 1
                else:
                    failed += 1
            except:
                default_log.warning(loc_exc_pos('translate_soup failed'))
                failed += 1
            if (idx < count) and (self.translator.request_interval > 0.01):
                time.sleep(self.translator.request_interval)
        return (success, failed)

    #提取soup包含文本的节点，返回一个列表 [(tag, text),...]
    def extract_soup_text(self, soup):
        elements = []
        maxLen = self.translator.max_len_per_request

        #内嵌递归函数：用于遍历BeautifulSoup元素的所有子节点并提取文本内容
        #tag: 开始的BeautifulSoup元素
        #position: 翻译后的文本显示的位置
        #返回: [(tag, text, needTrans),]
        def _extract(tag, position):
            for child in tag.find_all(recursive=False):
                #跳过AI自动生成的摘要
                if isinstance(child, Tag) and 'ai_generated_summary' in child.get('class', []):
                    continue

                needTrans = getattr(child, 'name', None) not in self.NO_TRANS_TAGS
                if self._contains_text(child):
                    if needTrans:
                        if position == 'replace':
                            text = str(child).strip()
                            text = re.sub(r'<a\b[^>]*>(.*?)</a>', r'<u>\1</u>', text) #去掉超链接
                        else:
                            text = child.get_text().strip()
                        if text and (self._tag_has_only_text(child) or (len(text) < maxLen)):
                            elements.append((child, text, needTrans))
                            continue
                    elif position == 'replace': #只有替代译文才保留不需要翻译的段落，其他情况使用原段落
                        elements.append((child, str(child).strip(), needTrans))
                        continue
                
                _extract(child, position)

        position = self.params.get('position', 'below')
        _extract(soup.body, position)
        return elements

    #确定soup节点是否直接包含文本元素
    def _contains_text(self, tag):
        #以下几个条件任意一个
        #1. 文本节点
        #2. p/table元素
        #3. 没有子节点
        tagName = getattr(tag, 'name', None)
        if isinstance(tag, NavigableString) or (tagName in ('p', 'table')) or (tag.string is not None):
            return True

        #4. 有直接的裸文本节点，之前在创建soup时已经去除了回车换行，这里文本节点就是文本内容
        if [x for x in tag.children if isinstance(x, NavigableString)]:
            return True

        #5. div内部只有行内元素
        if (tagName == 'div') and self._all_inline_elements(tag):
            return True

        return False

    #一个节点内是否只有行内元素
    def _all_inline_elements(self, tag):
        for elem in tag.descendants:
            if isinstance(elem, Tag) and elem.name not in self.INLINE_TAGS:
                return False
        return True

    #判断节点没有子标签节点，只有文本或链接
    def _tag_has_only_text(self, tag):
        if isinstance(tag, NavigableString):
            return True
        return all(isinstance(e, NavigableString) or (getattr(e, 'name', None) == 'a')
            for e in tag.children)

    #将翻译结果添加到DOM树
    #tag: 原文的tag
    #trans: 译文文本字符串
    #dst: 目标语种代码
    def add_translation_soup(self, soup, tag, trans, dst):
        position = self.params.get('position', 'below')
        origStyle = self.params.get('orig_style', '')
        transStyle = self.params.get('trans_style', '')
        trans = trans.replace('&lt;', '<').replace('&gt;', '>').replace('< /', '</')

        #内嵌函数，将一个纯文本包裹在一个html标签中，返回新标签对象
        def _wrapPureString(tagName, txt):
            if tagName in ('title', 'tr', 'td', 'th', 'thead', 'tbody', 'table', 'ul', 'ol', 'li', 'a'):
                tagName = 'span'
            newTag = soup.new_tag(tagName)
            newTag.string = str(txt)
            return newTag

        #有效的html文本
        if '<' in trans and '>' in trans:
            transSoup = BeautifulSoup(trans, 'html.parser') #'html.parser'解析器不会自动添加<html><body>
            transTag = transSoup.contents[0] if transSoup.contents else trans
        else:
            transTag = _wrapPureString(tag.name, trans)

        if isinstance(transTag, (str, NavigableString)):
            transTag = _wrapPureString(tag.name, transTag)

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

    #将soup文本分割提取的内容保存到文件，用于调试优化
    def debugSave(self, soup, elements):
        if not DEBUG_SPLITED_TRANS_SOUP:
            return

        import os
        fileName = os.path.join(os.path.dirname(__file__), 'debug_trans_soup.html')
        mode = 'a' if os.path.isfile(fileName) and os.path.getsize(fileName) < 500000 else 'w'
        with open(fileName, mode, encoding='utf-8') as f:
            f.write('TITLE: {}\n'.format(soup.find('title').string))
            for tag, text, needTrans in elements:
                f.write(tag.prettify())
                if needTrans:
                    f.write('T-------------------------\n')
                else:
                    f.write('N-------------------------\n')
                f.write(text)
                f.write('\n========================================================\n\n')
