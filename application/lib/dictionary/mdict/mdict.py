#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#mdx离线词典接口
import os
from bs4 import BeautifulSoup
from application.utils import xml_escape
from .readmdict import MDX
try:
    import marisa_trie
except:
    marisa_trie = None

#获取本地的mdx文件列表，只有列表，没有校验是否有效
def getMDictFileList():
    dictDir = os.environ.get('DICTIONARY_DIR')
    if not dictDir or not os.path.exists(dictDir):
        return {}

    ret = {}
    for dirPath, _, fileNames in os.walk(dictDir):
        for fileName in fileNames:
            if fileName.endswith('.mdx'):
                dictName = os.path.splitext(fileName)[0]
                #为了界面显示和其他dict的一致，键为词典路径，值为词典名字（和惯例相反~）
                ret[os.path.join(dirPath, fileName)] = dictName
    return ret

class MDict:
    name = "mdict"
    #词典列表，键为词典缩写，值为词典描述
    databases = getMDictFileList()

    #更新词典列表
    @classmethod
    def refresh(cls):
        cls.databases = getMDictFileList()

    def __init__(self, database='', host=None):
        self.database = database
        self.dictionary = None
        if database in self.databases:
            try:
                self.dictionary = IndexedMdx(database)
            except Exception as e:
                default_log.warning(f'Instantiate mdict failed: {self.databases[database]}: {e}')
        else:
            default_log.warning(f'dict not found: {self.databases[database]}')

    #返回当前使用的词典名字
    def __repr__(self):
        return 'mdict [{}]'.format(self.databases.get(self.database, ''))
        
    def definition(self, word, language=''):
        return self.dictionary.get(word) if self.dictionary else ''

#经过词典树缓存的Mdx
class IndexedMdx:
    TRIE_FMT = '>LLLLL'

    #fname: mdx文件全路径名
    def __init__(self, fname, encoding="", substyle=False, passcode=None):
        self.mdxFilename = fname
        prefix = os.path.splitext(fname)[0]
        dictName = os.path.basename(prefix)
        trieName = f'{prefix}.trie'
        self.trie = None
        self.mdx = MDX(fname, encoding, substyle, passcode)
        if os.path.exists(trieName):
            try:
                self.trie = marisa_trie.RecordTrie(self.TRIE_FMT) #type:ignore
                self.trie.load(trieName)
            except Exception as e:
                self.trie = None
                default_log.warning(f'Failed to load mdict trie data: {dictName}: {e}')

        if self.trie:
            return

        #重建索引
        #为什么不使用单独的后台任务自动重建索引？是因为运行时间还不是最重要的约束，而是服务器内存
        #如果是大词典，内存可能要爆，怎么运行都不行，如果是小词典，则时间可以接受
        default_log.info(f"Building trie for {dictName}")
        #为了能制作大词典，mdx中这些数据都是64bit的，但是为了节省空间，这里只使用32bit保存
        self.trie = marisa_trie.RecordTrie(self.TRIE_FMT, self.mdx.get_index()) #type:ignore
        self.trie.save(trieName)
        
        del self.trie
        self.trie = marisa_trie.RecordTrie(self.TRIE_FMT) #type:ignore
        self.trie.load(trieName)
        import gc
        gc.collect()

    #获取单词释义，不存在则返回空串
    def get(self, word):
        if not self.trie:
            return ''
        word = word.lower().strip()
        #和mdict官方应用一样，输入:about返回词典基本信息
        if word == ':about':
            return self.dict_html_info()

        indexes = self.trie[word] if word in self.trie else None
        ret = self.get_content_by_Index(indexes)
        if ret.startswith('@@@LINK='):
            word = ret[8:].strip()
            if word:
                indexes = self.trie[word] if word in self.trie else None
                ret = self.get_content_by_Index(indexes)
        return ret
        
    def __contains__(self, word) -> bool:
        return word.lower() in self.trie

    #通过单词的索引数据，直接读取文件对应的数据块返回释义
    #indexes是列表，因为可能有多个单词条目
    def get_content_by_Index(self, indexes):
        return self.post_process(self.mdx.get_content_by_Index(indexes))
        
    #对查词结果进行后处理
    def post_process(self, content):
        if not content:
            return ''

        soup = BeautifulSoup(content, 'html.parser') #html.parser不会自动添加html/body

        #浏览器不支持 entry:// 协议，会直接拦截导致无法跳转，
        #预先将其转换为 https://kindleear/entry/ 前缀，然后在js里面判断这个前缀
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            if href.startswith('entry://'):
                tag['href'] = f'https://kindleear/entry/{href[8:]}'

        #kindle对html支持很差，有一些词典又使用到这些标签
        for tag in soup.find_all(['article', 'aside', 'header', 'footer', 'nav', 'main',
            'figcaption', 'figure', 'section', 'time']):
            tag.name = 'div'

        #删除多媒体资源和脚本
        for tag in list(soup.find_all(['head', 'img', 'script', 'base', 'iframe', 'canvas', 'embed', 'source',
            'command', 'datalist', 'video', 'audio', 'noscript', 'meta', 'button'])):
            tag.extract()
        
        self.adjust_css(soup)
        self.justify_css_path(soup)
        #self.remove_empty_tags(soup)
        #self.convert_dict_tag(soup)

        #mdict质量良莠不齐，有些词典在html/body外写释义
        #所以不能直接提取body内容
        for name in ('html', 'body'):
            tag = soup.find(name)
            if tag:
                tag.unwrap()
        
        return str(soup)

    #调整一些CSS
    def adjust_css(self, soup):
        #删除 height 属性
        for element in soup.find_all():
            if element.has_attr('height'):
                del element['height']
            if element.has_attr('style'):
                existing = element.get('style', '')
                newStyle = dict(item.split(":") for item in existing.split(";") if item)
                if 'height' in newStyle:
                    del newStyle['height']
                element['style'] = "; ".join(f"{k}: {v}" for k, v in newStyle.items())

    def justify_css_path(self, soup):
        dictDir = os.environ.get('DICTIONARY_DIR')
        if not dictDir or not os.path.exists(dictDir):
            return

        link = soup.find('link', attrs={'rel': 'stylesheet', 'href': True})
        if link:
            mdxDir = os.path.dirname(self.mdxFilename)
            cssFile = os.path.join(mdxDir, link['href'])
            newHref = os.path.relpath(cssFile, dictDir)
            link['href'] = '/reader/css/' + newHref.replace('\\', '/')

    #将外部单独css文件的样式内联到html标签中，现在不使用了，直接修改css链接
    def inline_css(self, soup):
        link = soup.find('link', attrs={'rel': 'stylesheet', 'href': True})
        if not link:
            return

        link.extract()
        cssPath = os.path.join(os.path.dirname(self.mdxFilename), link['href'])  # type: ignore
        if not os.path.exists(cssPath):
            return
        try:
            with open(cssPath, 'r', encoding='utf-8') as f:
                css = f.read().strip()
        except:
            return

        import css_parser #大部分词典都没有外挂css，可以尽量晚的引入css_parser
        parser = css_parser.CSSParser()
        try:
            stylesheet = parser.parseString(css)
            cssRules = list(stylesheet.cssRules)
        except Exception as e:
            default_log.warning(f'parse css failed: {self.mdxFilename}: {e}')
            return

        parsed = {}
        for rule in cssRules:
            if rule.type == rule.STYLE_RULE:
                #css_parser对伪元素支持不好，要去掉
                selectors = [item.strip() for item in rule.selectorText.split(',') 
                    if (':' not in item) and item.strip()]
                styles = {}
                for style in rule.style:
                    if style.name != 'height':
                        styles[style.name] = style.value
                for selector in selectors:
                    parsed[selector] = styles

        def apply_styles(tag, styles):
            existing = tag.get('style', '')
            newStyle = dict(item.split(":") for item in existing.split(";") if item)
            newStyle.update(styles)
            tag['style'] = ";".join(f"{k}:{v}" for k, v in newStyle.items())

        for tag in soup.find_all(True):
            tagStyles = parsed.get(tag.name, {})
            classStyles = {}
            if tag.has_attr('class'):
                for item in tag['class']:
                    classStyles.update(parsed.get(f'.{item}', {}))

            idStyles = parsed.get(f'#{tag["id"]}', {}) if tag.has_attr('id') else {}
            apply_styles(tag, {**tagStyles, **classStyles, **idStyles})

    #删除空白元素
    def remove_empty_tags(self, soup, preserve_tags=None):
        if preserve_tags is None:
            preserve_tags = {"img", "hr"}

        empty_tags = []
        for tag in soup.find_all():
            if tag.name not in preserve_tags and not tag.get_text().strip():
                empty_tags.append(tag)
            else:
                self.remove_empty_tags(tag, preserve_tags)
        for tag in empty_tags:
            tag.decompose()

    #返回当前词典的基本信息，html格式
    def dict_html_info(self):
        ret = []
        header = self.mdx.header.copy()
        ret.append('<strong>{}</strong><hr/>'.format(header.pop('Title', '')))
        ret.append('<b>Description:</b><br/>{}<br/><hr/>'.format(header.pop('Description', '')))
        stylesheet = xml_escape(header.pop('StyleSheet', '').replace('\n', '\\n'))
        for k,v in header.items():
            ret.append('<b>{}:</b>&nbsp;&nbsp;{}<br/>'.format(k, v))
        ret.append('<b>StyleSheet:</b>{}<br/>'.format(stylesheet))
        return ''.join(ret)
