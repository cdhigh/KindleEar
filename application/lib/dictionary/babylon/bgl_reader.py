#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""实现BGL格式解析，原型来自：https://github.com/mgreen/bgl-reverse
最大程度的简化以便优化效率
很多bgl的crc校验出错，如果使用gzip库，需要hack代码跳过crc，就会导致只能固定某个python版本
还不如直接使用第三方库 indexed_gzip，它有 skip_crc_check 参数
Author: cdhigh <https://github.com/cdhigh>
"""
import os, io, re, logging
from bs4 import BeautifulSoup
import indexed_gzip
import marisa_trie

#一些常数定义，完整的常数定义在bgl_gls.py里面，拷贝到这里是为了方便单文件测试
PARAMETER = 0
PROPERTY = 3
TERM_1 = 0x1
TERM_A = 0xA
TERM_B = 0xB
RESOURCE = 2
CHARSET = {
    0x41: "cp1252", #Default
    0x42: "ISO-8859-1", #Latin
    0x43: "ISO-8859-2", #Eastern European
    0x44: "cp1251", #Cyriilic
    0x45: "cp932",#Japanese
    0x46: "big5",       #Traditional Chinese
    0x47: "gbk",        #Simplified Chinese
    0x48: "cp1257",     #Baltic
    0x49: "cp1253",     #Greek
    0x4A: "cp949",      #Korean
    0x4B: "ISO-8859-9", #Turkish
    0x4C: "ISO-8859-8", #Hebrew
    0x4D: "cp1256",     #Arabic
    0x4E: "cp874",}     #Thai

P_TITLE = 0x01
P_AUTHOR_NAME = 0x02
P_AUTHOR_EMAIL = 0x03
P_DESCRIPTION = 0x09
P_S_CHARSET = 0x1A
P_T_CHARSET = 0x1B

#特定长度的字节并转换为 big-endian unsigned int
def unpack_uint(data: bytes) -> int:
    return int.from_bytes(data, byteorder='big')

def unpack_block(data: bytes, x: int) -> (bytes, bytes):
    """return a tuple (block_data, unprocessed)"""
    blkLen = int.from_bytes(data[0:x], byteorder='big')
    return data[x: x + blkLen], data[x + blkLen:]

#解析词条块内容，返回 (word, definition)
#wordOnly: 是否只解析单词，跳过释义（节省时间）
def unpack_term(data: bytes, wordOnly=True) -> (bytes, bytes):
    #第一个字节为词条长度
    wordLen = data[0]
    word = data[1: wordLen + 1]
    if wordOnly:
        return word, ''

    #然后两个字节为definition长度
    defiLen = int.from_bytes(data[wordLen + 1: wordLen + 3], byteorder='big')
    definition = data[wordLen + 3: wordLen + 3 + defiLen] #data还剩下一些其他内容，这里不关注了
    
    #根据分隔符0x14，拆分为两部分
    # 找到分隔符 0x14 的位置并切片
    sepIdx = definition.find(0x14)
    if sepIdx != -1:
        definition = definition[:sepIdx]
    return word, definition

#解析词条块类型11内容，返回 (word, definition)
#wordOnly: 是否只解析单词，跳过释义（节省时间）
def unpack_term11(data: bytes, wordOnly=True) -> (bytes, bytes):
    #前5个字节为词条长度
    wordLen = int.from_bytes(data[0: 5], byteorder='big')
    word = data[5: wordLen + 5]
    if wordOnly:
        return word, ''

    pos = wordLen + 5
    #之后是4字节的altsCount长度 data[wordLen + 5: wordLen + 9]
    altsCount = data[pos: pos + 4]
    pos += 4
    for altIndex in range(altsCount):
        #每个alt的长度字段为四个字节
        altLen = int.from_bytes(data[pos: pos + 4], byteorder='big')
        pos += 4
        if not altLen:
            break
        #alt = data[pos: pos + altLen]
        pos += altLen

    #然后4个字节为definition长度
    defiLen = int.from_bytes(data[pos: pos + 4], byteorder='big')
    definition = data[pos + 4: pos + 4 + defiLen] #data还剩下一些其他内容，这里不关注了
    
    #根据分隔符0x14，拆分为两部分
    # 找到分隔符 0x14 的位置并切片
    sepIdx = definition.find(0x14)
    if sepIdx != -1:
        definition = definition[:sepIdx]
    return word, definition

def resilient_decode(data: bytes, encoding: str, fallback: str = 'latin1') -> str:
    """decode data to string with encoding, and try fallback when errors occur"""
    ret = ''
    while len(data) > 0:
        try:
            ret += data.decode(encoding)
            break
        except UnicodeDecodeError as e:
            ret += data[e.start:e.end].decode(fallback)
            data = data[e.end:]
    return ret

#封装类文件对象，读取和移动文件指针都添加一个偏移
class OffsetFileWrapper:
    def __init__(self, fileobj, offset):
        self.fileobj = fileobj
        self.offset = offset
        self.fileobj.seek(offset)
        self.name = fileobj.name

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        if whence == 0:  # 从文件头
            real_offset = self.offset + offset
        elif whence == 1:  # 从当前位置
            real_offset = self.fileobj.tell() + offset
        elif whence == 2:  # 从文件尾
            self.fileobj.seek(0, 2)  # 跳到文件末尾
            real_offset = self.fileobj.tell() + offset
        else:
            raise ValueError("Invalid 'whence' value")
        return self.fileobj.seek(real_offset, 0)

    def tell(self):
        return self.fileobj.tell() - self.offset

    def read(self, size=-1):
        return self.fileobj.read(size)

    def close(self):
        self.fileobj.close()

#表示一个bgl压缩文件
class BglFile(indexed_gzip.IndexedGzipFile):
    def __init__(self, fileName, *args, **kwargs):
        self.bglFileName = fileName
        self.args = args
        self.kwargs = kwargs
        self.reset(initialized=False)

    #跳过自定义文件头
    @staticmethod
    def gzHeaderOffset(fileobj):
        header = fileobj.read(4)
        if header != b'\x12\x34\x00\x01' and header != b'\x12\x34\x00\x02':
            raise IOError("invald header: {0:#x}".format(header))
        offset = int.from_bytes(fileobj.read(2), byteorder='big')
        #print(f'Position of gz header: {offset}') #TODO
        return offset

    #这个函数名是 gzip/indexed_gzip都没有的，用于复位文件指针
    def reset(self, initialized=True):
        if initialized:
            self.close()
        fileobj = open(self.bglFileName, 'rb')
        offset = BglFile.gzHeaderOffset(fileobj)
        super().__init__(fileobj=OffsetFileWrapper(fileobj, offset=offset), skip_crc_check=True, *self.args, **self.kwargs)

#分析bgl文件内容，提取词条和释义
#会自动生成两个索引文件：trie - 所有词头的词典树索引；gzidx - 用于快速随机存取的索引文件
class BglReader:
    #resetBeforeParse: 在每次启动解释之前是否将bgl文件实例复位一次
    def __init__(self, fileName, resetBeforeParse=False):
        self.log = logging.getLogger()
        self.fileName = fileName
        firstPart = os.path.splitext(fileName)[0]
        self.trieFileName = firstPart + '.trie'
        self.encFileName = firstPart + '.enc'
        self.idxFileName = firstPart + '.gzidx'
        self.trie = None
        self.resetBeforeParse = resetBeforeParse
        self.gzipPos = 0 #从真实gzip文件头开始的偏移(解压缩数据)

        #生成加速随机存取的索引文件
        if not os.path.isfile(self.idxFileName):
            self.bglFile = BglFile(fileName)
            self.bglFile.build_full_index()
            self.bglFile.export_index(self.idxFileName)
        else:
            self.bglFile = BglFile(fileName, index_file=self.idxFileName)
        
        #词典内容的字符集编码
        self.encoding = None
        if os.path.isfile(self.encFileName):
            with open(self.encFileName, 'r', encoding='utf-8') as f:
                self.encoding = f.read().strip()

        #词典树索引
        if os.path.isfile(self.trieFileName):
            try:
                self.trie = marisa_trie.BytesTrie() #type:ignore
                self.trie.load(self.trieFileName)
            except Exception as e:
                self.trie = None
                self.log.warning(f'Failed to load BglReader trie data: {fileName}: {e}')

        if self.trie:
            return
        
        #分析索引数据，构建前缀树
        self.log.info(f"Building trie for {fileName}")
        self.buildTrie()

    #查询一个单词的释义
    def query(self, word, default=''):
        for wd in [word, word.lower(), word.capitalize()]:
            if wd in self.trie:
                break
        else:
            return default

        pos = int.from_bytes(self.trie[wd][0], byteorder='big')
        if self.resetBeforeParse:
            self.bglFile.reset()
        self.bglFile.seek(pos)
        self.gzipPos = pos
        pos, recType, data = self.readRecord()
        if recType is None:
            return default

        _, definition = self.decodeWordRecord(recType, data, wordOnly=False)
        return self.justifyDefinition(definition)

    #分析索引数据，构建前缀树
    def buildTrie(self):
        encoding = self.encoding
        records = [(word, pos.to_bytes(4, byteorder='big')) for word, pos in self.wordList()]
        self.trie = marisa_trie.BytesTrie(records) #type:ignore
        self.trie.save(self.trieFileName)

        #同时保存内容编码
        with open(self.encFileName, 'w', encoding='utf-8') as f:
            f.write(self.encoding)

        del records
        del self.trie
        self.trie = marisa_trie.BytesTrie() #type:ignore
        self.trie.load(self.trieFileName)

    #生成器，返回单词列表，每项元素 (word, pos)
    def wordList(self):
        bglFile = self.bglFile
        if self.resetBeforeParse:
            bglFile.reset()
            self.gzipPos = 0
        if not self.encoding:
            self.encoding = self.readSrcEncoding()
            bglFile.reset()
            self.gzipPos = 0

        while True:
            pos, recType, data = self.readRecord()
            if recType is None:
                break
            word, _ = self.decodeWordRecord(recType, data, wordOnly=True)
            word = self.justifyWord(word)
            if word:
                yield (word, pos)
        #bglFile.close()

    #当前只分析单词块，返回 word, definition
    #wordOnly: =True - 不解码释义部分，节省时间
    def decodeWordRecord(self, recType, data, wordOnly=True):
        encoding = self.encoding # or 'cp1252'
        if recType in (1, 7, 10, 11, 13):
            bWord, bDefi = unpack_term(data, wordOnly)
            word = bWord.decode(encoding, 'ignore')
        elif recType == 11:
            bWord, bDefi = unpack_term11(data, wordOnly)
            word = bWord.decode(encoding, 'ignore')
        else:
            word = ''
            bDefi = b''

        #definition = bDefi.decode(encoding, 'ignore') if bDefi else ''
        definition = resilient_decode(bDefi, encoding) if bDefi else ''
        return word, definition
    
    #读取字典的源编码
    def readSrcEncoding(self):
        encoding = 'cp1252'
        bglFile = self.bglFile
        while True:
            _, recType, data = self.readRecord()
            if recType is None:
                break
            if recType == PROPERTY:
                #print(f'property: {bytes(data[0:2])}')
                if int.from_bytes(data[0:2], byteorder='big') == P_S_CHARSET: #0x1A
                    encoding = CHARSET.get(data[2], 'cp1252')
                    break
        return encoding

    #从文件中读取特定长度的字节并转换为 big-endian unsigned int
    def readUint(self, length: int) -> int:
        data = self.bglFile.read(length)
        dataLen = len(data)
        self.gzipPos += dataLen
        return None if dataLen != length else int.from_bytes(data, byteorder='big')

    #读取当前文件指针所在位置的一个记录块，返回 (pos, recType, data)
    #pos: 当前块的开始位置
    #recType: 块的类型，一个字节
    #data: 实际数据
    def readRecord(self) -> (int, int, bytes):
        pos = self.gzipPos
        spec = self.readUint(1)
        if spec is None:
            return None, None, None
        
        recType = spec & 0x0f
        spec >>= 4
        recLen = self.readUint(spec + 1) if spec < 4 else (spec - 4)
        data = self.bglFile.read(recLen)
        dataLen = len(data)
        self.gzipPos += dataLen
        if dataLen != recLen:
            return None, None, None

        return pos, recType, data

    #修正单词里面的"非法字符"，有几种情况：
    #1. 多个连续美元符号
    #2. 两个美元符号中间有一个整数
    #3. html标签
    #4. unicode的转义表达 &#x1234; &#1234;
    def justifyWord(self, word: str):
        if not word:
            return ''
        word = re.sub(r'\${2,}', ' ', word)
        word = re.sub(r'\$\d+\$', ' ', word)
        word = re.sub(r'<.*?>', ' ', word)
        word = re.sub(r'&#(\d+);', lambda match: chr(int(match.group(1))), word)
        word = re.sub(r'&#x([0-9A-Fa-f]+);', lambda match: chr(int(match.group(1), 16)), word)
        word = re.sub(r'\s+', ' ', word)
        return word

    def justifyDefinition(self, definition):
        if not definition:
            return ''

        soup = BeautifulSoup(definition, 'html.parser') #html.parser不会自动添加html/body
        #删除多媒体资源和脚本
        for tag in list(soup.find_all(['head', 'img', 'script', 'base', 'iframe', 'canvas', 'embed', 'source',
            'command', 'datalist', 'video', 'audio', 'noscript', 'meta', 'button', 'style'])):
            tag.extract()

        #词条跳转
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('bword://'):
                a['href'] = f'https://kindleear/entry/{href[8:].strip()}'
            else:
                a.extract()

        return str(soup)

if __name__ == '__main__':
    import os, json, time
    thisDir = os.path.dirname(__file__)
    file = os.path.join(thisDir, 'Macmillan English.bgl')
    startTime = time.perf_counter()
    reader = BglReader(file)
    print(f'Time taken - Init: {time.perf_counter()-startTime} seconds.')

    startTime = time.perf_counter()
    word = 'worked'
    definition = reader.query(word)
    print(f'Time taken - query: {time.perf_counter()-startTime} seconds.')
    print(word, '\n', definition)

