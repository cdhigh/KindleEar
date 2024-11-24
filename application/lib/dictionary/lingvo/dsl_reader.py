#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#dsl离线词典支持，不支持dsl.dz，即使使用indexed_gzip还是慢，建议先解压为dsl再使用
#Author: cdhigh <https://github.com/cdhigh>
import os, re, logging, io
import chardet

try:
    import marisa_trie
except:
    marisa_trie = None

#外部接口
class DslReader:
    TRIE_FMT = '>LH' #释义开始位置，释义块字数

    def __init__(self, fileName):
        self.log = logging.getLogger()
        self.fileName = fileName
        self.encoding = None
        firstPart = os.path.splitext(fileName)[0]
        self.trieFileName = firstPart + '.trie'
        self.encFileName = firstPart + '.enc'
        self.trie = None

        if os.path.isfile(self.encFileName):
            with open(self.encFileName, 'r', encoding='utf-8') as f:
                self.encoding = f.read().strip()

        if os.path.isfile(self.trieFileName):
            try:
                self.trie = marisa_trie.RecordTrie(self.TRIE_FMT) #type:ignore
                self.trie.load(self.trieFileName)
            except Exception as e:
                self.trie = None
                self.log.warning(f'Failed to load dsldict trie data: {fileName}: {e}')

        if self.trie:
            return

        #分析索引数据，构建前缀树
        self.log.info(f"Building trie for {fileName}")
        self.buildTrie()

    #分析索引数据，构建前缀树
    #代码简单点，全部读入内存
    def buildTrie(self):
        f = self.openDslFile()
        encoding = self.encoding
        records = []
        currWord = ''
        meanStart = None
        meanWordCnt = 0
        while True:
            line = f.readline()
            if line.startswith(('#', r'{{', '\n', '\r')):
                meanWordCnt += len(line)
                continue

            if not line: #文件结束
                if currWord and meanStart is not None:
                    records.append((currWord, (meanStart, min(meanWordCnt, 65000))))
                break
            
            #开始一个词条
            if not line.startswith((' ', '\t')):
                if currWord and meanStart is not None:
                    #保存前词条的偏移位置
                    records.append((currWord, (meanStart, min(meanWordCnt, 65000))))
                    meanStart = None

                currWord = line.strip()
                if meanStart is None:
                    meanStart = f.tell() #f.tell()特别慢，要等到需要的时候才调用
                meanWordCnt = 0
            else: #有缩进，是释义块
                meanWordCnt += len(line)

        f.close()
        self.trie = marisa_trie.RecordTrie(self.TRIE_FMT, records) #type:ignore
        self.trie.save(self.trieFileName)
        del records
        del self.trie
        self.trie = marisa_trie.RecordTrie(self.TRIE_FMT) #type:ignore
        self.trie.load(self.trieFileName)
    
    #打开文件，返回文件实例
    def openDslFile(self):
        if not self.encoding: #检测编码，因为很多词典不按官方的要求使用unicode
            import chardet
            with open(self.fileName, 'rb') as f:
                data = f.read(10000)
            ret = chardet.detect(data)
            encoding = ret['encoding'] if ret['confidence'] >= 0.8 else None

            #逐一测试
            if not encoding:
                for enc in ['utf-16', 'utf-16-le', 'windows-1252']:
                    try:
                        with open(self.fileName, 'r', encoding=enc) as f:
                            f.readline()
                        encoding = enc
                        break
                    except UnicodeError:
                        pass

            self.encoding = (encoding or 'utf-16').lower()
            with open(self.encFileName, 'w', encoding='utf-8') as fEnc:
                fEnc.write(self.encoding)

        return open(self.fileName, 'r', encoding=self.encoding)

    #查词接口
    def get(self, word, default=''): #type:ignore
        for wd in [word, word.lower(), word.capitalize(), word.upper()]:
            if wd in self.trie:
                break
        else:
            return default

        start, size = self.trie[wd][0]
        lines = []
        with self.openDslFile() as f:
            f.seek(start)
            lines = f.read(size).splitlines()
        mean = '\n'.join([line for line in lines if line.startswith((' ', '\t'))])
        return self.dslMeanToHtml(mean)

    #将原始释义转换为合法的html文本
    def dslMeanToHtml(self, mean):
        simpleTags = {"[']": '<u>', "[/']": '</u>', '[b]': '<b>', '[/b]': '</b>', '[i]': '<i>', 
            '[/i]': '</i>', '[u]': '<u>', '[/u]': '</u>',  '[sub]': '<sub>', '[/sub]': '</sub>',
            '[sup]': '<sup>', '[/sup]': '</sup>', '[/c]': '</span>', '@': '<br/>', '\t': '',
            '[*]': '<span>', '[/*]': '</span>', '\\[': '[', '\\]': ']', '\n': '<br/>',
            '[ex]': '<span style="color:#808080">', '[/ex]': '</span>',
            '[p]': '<i style="color:#008000">', '[/p]': '</i>',
            '[url]': '<span style="color:#0000ff;text-decoration:underline">', '[/url]': '</span>',
            '[ref]': '<span style="color:#0000ff;text-decoration:underline">', '[/ref]': '</span>',}
        removeTags = ['[/m]', '[com]', '[/com]', '[trn]', '[/trn]', '[trs]',
            '[/trs]', '[!trn]', '[/!trn]', '[!trs]', '[/!trs]', '[/lang]']
        
        #print(mean) #TODO
        for tag, repl in simpleTags.items():
            mean = mean.replace(tag, repl)
        for tag in removeTags:
            mean = mean.replace(tag, '')

        # 替换[m]，根据匹配内容生成相应数量的空格
        mean = re.sub(r'\[m\d+?\]', lambda match: '&nbsp;' * int(match.group(0)[2:-1]), mean)
        mean = re.sub(r'\[c.*?\]', '<span style="color:#006400">', mean)
        #浏览器不支持 entry:// 协议，会直接拦截导致无法跳转，
        mean = re.sub(r'\[lang.*?\]', '', mean)
        mean = re.sub(r'\[s\].*?\[/s\]', '', mean)
        mean = re.sub(r'<<(.*?)>>', r'<a href="https://kindleear/entry/\1">\1</a>', mean)
        #print(mean) #TODO
        return mean
