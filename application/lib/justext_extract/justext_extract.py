#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
Hack jusText库，提取网页文章正文，支持保留文章结构和图像文件
Author: cdhigh <https://github.com/cdhigh>
"""
from operator import itemgetter
import os, re, lxml, pkgutil
from lxml.builder import E
import justext
from justext import core as justext_core

OrgParagraph = justext_core.Paragraph

#Hack start
class CJKParagraph(justext_core.Paragraph):
    #中文词的平均长度为2，日语韩语的平均长度为2-3
    #这里只需要统计意义即可
    @property
    def words_count(self):
        return len(self.text)
    def stopwords_count(self, stopwords):
        text = self.text
        cnt = sum((text.count(stopword) for stopword in stopwords))
        return cnt
        
class KeepImagesMaker(justext_core.ParagraphMaker):
    def startElementNS(self, name, qname, attrs):
        ns, localname = name
        if localname == 'img' and attrs.get((ns, 'src')):
            self.path.append(localname)
            self._start_new_pragraph() #save prev tag
            self.paragraph.append_text(attrs.get((ns, 'src'))) #type:ignore
            self._start_new_pragraph() #end img tag here
            self.path.pop()
        else:
            return super().startElementNS(name, qname, attrs)

    def endElementNS(self, name, qname):
        if name[1] != 'img':
            return super().endElementNS(name, qname)

justext_core.ParagraphMaker = KeepImagesMaker

#Hack end
JT_CJK_STOP_LANGCODES = {
    'zh': 'chinese_simplified',
    'zh-tw': 'chinese_traditional',
    'zh-hant': 'chinese_traditional',
    'zh-hk': 'chinese_traditional',
    'zh-mo': 'chinese_traditional',
    'ja': 'japanese',
    'ko': 'korean',
}

JT_STOP_LANGCODES = {
    'af': 'Afrikaans',
    'sq': 'Albanian',
    'ar': 'Arabic',
    'an': 'Aragonese',
    'hy': 'Armenian',
    'rup': 'Aromanian',
    'ast': 'Asturian',
    'az': 'Azerbaijani',
    'eu': 'Basque',
    'be': 'Belarusian',
    'be-tarask': 'Belarusian_Taraskievica',
    'bn': 'Bengali',
    'bpy': 'Bishnupriya_Manipuri',
    'bs': 'Bosnian',
    'br': 'Breton',
    'bg': 'Bulgarian',
    'ca': 'Catalan',
    'ceb': 'Cebuano',
    'cv': 'Chuvash',
    'hr': 'Croatian',
    'cs': 'Czech',
    'da': 'Danish',
    'nl': 'Dutch',
    'en': 'English',
    'eo': 'Esperanto',
    'et': 'Estonian',
    'fi': 'Finnish',
    'fr': 'French',
    'gl': 'Galician',
    'ka': 'Georgian',
    'de': 'German',
    'el': 'Greek',
    'gu': 'Gujarati',
    'ht': 'Haitian',
    'he': 'Hebrew',
    'hi': 'Hindi',
    'hu': 'Hungarian',
    'is': 'Icelandic',
    'io': 'Ido',
    'ig': 'Igbo',
    'id': 'Indonesian',
    'ga': 'Irish',
    'it': 'Italian',
    'jv': 'Javanese',
    'kn': 'Kannada',
    'kk': 'Kazakh',
    'ko': 'Korean',
    'ku': 'Kurdish',
    'ky': 'Kyrgyz',
    'la': 'Latin',
    'lv': 'Latvian',
    'lt': 'Lithuanian',
    'lmo': 'Lombard',
    'nds': 'Low_Saxon',
    'lb': 'Luxembourgish',
    'mk': 'Macedonian',
    'ms': 'Malay',
    'ml': 'Malayalam',
    'mt': 'Maltese',
    'mr': 'Marathi',
    'nap': 'Neapolitan',
    'ne': 'Nepali',
    'new': 'Newar',
    'nb': 'Norwegian_Bokmal',
    'nn': 'Norwegian_Nynorsk',
    'oc': 'Occitan',
    'fa': 'Persian',
    'pms': 'Piedmontese',
    'pl': 'Polish',
    'pt': 'Portuguese',
    'qu': 'Quechua',
    'ro': 'Romanian',
    'ru': 'Russian',
    'bat': 'Samogitian',
    'sr': 'Serbian',
    'sh': 'Serbo_Croatian',
    'scn': 'Sicilian',
    'simple': 'Simple_English',
    'sk': 'Slovak',
    'sl': 'Slovenian',
    'es': 'Spanish',
    'su': 'Sundanese',
    'sw': 'Swahili',
    'sv': 'Swedish',
    'tl': 'Tagalog',
    'ta': 'Tamil',
    'te': 'Telugu',
    'tr': 'Turkish',
    'tk': 'Turkmen',
    'uk': 'Ukrainian',
    'ur': 'Urdu',
    'uz': 'Uzbek',
    'vi': 'Vietnamese',
    'vo': 'Volapuk',
    'wa': 'Walloon',
    'war': 'Waray_Waray',
    'cy': 'Welsh',
    'pa': 'Western_Panjabi',
    'fy': 'West_Frisian',
    'yo': 'Yoruba'
}

#根据 XPath 创建节点并确保层级正确
def create_node_at_path(root, xpath, content):
    # 去掉 /html[1]/body[1]/ 前缀
    cleaned_xpath = re.sub(r'^/html\[\d+\]/body\[\d+\]/', '', xpath)
    path_parts = cleaned_xpath.strip('/').split('/')
    current = root
    
    tag = ''
    for part in path_parts:
        tag = part.split('[')[0]
        index = int(part.split('[')[1].rstrip(']'))
        children = current.findall(tag)
        while len(children) < index:
            new_elem = E(tag)
            current.append(new_elem)
            children = current.findall(tag)
        current = children[index - 1]
    
    if tag == 'img':
        current.attrib['src'] = content
    else:
        current.text = content
    return current

#递归删除空标签
def remove_empty_tags(element):
    for child in list(element):
        if child.tag == 'img':
            continue
        remove_empty_tags(child)
        if len(child) == 0 and (child.text is None or not child.text.strip()):
            element.remove(child)

#创建一个HTML格式的调试输出文件，用来可视化和调试各种参数
#保存在justext_extract库的debug子目录（需要js/css）
def makeDebugOutput(paragraphs, stoplist, url, filename=''):
    html = ["<html>\n<head>",
        "<meta http-equiv=\"Content-Type\" content=\"text/html charset=utf-8\" />",
        "<link rel=\"stylesheet\" type=\"text/css\" href=\"css/style.css\" />",
        "<script type=\"text/javascript\" src=\"https://code.jquery.com/jquery-1.8.3.min.js\"></script>",
        "<script type=\"text/javascript\" src=\"js/jquery.qtip.min.js\"></script>",
        "<script type=\"text/javascript\" src=\"js/tooltip.js\"></script>",
        "<title>jusText debug</title>",
        "</head><body>",
        f"original page: <a href=\"{url}\">{url}</a>",
        "<div id=\"output_wrapper\">"]
    params = ["details = ["]
    for i, pg in enumerate(paragraphs):
        currClass = pg.class_type
        if not currClass:
            currClass = pg.cf_class

        if i != 0:
            params.append(",")
        params.append(f"{{id: 'pd{i}', parameters:{{")
        params.append(f"final_class:'{currClass}',")
        params.append(f" context_free_class:'{pg.cf_class}',")
        params.append(f" heading:'{pg.is_heading}',")
        params.append(f" length: {len(pg)},")
        params.append(f" characters_within_links: {pg.chars_count_in_links},")
        params.append(f" link_density:'{pg.links_density()}',")
        params.append(f" number_of_words: {pg.words_count},")
        params.append(f" number_of_stopwords: {pg.stopwords_count(stoplist)},")
        params.append(f" stopword_density: '{pg.stopwords_density(stoplist)}',")
        params.append(f"   dom:'...{pg.dom_path[-20:]}',")
        params.append(f" other:'{i}. paragraph',")
        params.append(" reason: ''}}")
        html.append(f"<p class=\"{currClass}\" qtip-content=\"pd{i}\">{pg.text}</p>")
    
    params.append(" ];")
    html.append(f"<script>{''.join(params)}</script>")
    html.append("</div><br/><br/><br/><br/><br/><br/><br/><br/><br/></html>")
    debugDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug')
    #避免不小心万一设置了debug一直没有取消，情理过期文件，保留最多30个调试文件
    debugFiles = sorted([(item, os.path.getmtime(os.path.join(debugDir, item))) 
        for item in os.listdir(debugDir)], key=itemgetter(1))
    for item in debugFiles[:-30]:
        try:
            os.remove(os.path.join(debugDir, item[0]))
        except:
            pass
    
    if not filename:
        filename = url[-20:].replace('/', '_').replace(':', '_').strip() + '.html'
    filename = os.path.join(debugDir, filename)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(''.join(html))

#获取CJK的停用词列表
def get_cjkstoplist(language):
    basename = JT_CJK_STOP_LANGCODES.get(language, '')
    if not basename:
        basename = JT_CJK_STOP_LANGCODES.get(language.split('-')[0], '')
    file_path = os.path.join("stoplists", f'{basename}.txt')
    try:
        stopwords = pkgutil.get_data("justext_extract", file_path)
    except IOError:
        raise ValueError(f"Stoplist for language '{language}' is missing.")

    return frozenset(w.decode("utf8").lower() for w in stopwords.splitlines()) #type:ignore

#使用justext进行文章正文提取
def justext_extract(html: str, language='', url='', debug=False):
    language = (language or '').replace('_', '-').lower()
    #中日韩语单独处理
    if any(language.startswith(item) for item in ('zh', 'ja', 'ko')):
        justext_core.Paragraph = CJKParagraph
        stopList = get_cjkstoplist(language)
        params = {'length_low': 30, 'length_high': 100, 'stopwords_low': 0.05, 'stopwords_high': 0.15}
    else:
        justext_core.Paragraph = OrgParagraph
        stopFile = JT_STOP_LANGCODES.get(language, '')
        if not stopFile:
            stopFile = JT_STOP_LANGCODES.get(language.split('-')[0], 'Simple_English')
        stopList = justext.get_stoplist(stopFile)
        params = {'length_low': 70, 'length_high': 150, 'stopwords_low': 0.30, 'stopwords_high': 0.32}

    paragraphs = justext.justext(html, stopList, **params)
    if debug:
        makeDebugOutput(paragraphs, stopList, url)
    data = [(pg.xpath, pg.text) for pg in paragraphs if not pg.is_boilerplate]

    #重建html结构
    root = E.html(E.body())
    body = root.find('body')
    for xpath, content in data:
        create_node_at_path(body, xpath, content)

    #增加备用算法提示
    new_elem = E('p', style='color:#555555;font-size:60%;text-align:right;')
    new_elem.text = 'Extracted by alternative algorithm.'
    body.append(new_elem)
    
    remove_empty_tags(root)
    #pretty_print=True
    return lxml.etree.tostring(root, encoding='unicode', method='html') #type:ignore
