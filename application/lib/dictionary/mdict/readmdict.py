#!/usr/bin/env python
# -*- coding: utf-8 -*-
# read_mdict.py
# Octopus MDict Dictionary File (.mdict) and Resource File (.mdd) Analyser
#
# Copyright (C) 2012, 2013, 2015 Xiaoqiang Wang <xiaoqiangwang AT gmail DOT com>
#
# This program is a free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# You can get a copy of GNU General Public License along this program
# But you can always get it from http://www.gnu.org/licenses/gpl.txt
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
import os, re, sys, io, json, zlib
from struct import pack, unpack
from typing import Dict

from .pureSalsa20 import Salsa20
from .ripemd128 import ripemd128
from . import lzo

class NumberFmt:
    """
    python struct.unpack format, reference: https://docs.python.org/3/library/struct.html
    """
    be_uint = ">I"
    be_ulonglong = ">Q"
    be_ushort = ">H"
    be_uchar = ">B"
    le_uint = "<I"
    le_ulonglong = "<Q"


def _unescape_entities(text):
    """
    unescape offending tags < > " &
    """
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&amp;", "&")
    return text


def _fast_decrypt(data, key):
    b = bytearray(data)
    key = bytearray(key)
    previous = 0x36
    for i in range(len(b)):
        t = (b[i] >> 4 | b[i] << 4) & 0xFF
        t = t ^ previous ^ (i & 0xFF) ^ key[i % len(key)]
        previous = b[i]
        b[i] = t
    return bytes(b)


def _mdx_decrypt(comp_block):
    key = ripemd128(comp_block[4:8] + pack(b"<L", 0x3695))
    return comp_block[0:8] + _fast_decrypt(comp_block[8:], key)


def _salsa_decrypt(ciphertext, encrypt_key):
    s20 = Salsa20(key=encrypt_key, IV=b"\x00" * 8, rounds=8)
    return s20.encryptBytes(ciphertext)


def _decrypt_regcode_by_deviceid(reg_code, deviceid):
    deviceid_digest = ripemd128(deviceid)
    s20 = Salsa20(key=deviceid_digest, IV=b"\x00" * 8, rounds=8)
    encrypt_key = s20.encryptBytes(reg_code)
    return encrypt_key


def _decrypt_regcode_by_email(reg_code, email):
    email_digest = ripemd128(email.decode().encode("utf-16-le"))
    s20 = Salsa20(key=email_digest, IV=b"\x00" * 8, rounds=8)
    encrypt_key = s20.encryptBytes(reg_code)
    return encrypt_key

class MDict(object):
    """
    Base class which reads in header and key block.
    It has no public methods and serves only as code sharing base class.
    """
    def __init__(self, fname, encoding="", passcode=None):
        self._fname = fname
        self.encoding = encoding.upper()
        self._passcode = passcode

        self.header = self._read_header()
        self._key_list = None

    def __len__(self):
        return self._num_entries

    def __iter__(self):
        return self.keys()

    def keys(self):
        """
        Return an iterator over dictionary keys.
        """
        return (key_value for key_id, key_value in self.key_list())

    #按需加载单词信息列表
    def key_list(self):
        if not self._key_list:
            try:
                self._key_list = self._read_keys()
            except:
                print("Try Brutal Force on Encrypted Key Blocks")
                self._key_list = self._read_keys_brutal()
        return self._key_list

    def _read_number(self, f):
        "根据版本不同，在缓冲区f中读取4个字节或8个字节，返回一个整数"
        return unpack(self._number_format, f.read(self._number_width))[0]

    def _decode_key_block_info(self, key_block_info_compressed):
        if self._version >= 2:
            # zlib compression
            assert key_block_info_compressed[:4] == b"\x02\x00\x00\x00"
            # decrypt if needed
            if self._encrypt & 0x02:
                key_block_info_compressed = _mdx_decrypt(key_block_info_compressed)
            # decompress
            key_block_info = zlib.decompress(key_block_info_compressed[8:])
            # adler checksum
            #adler32 = unpack(NumberFmt.be_uint, key_block_info_compressed[4:8])[0]
            #assert adler32 == zlib.adler32(key_block_info) & 0xFFFFFFFF
        else:
            # no compression
            key_block_info = key_block_info_compressed
        # decode
        key_block_info_list = []
        num_entries = 0
        i = 0
        if self._version >= 2:
            byte_format = NumberFmt.be_ushort
            byte_width = 2
            text_term = 1
        else:
            byte_format = NumberFmt.be_uchar
            byte_width = 1
            text_term = 0

        while i < len(key_block_info):
            #这一块key block包含多少个单词 number of entries in current key block
            num_entries += unpack(self._number_format, key_block_info[i : i + self._number_width])[0]
            i += self._number_width
            # text head size
            text_head_size = unpack(byte_format, key_block_info[i : i + byte_width])[0]
            i += byte_width
            # text head
            if self.encoding != "UTF-16":
                i += text_head_size + text_term
            else:
                i += (text_head_size + text_term) * 2
            # text tail size
            text_tail_size = unpack(byte_format, key_block_info[i : i + byte_width])[0]
            i += byte_width
            # text tail
            if self.encoding != "UTF-16":
                i += text_tail_size + text_term
            else:
                i += (text_tail_size + text_term) * 2
            # key block compressed size
            key_block_compressed_size = unpack(self._number_format, key_block_info[i : i + self._number_width])[0]
            i += self._number_width
            # key block decompressed size
            key_block_decompressed_size = unpack(self._number_format, key_block_info[i : i + self._number_width])[0]
            i += self._number_width
            key_block_info_list.append((key_block_compressed_size, key_block_decompressed_size))

        #assert num_entries == self._num_entries
        return key_block_info_list

    def _decode_key_block(self, key_block_compressed, key_block_info_list):
        key_list = []
        i = 0
        key_block = b''
        for compressed_size, decompressed_size in key_block_info_list:
            start = i
            end = i + compressed_size
            # 4 bytes : compression type
            key_block_type = key_block_compressed[start : start + 4]
            # 4 bytes : adler checksum of decompressed key block
            #adler32 = unpack(NumberFmt.be_uint, key_block_compressed[start + 4 : start + 8])[0]
            if key_block_type == b"\x00\x00\x00\x00":
                key_block = key_block_compressed[start + 8 : end]
            elif key_block_type == b"\x01\x00\x00\x00":
                header = b"\xf0" + pack(NumberFmt.be_uint, decompressed_size)
                key_block = lzo.decompress(header + key_block_compressed[start + 8 : end],
                    initSize=decompressed_size, blockSize=1308672)
            elif key_block_type == b"\x02\x00\x00\x00":
                key_block = zlib.decompress(key_block_compressed[start + 8 : end])
            # extract one single key block into a key list
            key_list.extend(self._split_key_block(key_block))
            # notice that adler32 returns signed value
            #assert adler32 == zlib.adler32(key_block) & 0xFFFFFFFF
            i += compressed_size
        return key_list

    def _split_key_block(self, key_block):
        #key_list = []
        key_start_index = 0
        key_end_index = 0
        while key_start_index < len(key_block):
            #temp = key_block[key_start_index : key_start_index + self._number_width]
            # the corresponding record's offset in record block
            key_id = unpack(
                self._number_format,
                key_block[key_start_index : key_start_index + self._number_width],
            )[0]
            # key text ends with '\x00'
            if self.encoding == "UTF-16":
                delimiter = b"\x00\x00"
                width = 2
            else:
                delimiter = b"\x00"
                width = 1
            i = key_start_index + self._number_width
            while i < len(key_block):
                if key_block[i : i + width] == delimiter:
                    key_end_index = i
                    break
                i += width
            key_text = (
                key_block[key_start_index + self._number_width : key_end_index]
                .decode(self.encoding, errors="ignore")
                .encode("utf-8")
                .strip()
            )
            key_start_index = key_end_index + width
            yield (key_id, key_text)
        return #key_list

    #读取文件头，生成一个python字典
    def _read_header(self):
        f = open(self._fname, "rb")
        #文件开头4个字节是头长度，不包括这4个字节和校验和，大端格式
        header_bytes_size = unpack(NumberFmt.be_uint, f.read(4))[0]
        header_bytes = f.read(header_bytes_size)
        #接下来4个字节，小端格式，adler32校验和
        f.read(4)
        #adler32 = unpack(NumberFmt.le_uint, f.read(4))[0]
        #assert adler32 == zlib.adler32(header_bytes) & 0xFFFFFFFF
        # mark down key block offset
        self._key_block_offset = f.tell()
        f.close()

        #头部信息最后两个字节如果为(0x00, 0x00)，则为UTF16编码，否则为UTF8编码
        headerEncoding = 'UTF-16' if header_bytes[-2:] == b'\x00\x00' else 'UTF-8'
        header_text = header_bytes[:-2].decode(headerEncoding)
        header_tag = self._parse_header(header_text)
        if not self.encoding:
            encoding = header_tag.get("Encoding", self.encoding)
            if encoding in ("GBK", "GB2312"): # GB18030 > GBK > GB2312
                encoding = "GB18030"
            self.encoding = encoding or 'UTF-8'

        self.title = header_tag.get('Title', '')
        self.description = header_tag.get('Description', '')
        
        # encryption flag
        #   0x00 - no encryption
        #   0x01 - encrypt record block
        #   0x02 - encrypt key info block
        encrypt = header_tag.get('Encrypted', '')
        if encrypt == "Yes":
            self._encrypt = 1
        elif encrypt.isdigit():
            self._encrypt = int(encrypt)
        else:
            self._encrypt = 0

        # stylesheet attribute if present takes form of:
        #   style_number # 1-255
        #   style_begin # or ''
        #   style_end # or ''
        # store stylesheet in dict in the form of
        # {'number' : ('style_begin', 'style_end')}
        stylesheet = {}
        lines = header_tag.get("StyleSheet", "").splitlines()
        for i in range(0, len(lines), 3):
            if (i + 2) < len(lines):
                k, v1, v2 = lines[i:i+3]
                stylesheet[k] = (v1, v2)
        self.stylesheet = stylesheet
        
        # before version 2.0, number is 4 bytes integer
        # version 2.0 and above uses 8 bytes
        self._version = float(header_tag["GeneratedByEngineVersion"])
        if self._version < 2.0:
            self._number_width = 4
            self._number_format = NumberFmt.be_uint
        else:
            self._number_width = 8
            self._number_format = NumberFmt.be_ulonglong

        return header_tag

    #将文件头信息分析为一个python字典
    def _parse_header(self, header) -> Dict[str, str]:
        """
        extract attributes from <Dict attr="value" ... >
        """
        tag_list = re.findall(r'(\w+)="(.*?)"', header, re.DOTALL)
        tag_dict = {}
        for k, v in tag_list:
            tag_dict[k] = _unescape_entities(v)
        return tag_dict

    #文件头后面就是单词信息列表
    def _read_keys(self):
        f = open(self._fname, "rb")
        f.seek(self._key_block_offset)

        #词典加密的原理是加密开头几个字节
        num_bytes = (8 * 5) if self._version >= 2.0 else (4 * 4)
        block = f.read(num_bytes)

        if self._encrypt & 1:
            if self._passcode is None:
                raise RuntimeError("user identification is needed to read encrypted file")
            regcode, userid = self._passcode
            if isinstance(userid, str):
                userid = userid.encode("utf-8")
            if self.header.get("RegisterBy") == "EMail":
                encrypted_key = _decrypt_regcode_by_email(regcode, userid)
            else:
                encrypted_key = _decrypt_regcode_by_deviceid(regcode, userid)
            block = _salsa_decrypt(block, encrypted_key)

        sf = io.BytesIO(block)
        num_key_blocks = self._read_number(sf) #Key block数量
        self._num_entries = self._read_number(sf) #词典中单词总数
        #2.0版本的key block info是压缩的，这里存放解压后长度
        if self._version >= 2.0:
            self._read_number(sf)
        #key block info字节长度
        key_block_info_size = self._read_number(sf)
        #单词块总共的字节长度
        key_block_size = self._read_number(sf)

        # 4 bytes: 前面num_bytes字节的adler校验和
        if self._version >= 2.0:
            f.read(4)
            #adler32 = unpack(NumberFmt.be_uint, f.read(4))[0]
            #assert adler32 == (zlib.adler32(block) & 0xFFFFFFFF)

        # read key block info, which indicates key block's compressed and
        # decompressed size
        key_block_info = f.read(key_block_info_size)
        key_block_info_list = self._decode_key_block_info(key_block_info)
        #assert num_key_blocks == len(key_block_info_list)

        # read key block
        key_block_compressed = f.read(key_block_size)
        # extract key block
        key_list = self._decode_key_block(key_block_compressed, key_block_info_list)

        self._record_block_offset = f.tell()
        f.close()

        return key_list

    def _read_keys_brutal(self):
        f = open(self._fname, "rb")
        f.seek(self._key_block_offset)

        # the following numbers could be encrypted, disregard them!
        if self._version >= 2.0:
            num_bytes = 8 * 5 + 4
            key_block_type = b"\x02\x00\x00\x00"
        else:
            num_bytes = 4 * 4
            key_block_type = b"\x01\x00\x00\x00"
        block = f.read(num_bytes)

        # key block info
        # 4 bytes '\x02\x00\x00\x00'
        # 4 bytes adler32 checksum
        # unknown number of bytes follows until '\x02\x00\x00\x00' which marks
        # the beginning of key block
        key_block_info = f.read(8)
        if self._version >= 2.0:
            assert key_block_info[:4] == b"\x02\x00\x00\x00"
        while True:
            fpos = f.tell()
            t = f.read(1024)
            index = t.find(key_block_type)
            if index != -1:
                key_block_info += t[:index]
                f.seek(fpos + index)
                break
            else:
                key_block_info += t

        key_block_info_list = self._decode_key_block_info(key_block_info)
        key_block_size = sum(list(zip(*key_block_info_list))[0])

        # read key block
        key_block_compressed = f.read(key_block_size)
        # extract key block
        key_list = self._decode_key_block(key_block_compressed, key_block_info_list)

        self._record_block_offset = f.tell()
        f.close()

        self._num_entries = len(key_list)
        return key_list


class MDD(MDict):
    """
    MDict resource file format (*.MDD) reader.
    >>> mdd = MDD('example.mdd')
    >>> len(mdd)
    208
    >>> for filename,content in mdd.items():
    ... print filename, content[:10]
    """

    def __init__(self, fname, passcode=None):
        MDict.__init__(self, fname, encoding="UTF-16", passcode=passcode)

    def items(self):
        """Return a generator which in turn produce tuples in the form of (filename, content)"""
        return self._decode_record_block()

    def _decode_record_block(self):
        f = open(self._fname, "rb")
        f.seek(self._record_block_offset)

        num_record_blocks = self._read_number(f)
        num_entries = self._read_number(f)
        assert num_entries == self._num_entries
        record_block_info_size = self._read_number(f)
        record_block_size = self._read_number(f)

        # record block info section
        record_block_info_list = []
        size_counter = 0
        for i in range(num_record_blocks):
            compressed_size = self._read_number(f)
            decompressed_size = self._read_number(f)
            record_block_info_list += [(compressed_size, decompressed_size)]
            size_counter += self._number_width * 2
        assert size_counter == record_block_info_size

        # actual record block
        offset = 0
        i = 0
        size_counter = 0
        for compressed_size, decompressed_size in record_block_info_list:
            record_block_compressed = f.read(compressed_size)
            # 4 bytes: compression type
            record_block_type = record_block_compressed[:4]
            # 4 bytes: adler32 checksum of decompressed record block
            adler32 = unpack(NumberFmt.be_uint, record_block_compressed[4:8])[0]
            if record_block_type == b"\x00\x00\x00\x00":
                record_block = record_block_compressed[8:]
            elif record_block_type == b"\x01\x00\x00\x00":
                header = b"\xf0" + pack(NumberFmt.be_uint, decompressed_size)
                record_block = lzo.decompress(header + record_block_compressed[start + 8 : end],
                    initSize=decompressed_size, blockSize=1308672)
            elif record_block_type == b"\x02\x00\x00\x00":
                record_block = zlib.decompress(record_block_compressed[8:])
            else:
                record_block = b''

            # notice that adler32 return signed value
            assert adler32 == zlib.adler32(record_block) & 0xFFFFFFFF

            assert len(record_block) == decompressed_size
            # split record block according to the offset info from key block
            keyList = self.key_list()
            while i < len(keyList):
                record_start, key_text = keyList[i]
                # reach the end of current record block
                if record_start - offset >= len(record_block):
                    break
                # record end index
                if i < len(keyList) - 1:
                    record_end = keyList[i + 1][0]
                else:
                    record_end = len(record_block) + offset
                i += 1
                data = record_block[record_start - offset : record_end - offset]
                yield key_text, data
            offset += len(record_block)
            size_counter += compressed_size
        assert size_counter == record_block_size

        f.close()

        ### 获取 mdict 文件的索引列表，格式为
        ###  key_text(关键词，可以由后面的 keylist 得到)
        ###  file_pos(record_block开始的位置), 32bit
        ###  compressed_size(record_block压缩前的大小) 64bit
        ###  decompressed_size(解压后的大小) 64bit
        ###  record_block_type(record_block 的压缩类型) 32bit
        ###  record_start (以下三个为从 record_block 中提取某一调记录需要的参数，可以直接保存） 64bit
        ###  record_end 64bit
        ###  offset 64bit

    def get_index(self, check_block=True):
        f = open(self._fname, "rb")
        index_dict_list = []
        f.seek(self._record_block_offset)

        num_record_blocks = self._read_number(f)
        num_entries = self._read_number(f)
        assert num_entries == self._num_entries
        record_block_info_size = self._read_number(f)
        record_block_size = self._read_number(f)

        # record block info section
        record_block_info_list = []
        size_counter = 0
        for i in range(num_record_blocks):
            compressed_size = self._read_number(f)
            decompressed_size = self._read_number(f)
            record_block_info_list += [(compressed_size, decompressed_size)]
            size_counter += self._number_width * 2
        # todo:注意！！！
        assert size_counter == record_block_info_size

        # actual record block
        offset = 0
        i = 0
        size_counter = 0
        for compressed_size, decompressed_size in record_block_info_list:
            current_pos = f.tell()
            record_block_compressed = f.read(compressed_size)
            # 4 bytes: compression type
            record_block_type = record_block_compressed[:4]
            # 4 bytes: adler32 checksum of decompressed record block
            adler32 = unpack(NumberFmt.be_uint, record_block_compressed[4:8])[0]
            record_block = b''
            if record_block_type == b"\x00\x00\x00\x00":
                _type = 0
                if check_block:
                    record_block = record_block_compressed[8:]
            elif record_block_type == b"\x01\x00\x00\x00":
                _type = 1
                header = b"\xf0" + pack(NumberFmt.be_uint, decompressed_size)
                if check_block:
                    record_block = lzo.decompress(header + record_block_compressed[start + 8 : end],
                        initSize=decompressed_size, blockSize=1308672)
            elif record_block_type == b"\x02\x00\x00\x00":
                _type = 2
                if check_block:
                    record_block = zlib.decompress(record_block_compressed[8:])
            
            # notice that adler32 return signed value
            if check_block:
                assert adler32 == zlib.adler32(record_block) & 0xFFFFFFFF
                assert len(record_block) == decompressed_size
            # split record block according to the offset info from key block
            keyList = self.key_list()
            while i < len(keyList):
                ### 用来保存索引信息的空字典
                index_dict = {}
                index_dict["file_pos"] = current_pos
                index_dict["compressed_size"] = compressed_size
                index_dict["decompressed_size"] = decompressed_size
                index_dict["record_block_type"] = _type
                record_start, key_text = keyList[i]
                index_dict["record_start"] = record_start
                index_dict["key_text"] = key_text.decode("utf-8")
                index_dict["offset"] = offset
                # reach the end of current record block
                if record_start - offset >= decompressed_size:
                    break
                # record end index
                if i < len(keyList) - 1:
                    record_end = keyList[i + 1][0]
                else:
                    record_end = decompressed_size + offset
                index_dict["record_end"] = record_end
                i += 1
                if check_block:
                    data = record_block[record_start - offset : record_end - offset]
                index_dict_list.append(index_dict)
                # yield key_text, data
            offset += decompressed_size
            size_counter += compressed_size
        assert size_counter == record_block_size
        f.close()
        return index_dict_list


class MDX(MDict):
    """
    MDict dictionary file format (*.MDD) reader.
    >>> mdict = MDX('example.mdict')
    >>> len(mdict)
    42481
    >>> for key,value in mdict.items():
    ... print key, value[:10]
    """

    def __init__(self, fname, encoding="", substyle=False, passcode=None):
        MDict.__init__(self, fname, encoding, passcode)
        self._substyle = substyle

    def items(self):
        """Return a generator which in turn produce tuples in the form of (key, value)"""
        return self._decode_record_block()

    #一种模板替换，使用词典内的预定义模板替换释义
    def _substitute_stylesheet(self, txt):
        # substitute stylesheet definition
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

    def _decode_record_block(self):
        f = open(self._fname, "rb")
        f.seek(self._record_block_offset)

        num_record_blocks = self._read_number(f)
        num_entries = self._read_number(f)
        assert num_entries == self._num_entries
        record_block_info_size = self._read_number(f)
        record_block_size = self._read_number(f)

        # record block info section
        record_block_info_list = []
        size_counter = 0
        for i in range(num_record_blocks):
            compressed_size = self._read_number(f)
            decompressed_size = self._read_number(f)
            record_block_info_list += [(compressed_size, decompressed_size)]
            size_counter += self._number_width * 2
        assert size_counter == record_block_info_size

        # actual record block data
        offset = 0
        i = 0
        size_counter = 0
        ###最后的索引表的格式为
        ###  key_text(关键词，可以由后面的 keylist 得到)
        ###  file_pos(record_block开始的位置)
        ###  compressed_size(record_block压缩前的大小)
        ###  decompressed_size(解压后的大小)
        ###  record_block_type(record_block 的压缩类型)
        ###  record_start (以下三个为从 record_block 中提取某一调记录需要的参数，可以直接保存）
        ###  record_end
        ###  offset
        record_block = b''
        for compressed_size, decompressed_size in record_block_info_list:
            record_block_compressed = f.read(compressed_size)
            ###### 要得到 record_block_compressed 需要得到 compressed_size (这个可以直接记录）
            ###### 另外还需要记录当前 f 对象的位置
            ###### 使用 f.tell() 命令/ 在建立索引是需要 f.seek()
            # 4 bytes indicates block compression type
            record_block_type = record_block_compressed[:4]
            # 4 bytes adler checksum of uncompressed content
            adler32 = unpack(NumberFmt.be_uint, record_block_compressed[4:8])[0]
            if record_block_type == b"\x00\x00\x00\x00":
                record_block = record_block_compressed[8:]
            elif record_block_type == b"\x01\x00\x00\x00":
                header = b"\xf0" + pack(NumberFmt.be_uint, decompressed_size)
                record_block = lzo.decompress(header + record_block_compressed[8:],
                    initSize=decompressed_size, blockSize=1308672)
            elif record_block_type == b"\x02\x00\x00\x00":
                # decompress
                record_block = zlib.decompress(record_block_compressed[8:])
            ###### 这里比较重要的是先要得到 record_block, 而 record_block 是解压得到的，其中一共有三种解压方法
            ###### 需要的信息有 record_block_compressed, decompress_size,
            ###### record_block_type
            ###### 另外还需要校验信息 adler32
            # notice that adler32 return signed value
            #assert adler32 == zlib.adler32(record_block) & 0xFFFFFFFF
            #assert len(record_block) == decompressed_size
            # split record block according to the offset info from key block
            keyList = self.key_list()
            while i < len(keyList):
                record_start, key_text = keyList[i]
                # reach the end of current record block
                if record_start - offset >= len(record_block):
                    break
                # record end index
                if i < len(keyList) - 1:
                    record_end = keyList[i + 1][0]
                else:
                    record_end = len(record_block) + offset
                i += 1
                #############需要得到 record_block , record_start, record_end,
                #############offset
                record = record_block[record_start - offset : record_end - offset]
                # convert to utf-8
                record = (
                    record.decode(self.encoding, errors="ignore")
                    .strip("\x00")
                    .encode("utf-8")
                )
                # substitute styles
                #############是否替换样式表
                if self._substyle and self.stylesheet:
                    record = self._substitute_stylesheet(record)

                yield key_text, record
            offset += len(record_block)
            size_counter += compressed_size
        assert size_counter == record_block_size

        f.close()

    ### 获取 mdict 文件的索引列表，格式为
    ###  key_text(关键词，可以由后面的 keylist 得到)
    ###  file_pos(record_block开始的位置)
    ###  compressed_size(record_block压缩前的大小)
    ###  decompressed_size(解压后的大小)
    ###  record_block_type(record_block 的压缩类型)
    ###  record_start (以下三个为从 record_block 中提取某一调记录需要的参数，可以直接保存）
    ###  record_end
    ###  offset
    ### 所需 metadata
    ###
    def get_index(self, check_block=True):
        ###  索引列表
        keyList = self.key_list()
        keyListLen = len(keyList)

        f = open(self._fname, "rb")
        f.seek(self._record_block_offset)

        num_record_blocks = self._read_number(f)
        num_entries = self._read_number(f)
        assert num_entries == self._num_entries
        record_block_info_size = self._read_number(f)
        record_block_size = self._read_number(f)

        # record block info section
        record_block_info_list = []
        for i in range(num_record_blocks):
            compressed_size = self._read_number(f)
            decompressed_size = self._read_number(f)
            record_block_info_list.append((compressed_size, decompressed_size))

        # actual record block data
        ###最后的索引表的格式为
        ###  key_text(关键词，可以由后面的 keylist 得到)
        ###  file_pos(record_block开始的位置)
        ###  compressed_size(record_block压缩前的大小)
        ###  decompressed_size(解压后的大小)
        ###  record_block_type(record_block 的压缩类型)
        ###  record_start (以下三个为从 record_block 中提取某一调记录需要的参数，可以直接保存）
        ###  record_end
        ###  offset
        current_pos = f.tell()
        f.close()
        offset = 0
        i = 0
        for compressed_size, decompressed_size in record_block_info_list:
            ###### 要得到 record_block_compressed 需要得到 compressed_size (这个可以直接记录）
            ###### 另外还需要记录当前 f 对象的位置
            ###### 使用 f.tell() 命令/ 在建立索引是需要 f.seek()
            # 4 bytes indicates block compression type
            #record_block_type = record_block_compressed[:4]
            # 4 bytes adler checksum of uncompressed content
            #adler32 = unpack(NumberFmt.be_uint, record_block_compressed[4:8])[0]
            # split record block according to the offset info from key block
            while i < keyListLen:
                record_start, key_text = keyList[i]
                if record_start - offset >= decompressed_size: # reach the end of current record block
                    break
                
                record_end = keyList[i + 1][0] if i < keyListLen - 1 else (decompressed_size + offset)
                index_tuple = (current_pos, compressed_size, decompressed_size, record_start - offset, 
                    record_end - offset)
                yield (key_text.decode('utf-8'), index_tuple)
                i += 1

            current_pos += compressed_size
            offset += decompressed_size
        return

    #通过单词的索引数据，直接读取文件对应的数据块返回释义
    #indexes是列表，因为可能有多个相同的单词条目
    def get_content_by_Index(self, indexes) -> str:
        if not indexes:
            return ''

        ret = []
        f = open(self._fname, 'rb')
        for index in indexes:
            #这些变量是保存到trie的数据格式，32位
            filePos, compSize, decompSize, startIdx, endIdx = index
            f.seek(filePos)
            compressed = f.read(compSize)
            type_ = compressed[:4] #32bit-type, 32bit-adler, data
            if type_ == b"\x00\x00\x00\x00":
                data = compressed[8:]
            elif type_ == b"\x01\x00\x00\x00":
                header = b"\xf0" + pack(">I", decompSize)
                data = lzo.decompress(header + compressed[8:], initSize=decompSize, blockSize=1308672)
            elif type_ == b"\x02\x00\x00\x00":
                data = zlib.decompress(compressed[8:])
            else:
                continue
            record = data[startIdx : endIdx]
            ret.append(record) #.strip(b"\x00"))

        f.close()
        txt = b'<hr/>'.join(ret).decode(self.encoding)
        return self._substitute_stylesheet(txt) if self.stylesheet else txt

    def compare_keys(self, key1, key2):
        """
        排序要求：
        header中KeyCaseSensitive表明排序时是否大小写不敏感,为No时要转化为小写字母比较。
        header中StripKey只对mdx有效，为No，则不分词，字母、空格、符号都参与排序，为Yes，则分词，仅字母参与排序，去掉空格、符号。
        MDX的编码有utf-8,utf-16,gb18030(包括gbk，gb2313,gb18030),BIG5,ISO8859-1。
        MDD的编码为utf-16le,尽管utf-16默认也是utf-16le，但是会加前缀\xff\xfe。
        排序:utf-16按照utf-16le编解码，按照utf-16be排序，其他按照各自编码排序。
        @param key1: the key user input
        @param key2: the key from the file
        @return:
        """
        # mdx和mdd中的key都是bytes，查询key是str，因此str转bytes要在lower()之后进行。
        # if type(key1) == str:
        #     key1 = key1.encode(self._encoding)
        # if type(key2) == str:
        #     key2 = key2.encode(self._encoding)
        # Dictionary of Engineering的最后一个词条是b'\xc5ngstr\xf6m compensation pyrheliometer'，其中\xc5和\xf6解码报错，因此用replace。
        key1 = self.process_str_keys(key1)
        key2 = self.process_str_keys(key2)

        # if operator.__lt__(key1, key2):
        #     return -1
        # elif operator.__eq__(key1, key2):
        #     return 0
        # elif operator.__gt__(key1, key2):
        #     return 1
        import operator
        if self.__class__.__name__ == 'MDX':
            if self.encoding == 'UTF-16':
                t_key1 = key1.encode('utf-16be', errors='ignore')
                t_key2 = key2.encode('utf-16be', errors='ignore')
                if operator.__lt__(t_key1, t_key2):
                    return -1
                elif operator.__eq__(t_key1, t_key2):
                    return 0
                elif operator.__gt__(t_key1, t_key2):
                    return 1
            if self.encoding == 'BIG-5':
                t_key1 = key1.encode('utf-8', errors='ignore')
                t_key2 = key2.encode('utf-8', errors='ignore')
                if operator.__lt__(t_key1, t_key2):
                    return -1
                elif operator.__eq__(t_key1, t_key2):
                    return 0
                elif operator.__gt__(t_key1, t_key2):
                    return 1
            else:
                t_key1 = key1.encode(self.encoding, errors='ignore')
                t_key2 = key2.encode(self.encoding, errors='ignore')
                if operator.__lt__(t_key1, t_key2):
                    return -1
                elif operator.__eq__(t_key1, t_key2):
                    return 0
                elif operator.__gt__(t_key1, t_key2):
                    return 1
        else:
            t_key1 = key1.encode('utf-8', errors='ignore')
            t_key2 = key2.encode('utf-8', errors='ignore')
            if operator.__lt__(t_key1, t_key2):
                return -1
            elif operator.__eq__(t_key1, t_key2):
                return 0
            elif operator.__gt__(t_key1, t_key2):
                return 1

    def lower_str_keys(self, key):
        """自动转换为小写"""
        return key if self.header.get('KeyCaseSensitive') == 'Yes' else key.lower()
        
    def strip_key(self):
        # 0:False,1:True,2:None
        if 'StripKey' in self.header.keys():
            if self.header['StripKey'] == 'Yes':
                self._strip_key = 1
            elif self.header['StripKey'] == 'No':
                self._strip_key = 0
            else:
                self._strip_key = 2
        else:
            self._strip_key = 2

        if self.__class__.__name__ == 'MDD':
            self._strip_key = 0

    def process_str_keys(self, key):
        if self.__class__.__name__ == 'MDX':
            if isinstance(key, bytes):
                if self.encoding == 'UTF-16':
                    key = key.decode('utf-16le', errors='ignore')
                else:
                    # ISO8859-1编码中文报错latin-1 UnicodeDecodeError
                    key = key.decode(self.encoding, errors='ignore')
        else:
            if isinstance(key, bytes):
                key = key.decode(self.encoding)
        if self._strip_key == 1:
            key = re.sub(r'[ _=,.;:!?@%&#~`()\[\]<>{}/\\\$\+\-\*\^\'"\t|]', '', key)
        return self.lower_str_keys(key) # 这里不能strip()

if __name__ == "__main__":
    import sys
    import os
    import os.path
    import argparse
    import codecs

    def passcode(s):
        try:
            regcode, userid = s.split(",")
        except:
            raise argparse.ArgumentTypeError("Passcode must be regcode,userid")
        try:
            regcode = codecs.decode(regcode, "hex")
        except:
            raise argparse.ArgumentTypeError(
                "regcode must be a 32 bytes hexadecimal string"
            )
        return regcode, userid

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-x",
        "--extract",
        action="store_true",
        help="extract mdict to source format and extract files from mdd",
    )
    parser.add_argument(
        "-s",
        "--substyle",
        action="store_true",
        help="substitute style definition if present",
    )
    parser.add_argument(
        "-d",
        "--datafolder",
        default="data",
        help="folder to extract data files from mdd",
    )
    parser.add_argument(
        "-e", "--encoding", default="", help="folder to extract data files from mdd"
    )
    parser.add_argument(
        "-p",
        "--passcode",
        default=None,
        type=passcode,
        help="register_code,email_or_deviceid",
    )
    parser.add_argument("filename", nargs="?", help="mdict file name")
    args = parser.parse_args()

    # use GUI to select file, default to extract
    if not args.filename:
        import tkinter as Tkinter
        import tkinter.filedialog as tkFileDialog
        root = Tkinter.Tk()
        root.withdraw()
        args.filename = tkFileDialog.askopenfilename(parent=root)
        args.extract = True

    if not os.path.exists(args.filename):
        print("Please specify a valid MDX/MDD file")

    base, ext = os.path.splitext(args.filename)

    # read mdict file
    if ext.lower() == ".mdx":
        mdx = MDX(args.filename, args.encoding, args.substyle, args.passcode)
        if isinstance(args.filename, str):
            bfname = args.filename.encode("utf-8")
        else:
            bfname = args.filename
        print("======== %s ========" % bfname)
        print("  Number of Entries : %d" % len(mdx))
        for key, value in mdx.header.items():
            print("  %s : %s" % (key, value))
    else:
        mdx = None

    # find companion mdd file
    mdd_filename = "".join([base, os.path.extsep, "mdd"])
    if os.path.exists(mdd_filename):
        mdd = MDD(mdd_filename, args.passcode)
        if isinstance(mdd_filename, str):
            bfname = mdd_filename.encode("utf-8")
        else:
            bfname = mdd_filename
        print("======== %s ========" % bfname)
        print("  Number of Entries : %d" % len(mdd))
        for key, value in mdd.header.items():
            print("  %s : %s" % (key, value))
    else:
        mdd = None

    if args.extract:
        # write out glos
        if mdx:
            output_fname = "".join([base, os.path.extsep, "txt"])
            tf = open(output_fname, "wb")
            for key, value in mdx.items():
                tf.write(key)
                tf.write(b"\r\n")
                tf.write(value)
                if not value.endswith(b"\n"):
                    tf.write(b"\r\n")
                tf.write(b"</>\r\n")
            tf.close()
            # write out style
            if mdx.header.get("StyleSheet"):
                style_fname = "".join([base, "_style", os.path.extsep, "txt"])
                sf = open(style_fname, "wb")
                sf.write("\r\n".join(mdx.header["StyleSheet"].splitlines()))
                sf.close()
        # write out optional data files
        if mdd:
            datafolder = os.path.join(os.path.dirname(args.filename), args.datafolder)
            if not os.path.exists(datafolder):
                os.makedirs(datafolder)
            for key, value in mdd.items():
                fname = key.decode("utf-8").replace("\\", os.path.sep)
                dfname = datafolder + fname
                if not os.path.exists(os.path.dirname(dfname)):
                    os.makedirs(os.path.dirname(dfname))
                df = open(dfname, "wb")
                df.write(value)
                df.close()
