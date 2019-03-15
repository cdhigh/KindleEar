# -*- coding: utf-8 -*-

# http://dean.edwards.name/packer/
# http://dean.edwards.name/unpacker/
import re


# https://github.com/ytdl-org/youtube-dl/blob/befa4708fd2165b85d04002c3845adf191d34302/youtube_dl/utils.py
PACKED_CODES_RE = re.compile(r"}\('(.+)',(\d+),(\d+),'([^']+)'\.split\('\|'\)")


def encode_base_n(num, n, table=None):
    FULL_TABLE = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if not table:
        table = FULL_TABLE[:n]

    if n > len(table):
        raise ValueError("base %d exceeds table length %d" % (n, len(table)))

    if num == 0:
        return table[0]

    ret = ""
    while num:
        ret = table[num % n] + ret
        num = num // n
    return ret


def decode_packed_codes(code):
    mobj = PACKED_CODES_RE.search(code)
    obfucasted_code, base, count, symbols = mobj.groups()
    base = int(base)
    count = int(count)
    symbols = symbols.split("|")
    symbol_table = {}

    while count:
        count -= 1
        base_n_count = encode_base_n(count, base)
        symbol_table[base_n_count] = symbols[count] or base_n_count

    return re.sub(
        r"\b(\w+)\b", lambda mobj: symbol_table[mobj.group(0)], obfucasted_code
    )
