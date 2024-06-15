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
import json
import re
import sys
import os

# zlib compression is used for engine version >=2.0
import zlib
from io import BytesIO
from struct import pack, unpack
from typing import Dict

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(__file__))

from .pureSalsa20 import Salsa20
from .ripemd128 import ripemd128
from . import lzo

'''
key_block_info,key_block,record_block的开头4个字节是压缩类型
b'\x00\x00\x00\x00'无压缩
b'\x01\x00\x00\x00'lzo压缩
b'\x02\x00\x00\x00'zlib压缩

self._encrypt是加密类型
0 无加密
1 Salsa20加密，需要提供self._passcode
2 ripemd128加密
'''

# 2x3 compatible
if sys.hexversion >= 0x03000000:
    unicode = str


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
    text = text.replace(b"&lt;", b"<")
    text = text.replace(b"&gt;", b">")
    text = text.replace(b"&quot;", b'"')
    text = text.replace(b"&amp;", b"&")
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


def _parse_header(header) -> Dict[str, str]:
    """
    extract attributes from <Dict attr="value" ... >
    """
    tag_list = re.findall(b'(\w+)="(.*?)"', header, re.DOTALL)
    tag_dict = {}
    for k, v in tag_list:
        tag_dict[k] = _unescape_entities(v)
    return tag_dict


class MDict(object):
    """
    Base class which reads in header and key block.
    It has no public methods and serves only as code sharing base class.
    """

    def __init__(self, fname, encoding="", passcode=None):
        self._fname = fname
        self._encoding = encoding.upper()
        self._passcode = passcode

        self.header = self._read_header()
        try:
            self._key_list = self._read_keys()
        except:
            print("Try Brutal Force on Encrypted Key Blocks")
            self._key_list = self._read_keys_brutal()

    def __len__(self):
        return self._num_entries

    def __iter__(self):
        return self.keys()

    def keys(self):
        """
        Return an iterator over dictionary keys.
        """
        return (key_value for key_id, key_value in self._key_list)

    def _read_number(self, f):
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
            adler32 = unpack(NumberFmt.be_uint, key_block_info_compressed[4:8])[0]
            assert adler32 == zlib.adler32(key_block_info) & 0xFFFFFFFF
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
            # number of entries in current key block
            num_entries += unpack(
                self._number_format, key_block_info[i : i + self._number_width]
            )[0]
            i += self._number_width
            # text head size
            text_head_size = unpack(byte_format, key_block_info[i : i + byte_width])[0]
            i += byte_width
            # text head
            if self._encoding != "UTF-16":
                i += text_head_size + text_term
            else:
                i += (text_head_size + text_term) * 2
            # text tail size
            text_tail_size = unpack(byte_format, key_block_info[i : i + byte_width])[0]
            i += byte_width
            # text tail
            if self._encoding != "UTF-16":
                i += text_tail_size + text_term
            else:
                i += (text_tail_size + text_term) * 2
            # key block compressed size
            key_block_compressed_size = unpack(
                self._number_format, key_block_info[i : i + self._number_width]
            )[0]
            i += self._number_width
            # key block decompressed size
            key_block_decompressed_size = unpack(
                self._number_format, key_block_info[i : i + self._number_width]
            )[0]
            i += self._number_width
            key_block_info_list += [
                (key_block_compressed_size, key_block_decompressed_size)
            ]

        assert num_entries == self._num_entries

        return key_block_info_list

    def _decode_key_block(self, key_block_compressed, key_block_info_list):
        key_list = []
        i = 0
        for compressed_size, decompressed_size in key_block_info_list:
            start = i
            end = i + compressed_size
            # 4 bytes : compression type
            key_block_type = key_block_compressed[start : start + 4]
            # 4 bytes : adler checksum of decompressed key block
            adler32 = unpack(
                NumberFmt.be_uint, key_block_compressed[start + 4 : start + 8]
            )[0]
            if key_block_type == b"\x00\x00\x00\x00":
                key_block = key_block_compressed[start + 8 : end]
            elif key_block_type == b"\x01\x00\x00\x00":
                if lzo is None:
                    print("LZO compression is not supported")
                    break
                # decompress key block
                header = b"\xf0" + pack(NumberFmt.be_uint, decompressed_size)
                key_block = lzo.decompress(
                    key_block_compressed[start + 8 : end],
                    initSize=decompressed_size,
                    blockSize=1308672,
                )
            elif key_block_type == b"\x02\x00\x00\x00":
                # decompress key block
                key_block = zlib.decompress(key_block_compressed[start + 8 : end])
            # extract one single key block into a key list
            key_list += self._split_key_block(key_block)
            # notice that adler32 returns signed value
            assert adler32 == zlib.adler32(key_block) & 0xFFFFFFFF

            i += compressed_size
        return key_list

    def _split_key_block(self, key_block):
        key_list = []
        key_start_index = 0
        while key_start_index < len(key_block):
            temp = key_block[key_start_index : key_start_index + self._number_width]
            # the corresponding record's offset in record block
            key_id = unpack(
                self._number_format,
                key_block[key_start_index : key_start_index + self._number_width],
            )[0]
            # key text ends with '\x00'
            if self._encoding == "UTF-16":
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
                .decode(self._encoding, errors="ignore")
                .encode("utf-8")
                .strip()
            )
            key_start_index = key_end_index + width
            key_list += [(key_id, key_text)]
        return key_list

    def _read_header(self):
        f = open(self._fname, "rb")
        # number of bytes of header text >:big endian,I:unsigned int
        header_bytes_size = unpack(NumberFmt.be_uint, f.read(4))[0]
        header_bytes = f.read(header_bytes_size)
        # 4 bytes: adler32 checksum of header, in little endian
        adler32 = unpack(NumberFmt.le_uint, f.read(4))[0]
        assert adler32 == zlib.adler32(header_bytes) & 0xFFFFFFFF
        # mark down key block offset
        self._key_block_offset = f.tell()
        f.close()

        # header text in utf-16 encoding ending with '\x00\x00'
        header_text = header_bytes[:-2].decode("utf-16").encode("utf-8")
        header_tag = _parse_header(header_text)
        if not self._encoding:
            encoding = header_tag[b"Encoding"]
            if sys.hexversion >= 0x03000000:
                encoding = encoding.decode("utf-8")
            # GB18030 > GBK > GB2312
            if encoding in ["GBK", "GB2312"]:
                encoding = "GB18030"
            self._encoding = encoding
        # 读取标题和描述
        if b"Title" in header_tag:
            self._title = header_tag[b"Title"].decode("utf-8")
        else:
            self._title = ""

        if b"Description" in header_tag:
            self._description = header_tag[b"Description"].decode("utf-8")
        else:
            self._description = ""
        pass
        # encryption flag
        #   0x00 - no encryption
        #   0x01 - encrypt record block
        #   0x02 - encrypt key info block
        if b"Encrypted" not in header_tag or header_tag[b"Encrypted"] == b"No":
            self._encrypt = 0
        elif header_tag[b"Encrypted"] == b"Yes":
            self._encrypt = 1
        else:
            self._encrypt = int(header_tag[b"Encrypted"])

        # stylesheet attribute if present takes form of:
        #   style_number # 1-255
        #   style_begin # or ''
        #   style_end # or ''
        # store stylesheet in dict in the form of
        # {'number' : ('style_begin', 'style_end')}
        self._stylesheet = {}
        if header_tag.get(b"StyleSheet"):
            lines = header_tag[b"StyleSheet"].decode("utf-8").strip().splitlines()
            for i in range(0, len(lines), 3):
                self._stylesheet[lines[i]] = (lines[i + 1], lines[i + 2])

        # before version 2.0, number is 4 bytes integer
        # version 2.0 and above uses 8 bytes
        self._version = float(header_tag[b"GeneratedByEngineVersion"])
        if self._version < 2.0:
            self._number_width = 4
            self._number_format = NumberFmt.be_uint
        else:
            self._number_width = 8
            self._number_format = NumberFmt.be_ulonglong

        return header_tag

    def _read_keys(self):
        f = open(self._fname, "rb")
        f.seek(self._key_block_offset)

        # the following numbers could be encrypted
        if self._version >= 2.0:
            num_bytes = 8 * 5
        else:
            num_bytes = 4 * 4
        block = f.read(num_bytes)

        if self._encrypt & 1:
            if self._passcode is None:
                raise RuntimeError(
                    "user identification is needed to read encrypted file"
                )
            regcode, userid = self._passcode
            if isinstance(userid, unicode):
                userid = userid.encode("utf8")
            if self.header[b"RegisterBy"] == b"EMail":
                encrypted_key = _decrypt_regcode_by_email(regcode, userid)
            else:
                encrypted_key = _decrypt_regcode_by_deviceid(regcode, userid)
            block = _salsa_decrypt(block, encrypted_key)

        # decode this block
        sf = BytesIO(block)
        # number of key blocks
        num_key_blocks = self._read_number(sf)
        # number of entries
        self._num_entries = self._read_number(sf)
        # number of bytes of key block info after decompression
        if self._version >= 2.0:
            key_block_info_decomp_size = self._read_number(sf)
        # number of bytes of key block info
        key_block_info_size = self._read_number(sf)
        # number of bytes of key block
        key_block_size = self._read_number(sf)

        # 4 bytes: adler checksum of previous 5 numbers
        if self._version >= 2.0:
            adler32 = unpack(NumberFmt.be_uint, f.read(4))[0]
            assert adler32 == (zlib.adler32(block) & 0xFFFFFFFF)

        # read key block info, which indicates key block's compressed and
        # decompressed size
        key_block_info = f.read(key_block_info_size)
        key_block_info_list = self._decode_key_block_info(key_block_info)
        assert num_key_blocks == len(key_block_info_list)

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
                if lzo is None:
                    print("LZO compression is not supported")
                    break
                # decompress
                header = b"\xf0" + pack(NumberFmt.be_uint, decompressed_size)
                record_block = lzo.decompress(
                    record_block_compressed[start + 8 : end],
                    initSize=decompressed_size,
                    blockSize=1308672,
                )
            elif record_block_type == b"\x02\x00\x00\x00":
                # decompress
                record_block = zlib.decompress(record_block_compressed[8:])

            # notice that adler32 return signed value
            assert adler32 == zlib.adler32(record_block) & 0xFFFFFFFF

            assert len(record_block) == decompressed_size
            # split record block according to the offset info from key block
            while i < len(self._key_list):
                record_start, key_text = self._key_list[i]
                # reach the end of current record block
                if record_start - offset >= len(record_block):
                    break
                # record end index
                if i < len(self._key_list) - 1:
                    record_end = self._key_list[i + 1][0]
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
            if record_block_type == b"\x00\x00\x00\x00":
                _type = 0
                if check_block:
                    record_block = record_block_compressed[8:]
            elif record_block_type == b"\x01\x00\x00\x00":
                _type = 1
                if lzo is None:
                    print("LZO compression is not supported")
                    break
                # decompress
                header = b"\xf0" + pack(NumberFmt.be_uint, decompressed_size)
                if check_block:
                    record_block = lzo.decompress(
                        record_block_compressed[start + 8 : end],
                        initSize=decompressed_size,
                        blockSize=1308672,
                    )
            elif record_block_type == b"\x02\x00\x00\x00":
                # decompress
                _type = 2
                if check_block:
                    record_block = zlib.decompress(record_block_compressed[8:])

            # notice that adler32 return signed value
            if check_block:
                assert adler32 == zlib.adler32(record_block) & 0xFFFFFFFF
                assert len(record_block) == decompressed_size
            # split record block according to the offset info from key block
            while i < len(self._key_list):
                ### 用来保存索引信息的空字典
                index_dict = {}
                index_dict["file_pos"] = current_pos
                index_dict["compressed_size"] = compressed_size
                index_dict["decompressed_size"] = decompressed_size
                index_dict["record_block_type"] = _type
                record_start, key_text = self._key_list[i]
                index_dict["record_start"] = record_start
                index_dict["key_text"] = key_text.decode("utf-8")
                index_dict["offset"] = offset
                # reach the end of current record block
                if record_start - offset >= decompressed_size:
                    break
                # record end index
                if i < len(self._key_list) - 1:
                    record_end = self._key_list[i + 1][0]
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

    def _substitute_stylesheet(self, txt):
        # substitute stylesheet definition
        txt_list = re.split("`\d+`", txt)
        txt_tag = re.findall("`\d+`", txt)
        txt_styled = txt_list[0]
        for j, p in enumerate(txt_list[1:]):
            style = self._stylesheet[txt_tag[j][1:-1]]
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
        for compressed_size, decompressed_size in record_block_info_list:
            record_block_compressed = f.read(compressed_size)
            ###### 要得到 record_block_compressed 需要得到 compressed_size (这个可以直接记录）
            ###### 另外还需要记录当前 f 对象的位置
            ###### 使用 f.tell() 命令/ 在建立索引是需要 f.seek()
            # 4 bytes indicates block compression type
            record_block_type = record_block_compressed[:4]
            # 4 bytes adler checksum of uncompressed content
            adler32 = unpack(NumberFmt.be_uint, record_block_compressed[4:8])[0]
            # no compression
            if record_block_type == b"\x00\x00\x00\x00":
                record_block = record_block_compressed[8:]
            # lzo compression
            elif record_block_type == b"\x01\x00\x00\x00":
                if lzo is None:
                    print("LZO compression is not supported")
                    break
                # decompress
                header = b"\xf0" + pack(NumberFmt.be_uint, decompressed_size)
                record_block = lzo.decompress(
                    record_block_compressed[8:],
                    initSize=decompressed_size,
                    blockSize=1308672,
                )
            # zlib compression
            elif record_block_type == b"\x02\x00\x00\x00":
                # decompress
                record_block = zlib.decompress(record_block_compressed[8:])
            ###### 这里比较重要的是先要得到 record_block, 而 record_block 是解压得到的，其中一共有三种解压方法
            ###### 需要的信息有 record_block_compressed, decompress_size,
            ###### record_block_type
            ###### 另外还需要校验信息 adler32
            # notice that adler32 return signed value
            assert adler32 == zlib.adler32(record_block) & 0xFFFFFFFF

            assert len(record_block) == decompressed_size
            # split record block according to the offset info from key block
            while i < len(self._key_list):
                record_start, key_text = self._key_list[i]
                # reach the end of current record block
                if record_start - offset >= len(record_block):
                    break
                # record end index
                if i < len(self._key_list) - 1:
                    record_end = self._key_list[i + 1][0]
                else:
                    record_end = len(record_block) + offset
                i += 1
                #############需要得到 record_block , record_start, record_end,
                #############offset
                record = record_block[record_start - offset : record_end - offset]
                # convert to utf-8
                record = (
                    record.decode(self._encoding, errors="ignore")
                    .strip("\x00")
                    .encode("utf-8")
                )
                # substitute styles
                #############是否替换样式表
                if self._substyle and self._stylesheet:
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
        index_dict_list = []
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
        for compressed_size, decompressed_size in record_block_info_list:
            current_pos = f.tell()
            record_block_compressed = f.read(compressed_size)
            ###### 要得到 record_block_compressed 需要得到 compressed_size (这个可以直接记录）
            ###### 另外还需要记录当前 f 对象的位置
            ###### 使用 f.tell() 命令/ 在建立索引是需要 f.seek()
            # 4 bytes indicates block compression type
            record_block_type = record_block_compressed[:4]
            # 4 bytes adler checksum of uncompressed content
            adler32 = unpack(NumberFmt.be_uint, record_block_compressed[4:8])[0]
            # no compression
            if record_block_type == b"\x00\x00\x00\x00":
                _type = 0
                record_block = record_block_compressed[8:]
            # lzo compression
            elif record_block_type == b"\x01\x00\x00\x00":
                _type = 1
                if lzo is None:
                    print("LZO compression is not supported")
                    break
                # decompress
                header = b"\xf0" + pack(NumberFmt.be_uint, decompressed_size)
                if check_block:
                    record_block = lzo.decompress(
                        record_block_compressed[8:],
                        initSize=decompressed_size,
                        blockSize=1308672,
                    )
            # zlib compression
            elif record_block_type == b"\x02\x00\x00\x00":
                # decompress
                _type = 2
                if check_block:
                    record_block = zlib.decompress(record_block_compressed[8:])
            ###### 这里比较重要的是先要得到 record_block, 而 record_block 是解压得到的，其中一共有三种解压方法
            ###### 需要的信息有 record_block_compressed, decompress_size,
            ###### record_block_type
            ###### 另外还需要校验信息 adler32
            # notice that adler32 return signed value
            if check_block:
                assert adler32 == zlib.adler32(record_block) & 0xFFFFFFFF
                assert len(record_block) == decompressed_size
            # split record block according to the offset info from key block
            while i < len(self._key_list):
                ### 用来保存索引信息的空字典
                index_dict = {}
                index_dict["file_pos"] = current_pos
                index_dict["compressed_size"] = compressed_size
                index_dict["decompressed_size"] = decompressed_size
                index_dict["record_block_type"] = _type
                record_start, key_text = self._key_list[i]
                index_dict["record_start"] = record_start
                index_dict["key_text"] = key_text.decode("utf-8")
                index_dict["offset"] = offset
                # reach the end of current record block
                if record_start - offset >= decompressed_size:
                    break
                # record end index
                if i < len(self._key_list) - 1:
                    record_end = self._key_list[i + 1][0]
                else:
                    record_end = decompressed_size + offset
                index_dict["record_end"] = record_end
                i += 1
                #############需要得到 record_block , record_start, record_end,
                #############offset
                if check_block:
                    record = record_block[record_start - offset : record_end - offset]
                    # convert to utf-8
                    record = (
                        record.decode(self._encoding, errors="ignore")
                        .strip("\x00")
                        .encode("utf-8")
                    )
                    # substitute styles
                    #############是否替换样式表
                    if self._substyle and self._stylesheet:
                        record = self._substitute_stylesheet(record)
                index_dict_list.append(index_dict)

            offset += decompressed_size
            size_counter += compressed_size
        # todo: 注意！！！
        # assert(size_counter == record_block_size)
        f.close
        # 这里比 mdd 部分稍有不同，应该还需要传递编码以及样式表信息
        meta = {}
        meta["encoding"] = self._encoding
        meta["stylesheet"] = json.dumps(self._stylesheet)
        meta["title"] = self._title
        meta["description"] = self._description

        return {"index_dict_list": index_dict_list, "meta": meta}


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
        if type(args.filename) is unicode:
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
        if type(mdd_filename) is unicode:
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
                sf.write(b"\r\n".join(mdx.header["StyleSheet"].splitlines()))
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
