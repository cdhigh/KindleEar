#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#stardict词典支持，基于 <https://github.com/lig/pystardict> 修改
import os, re, logging
from struct import unpack
try:
    import indexed_gzip as igzip
except:
    import gzip
    igzip = None

try:
    import marisa_trie
except:
    marisa_trie = None

#外部接口
class PyStarDict:
    """
    Dictionary-like class for lazy manipulating stardict dictionaries

    All items of this dictionary are writable and dict is expandable itself,
    but changes are not stored anywhere and available in runtime only.

    We assume in this documentation that "x" or "y" is instances of the
    StarDictDict class and "x.{ifo,idx{,.gz},dict{,.dz},syn}" or
    "y.{ifo,idx{,.gz},dict{,.dz},syn}" is files of the corresponding stardict
    dictionaries.

    Following documentation is from the "dict" class an is subkect to rewrite
    in further impleneted methods:

    """

    def __init__(self, filename_prefix):
        """
        filename_prefix: path to dictionary files without files extensions

        initializes new StarDictDict instance from stardict dictionary files
        provided by filename_prefix
        """
        self.log = logging.getLogger() #'StarDict'
        self.ifo = _StarDictIfo(dict_prefix=filename_prefix, container=self)
        self.idx = _StarDictIdx(dict_prefix=filename_prefix, container=self)
        self.dict = _StarDictDict(dict_prefix=filename_prefix, container=self)
        self.syn = _StarDictSyn(dict_prefix=filename_prefix, container=self)

    def __contains__(self, k):
        return k in self.idx

    def __getitem__(self, k):
        return self.dict[k]

    def __len__(self):
        return self.ifo.wordcount

    def __repr__(self):
        return f'{self.__class__} {self.ifo.bookname}'

    def get(self, word, default=''): #type:ignore
        return self[word] if word in self.idx else default

    def has_key(self, k):
        return k in self

#词典基本信息，比如版本，名字，索引文件长度等
class _StarDictIfo:
    """
    The .ifo file has the following format:

    StarDict's dict ifo file
    version=2.4.2
    [options]

    Note that the current "version" string must be "2.4.2" or "3.0.0".  If it's not,
    then StarDict will refuse to read the file.
    If version is "3.0.0", StarDict will parse the "idxoffsetbits" option.

    [options]
    ---------
    In the example above, [options] expands to any of the following lines
    specifying information about the dictionary.  Each option is a keyword
    followed by an equal sign, then the value of that option, then a
    newline.  The options may be appear in any order.

    Note that the dictionary must have at least a bookname, a wordcount and a 
    idxfilesize, or the load will fail.  All other information is optional.  All 
    strings should be encoded in UTF-8.

    Available options:

    bookname=      // required
    wordcount=     // required
    synwordcount=  // required if ".syn" file exists.
    idxfilesize=   // required
    idxoffsetbits= // New in 3.0.0
    author=
    email=
    website=
    description=    // You can use <br> for new line.
    date=
    sametypesequence= // very important.
    """
    def __init__(self, dict_prefix, container):
        ifo_filename = f'{dict_prefix}.ifo'

        try:
            _file = open(ifo_filename)
        except Exception as e:
            raise Exception('ifo file opening error: "{}"'.format(e))

        _file.readline() # skipping ifo header
        _line = _file.readline().split('=')
        if _line[0] == 'version':
            self.version = _line[1]
        else:
            raise Exception('ifo has invalid format')

        _config = {}
        for _line in _file:
            _line_splited = _line.split('=')
            _config[_line_splited[0]] = _line_splited[1]
        _file.close()

        self.bookname = _config.get('bookname', '').strip()
        if not self.bookname:
            raise Exception('ifo has no bookname')

        wordcount = _config.get('wordcount', '')
        if not wordcount:
            raise Exception('ifo has no wordcount')
        self.wordcount = int(wordcount)

        if self.version == '3.0.0':
            try:
                #_syn = open(f'{dict_prefix}.syn')    # not used
                synwordcount = _config.get('synwordcount', None)
                if synwordcount is None:
                    raise Exception('ifo has no synwordcount but .syn file exists')
                self.synwordcount = int(synwordcount)
            except IOError:
                pass

        idxfilesize = _config.get('idxfilesize', None)
        if idxfilesize is None:
            raise Exception('ifo has no idxfilesize')
        self.idxfilesize = int(idxfilesize)

        self.idxoffsetbits = int(_config.get('idxoffsetbits', 32))
        self.author = _config.get('author', '').strip()
        self.email = _config.get('email', '').strip()
        self.website = _config.get('website', '').strip()
        self.description = _config.get('description', '').strip()
        self.date = _config.get('date', '').strip()
        self.sametypesequence = _config.get('sametypesequence', '').strip()

#idx, 词条的索引文件，按升序排序。
class _StarDictIdx:
    """
    The .idx file is just a word list.

    The word list is a sorted list of word entries.

    Each entry in the word list contains three fields, one after the other:
         word_str;  // a utf-8 string terminated by '\0' (长度小于256，所收词条单词)
         word_data_offset;  // word data's offset in .dict file (32bit/64bit 无符号整数 网络字节序列)
         word_data_size;  // word data's total size in .dict file (32bit 无符号整数 网络字节序列)
    如果ifo包含idxoffsetbits字段，表示字典偏移长度为64位，即8字节
    """
    def __init__(self, dict_prefix, container):
        self._container = container

        dict_name = os.path.basename(dict_prefix)
        idx_filename = f'{dict_prefix}.idx'
        idx_filename_gz = f'{idx_filename}.gz'
        trie_filename = f'{dict_prefix}.trie'
        self.trie = None
        bytes_size = int(container.ifo.idxoffsetbits / 8)
        offset_format = 'L' if bytes_size == 4 else 'Q'
        trie_fmt = f">{offset_format}L"
        if os.path.exists(trie_filename):
            try:
                self.trie = marisa_trie.RecordTrie(trie_fmt) #type:ignore
                self.trie.load(trie_filename)
            except Exception as e:
                self.trie = None
                container.log.warning(f'Failed to load stardict trie data: {dict_name}: {e}')

        if self.trie:
            return

        #分析索引数据，构建前缀树
        container.log.info(f"Building trie for {dict_name}")
        try:
            file = open_file(idx_filename, idx_filename_gz)
        except Exception as e:
            raise Exception('idx file opening error: "{}"'.format(e))

        fileContent = file.read()

        #check file size
        if file.tell() != container.ifo.idxfilesize:
            file.close()
            raise Exception('size of the .idx file is incorrect')

        file.close()

        #prepare main dict and parsing parameters
        record_size = str(bytes_size + 4).encode('utf-8') #偏移+数据长

        #parse data via regex
        record_pattern = br'(.+?\x00.{' + record_size + br'})'
        matched_records = re.findall(record_pattern, fileContent, re.DOTALL) #type:ignore

        #check records count
        if len(matched_records) != container.ifo.wordcount:
            raise Exception('words count is incorrect')

        #unpack parsed records
        #为了减小一点内存占用，将这部分写成生成器
        def idxForTrie():
            for matched_record in matched_records:
                cnt = matched_record.find(b'\x00') + 1
                record_tuple = unpack(f'>{cnt}c{offset_format}L', matched_record)
                word = b''.join(record_tuple[:cnt-1]).decode('utf8').lower()
                yield (word, record_tuple[cnt:]) #(word, (offset, size))

        self.trie = marisa_trie.RecordTrie(trie_fmt, idxForTrie()) #type:ignore
        self.trie.save(trie_filename)
        
        del self.trie
        self.trie = marisa_trie.RecordTrie(trie_fmt) #type:ignore
        self.trie.load(trie_filename)
        del fileContent
        del matched_records
        import gc
        gc.collect()
        
    def __getitem__(self, word) -> tuple:
        """
        returns tuple (word_data_offset, word_data_size,) for word in .dict

        @note: here may be placed flexible search realization
        """
        return self.trie[word.lower()][0] #type:ignore
        
    def __contains__(self, word) -> bool:
        return word.lower() in self.trie

#实际的词典数据
class _StarDictDict:
    """
    The .dict file is a pure data sequence, as the offset and size of each
    word is recorded in the corresponding .idx file.

    If the "sametypesequence" option is not used in the .ifo file, then
    the .dict file has fields in the following order:
    ==============
    word_1_data_1_type; // a single char identifying the data type
    word_1_data_1_data; // the data
    word_1_data_2_type;
    word_1_data_2_data;
    ...... // the number of data entries for each word is determined by
           // word_data_size in .idx file
    word_2_data_1_type;
    word_2_data_1_data;
    ......
    ==============
    It's important to note that each field in each word indicates its
    own length, as described below.  The number of possible fields per
    word is also not fixed, and is determined by simply reading data until
    you've read word_data_size bytes for that word.


    Suppose the "sametypesequence" option is used in the .idx file, and
    the option is set like this:
    sametypesequence=tm
    Then the .dict file will look like this:
    ==============
    word_1_data_1_data
    word_1_data_2_data
    word_2_data_1_data
    word_2_data_2_data
    ......
    ==============
    The first data entry for each word will have a terminating '\0', but
    the second entry will not have a terminating '\0'.  The omissions of
    the type chars and of the last field's size information are the
    optimizations required by the "sametypesequence" option described
    above.

    If "idxoffsetbits=64", the file size of the .dict file will be bigger 
    than 4G. Because we often need to mmap this large file, and there is 
    a 4G maximum virtual memory space limit in a process on the 32 bits 
    computer, which will make we can get error, so "idxoffsetbits=64" 
    dictionary can't be loaded in 32 bits machine in fact, StarDict will 
    simply print a warning in this case when loading. 64-bits computers 
    should haven't this limit.

    Type identifiers
    ----------------
    Here are the single-character type identifiers that may be used with
    the "sametypesequence" option in the .idx file, or may appear in the
    dict file itself if the "sametypesequence" option is not used.

    Lower-case characters signify that a field's size is determined by a
    terminating '\0', while upper-case characters indicate that the data
    begins with a network byte-ordered guint32 that gives the length of 
    the following data's size(NOT the whole size which is 4 bytes bigger).

    'm'
    Word's pure text meaning.
    The data should be a utf-8 string ending with '\0'.

    'l'
    Word's pure text meaning.
    The data is NOT a utf-8 string, but is instead a string in locale
    encoding, ending with '\0'.  Sometimes using this type will save disk
    space, but its use is discouraged.

    'g'
    A utf-8 string which is marked up with the Pango text markup language.
    For more information about this markup language, See the "Pango
    Reference Manual."
    You might have it installed locally at:
    file:///usr/share/gtk-doc/html/pango/PangoMarkupFormat.html

    't'
    English phonetic string.
    The data should be a utf-8 string ending with '\0'.

    Here are some utf-8 phonetic characters:
    θʃŋʧðʒæıʌʊɒɛəɑɜɔˌˈːˑṃṇḷ
    æɑɒʌәєŋvθðʃʒɚːɡˏˊˋ

    'x'
    A utf-8 string which is marked up with the xdxf language.
    See http://xdxf.sourceforge.net
    StarDict have these extention:
    <rref> can have "type" attribute, it can be "image", "sound", "video" 
    and "attach".
    <kref> can have "k" attribute.

    'y'
    Chinese YinBiao or Japanese KANA.
    The data should be a utf-8 string ending with '\0'.

    'k'
    KingSoft PowerWord's data. The data is a utf-8 string ending with '\0'.
    It is in XML format.

    'w'
    MediaWiki markup language.
    See http://meta.wikimedia.org/wiki/Help:Editing#The_wiki_markup

    'h'
    Html codes.

    'r'
    Resource file list.
    The content can be:
    img:pic/example.jpg     // Image file
    snd:apple.wav           // Sound file
    vdo:film.avi            // Video file
    att:file.bin            // Attachment file
    More than one line is supported as a list of available files.
    StarDict will find the files in the Resource Storage.
    The image will be shown, the sound file will have a play button.
    You can "save as" the attachment file and so on.

    'W'
    wav file.
    The data begins with a network byte-ordered guint32 to identify the wav
    file's size, immediately followed by the file's content.

    'P'
    Picture file.
    The data begins with a network byte-ordered guint32 to identify the picture
    file's size, immediately followed by the file's content.

    'X'
    this type identifier is reserved for experimental extensions.

    """

    def __init__(self, dict_prefix, container):
        """
        opens regular or dziped .dict file
        """
        self._container = container

        dict_filename = f'{dict_prefix}.dict'
        dict_filename_dz = f'{dict_filename}.dz'

        try:
            f = open_file(dict_filename, dict_filename_dz)
        except Exception as e:
            raise Exception('dict file opening error: "{}"'.format(e))

        self._file = f

    def __getitem__(self, word) -> bytes:
        """
        returns data from .dict for word
        """
        cords = self._container.idx[word]
        self._file.seek(cords[0])
        data = self._file.read(cords[1]) #type:ignore
        ret = {}
        typeSeq = self._container.ifo.sametypesequence
        seqLen = len(typeSeq)
        if seqLen:
            for k, type_ in enumerate(typeSeq):
                if type_ in "mlgtxykwhnr": #文本
                    if k >= seqLen - 1: #最后一个数据段
                        ret[type_] = data
                    else:
                        ret[type_], _, data = data.partition(b'\0') #type:ignore
                else: #音频图像，暂不支持
                    #开头一个网络字节序的32位整数指示实际数据长度
                    size = unpack("!L", data[:4]) #type:ignore
                    #ret[type_] = data[4:size + 4] #type:ignore
                    data = data[size + 4:]
        else:
            while data:
                type_ = unpack("!c", data[:1]) #type:ignore
                if type_ in "mlgtxykwhnr": #type:ignore
                    ret[type_], _, data = data.partition(b'\0') #type:ignore
                else: #音频图像，暂不支持
                    size = unpack("!L", data[:4]) #type:ignore
                    #ret[type_] = data[4:size + 4] #type:ignore
                    data = data[size + 4:]

        return b''.join(ret.values())
        
    def __contains__(self, word):
        return word in self._container.idx

class _StarDictSyn(object):
    def __init__(self, dict_prefix, container):
        syn_filename = f'{dict_prefix}.syn'

        #try:
        #    self._file = open(syn_filename)
        #except IOError:
        #    # syn file is optional, passing silently
        #    pass

def open_file(regular, gz):
    """
    Open regular file if it exists, gz file otherwise.
    If no file exists, raise ValueError.
    """
    if os.path.exists(regular):
        try:
            return open(regular, 'rb')
        except Exception as e:
            raise Exception('regular file opening error: "{}"'.format(e))

    #压缩索引文件后缀一般是gz，使用gzip压缩, 
    #压缩数据文件后缀一般是dz，使用dictzip压缩，dictzip使用与 gzip 相同的压缩算法和文件格式，
    #但是它提供一个表可以用来在文件中随机访问压缩块。
    if os.path.exists(gz):
        try:
            return igzip.IndexedGzipFile(gz) if igzip else gzip.open(gz, 'rb') #type:ignore
        except Exception as e:
            raise Exception('gz file opening error: "{}"'.format(e))

    raise ValueError('Neither regular nor gz file exists')
