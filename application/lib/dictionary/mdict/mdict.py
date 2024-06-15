#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#mdx离线词典接口
#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#stardict离线词典支持
import os, re, zlib, json
from bs4 import BeautifulSoup
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
                #try:
                self.dictionary = IndexedMdx(database)
                #except Exception as e:
                #default_log.warning(f'Instantiate mdict failed: {self.databases[database]}: {e}')

    #返回当前使用的词典名字
    def __repr__(self):
        return 'mdict [{}]'.format(self.databases.get(self.database, ''))
        
    def definition(self, word, language=''):
        ret = self.dictionary.get(word) if self.dictionary else ''
        if isinstance(ret, bytes):
            ret = ret.decode(self.dictionary.meta.get('encoding', 'utf-8'))
        return ret

#经过词典树缓存的Mdx
class IndexedMdx:
    TRIE_FMT = '>LLLLLL'

    #fname: mdx文件全路径名
    def __init__(self, fname, encoding="", substyle=False, passcode=None):
        self.mdxFilename = fname
        prefix = os.path.splitext(fname)[0]
        dictName = os.path.basename(prefix)
        trieName = f'{prefix}.trie'
        metaName = f'{prefix}.meta'
        self.trie = None
        self.meta = {}
        self.stylesheet = {}
        if os.path.exists(trieName) and os.path.exists(metaName):
            try:
                self.trie = marisa_trie.RecordTrie(self.TRIE_FMT)
                self.trie.load(trieName)
                with open(metaName, 'r', encoding='utf-8') as f:
                    self.meta = json.loads(f.read())
                if not isinstance(self.meta, dict):
                    self.meta = {}
                self.stylesheet = json.loads(self.meta.get("stylesheet", '{}'))
            except Exception as e:
                self.trie = None
                default_log.warning(f'Failed to load mdict trie data: {dictName}: {e}')

        if self.trie and self.meta:
            self.fMdx = open(fname, 'rb')
            return

        #重建索引
        default_log.info(f"Building trie for {dictName}")
        mdx = MDX(fname, encoding, substyle, passcode)
        dictIndex = mdx.get_index()
        indexList = dictIndex["index_dict_list"]
        #[(word, (params,)),...]
        #为了能制作大词典，mdx中这些数据都是64bit的，但是为了节省空间，这里只使用32bit保存(>LLLLLL)
        idxBuff = [(item["key_text"].lower(), (
                item["file_pos"], #32bit
                item["compressed_size"], #64bit
                item["decompressed_size"], #64bit
                item["record_start"], #64bit
                item["record_end"], #64bit
                item["offset"])) #64bit
            for item in indexList]
        self.trie = marisa_trie.RecordTrie(self.TRIE_FMT, idxBuff)
        self.trie.save(trieName)
        self.meta = dictIndex['meta']
        #mdx内嵌css，键为序号(1-255)，值为元祖 (startTag, endTag)
        self.stylesheet = json.loads(self.meta.get("stylesheet", '{}'))
        with open(metaName, 'w', encoding='utf-8') as f:
            f.write(json.dumps(self.meta))

        self.fMdx = open(fname, 'rb')

        del mdx
        del self.trie
        self.trie = marisa_trie.RecordTrie(self.TRIE_FMT)
        self.trie.load(trieName)
        del idxBuff
        import gc
        gc.collect()

    #获取单词释义，不存在则返回空串
    def get(self, word):
        word = word.lower().strip()
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
        if not indexes:
            return ''

        ret = []
        encoding = self.meta.get('encoding', 'utf-8')
        for index in indexes:
            filePos, compSize, decompSize, startPos, endPos, offset = index
            self.fMdx.seek(filePos)
            compressed = self.fMdx.read(compSize)
            type_ = compressed[:4] #32bit-type, 32bit-adler, data
            if type_ == b"\x00\x00\x00\x00":
                data = compressed[8:]
            elif type_ == b"\x01\x00\x00\x00":
                #header = b"\xf0" + pack(">I", decompSize)
                data = lzo.decompress(compressed[8:], initSize=decompSize, blockSize=1308672)
            elif type_ == b"\x02\x00\x00\x00":
                data = zlib.decompress(compressed[8:])
            else:
                continue
            record = data[startPos - offset : endPos - offset]
            ret.append(record.decode(encoding, errors="ignore").strip("\x00"))

        txt = '<hr/>'.join(ret)
        if self.stylesheet:
            txt = self.replace_css(txt)

        #很多人制作的mdx很复杂，可能需要后处理
        return self.post_process(txt)
        
    #对查词结果进行后处理
    def post_process(self, content):
        if not content:
            return ''

        soup = BeautifulSoup(content, 'html.parser') #html.parser不会自动添加body

        #删除图像
        for tag in soup.find_all('img'):
            tag.extract()

        self.inline_css(soup)
        self.remove_empty_tags(soup)

        body = soup.body
        if body:
            body.name = 'div'

        return str(soup)

    #将css样式内联到html标签中
    def inline_css(self, soup):
        # 首先删除 height 属性
        for element in soup.find_all():
            if element.has_attr('height'):
                del element['height']
            if element.has_attr('style'):
                existing = element.get('style', '')
                newStyle = dict(item.split(":") for item in existing.split(";") if item)
                if 'height' in newStyle:
                    del newStyle['height']
                element['style'] = "; ".join(f"{k}: {v}" for k, v in newStyle.items())

        link = soup.find('link', attrs={'rel': 'stylesheet', 'href': True})
        if not link:
            return

        link.extract()
        css = ''
        link = os.path.join(os.path.dirname(self.mdxFilename), link['href']) #type:ignore
        if os.path.exists(link):
            with open(link, 'r', encoding='utf-8') as f:
                css = f.read().strip()

        if not css:
            return

        parsed = {} #css文件的样式字典
        cssRules = []

        import css_parser
        parser = css_parser.CSSParser()
        try:
            stylesheet = parser.parseString(css)
            cssRules = list(stylesheet.cssRules)
        except Exception as e:
            default_log.warning(f'parse css failed: {self.mdxFilename}: {e}')
            return
            
        for rule in cssRules:
            if rule.type == rule.STYLE_RULE:
                selector = rule.selectorText
                if ':' in selector: #伪元素
                    continue
                styles = {}
                for style in rule.style:
                    if style.name != 'height':
                        styles[style.name] = style.value
                parsed[selector] = styles

        #内联样式
        for selector, styles in parsed.items():
            try:
                elements = soup.select(selector)
            except NotImplementedError as e:
                default_log.debug(f"Skipping unsupported selector: {selector}")
                continue
            for element in elements:
                existing = element.get('style', '')
                newStyle = dict(item.split(":") for item in existing.split(";") if item)
                newStyle.update(styles)
                element['style'] = "; ".join(f"{k}: {v}" for k, v in newStyle.items())

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

    #替换css，其实这个不是css，算是一种模板替换，不过都这么叫
    def replace_css(self, txt):
        txt_list = re.split(r"`\d+`", txt)
        txt_tag = re.findall(r"`\d+`", txt)
        txt_styled = txt_list[0]
        for j, p in enumerate(txt_list[1:]):
            style = self.stylesheet[txt_tag[j][1:-1]]
            if p and p[-1] == "\n":
                txt_styled = txt_styled + style[0] + p.rstrip() + style[1] + "\r\n"
            else:
                txt_styled = txt_styled + style[0] + p + style[1]
        return txt_styled
