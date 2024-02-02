# -*- coding: utf-8 -*-

# http://dean.edwards.name/packer/
# http://dean.edwards.name/unpacker/
import re

from userdecompress import decompressFromBase64


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


def hex_to_ascii(raw):
    return re.sub(r"\\x([0-9a-e]{2})", lambda match: match.group(1).decode("hex"), raw)


def splic_to_split(match):
    content = decompressFromBase64(match.group(1))
    return u"'{}'.split('|')".format(content)


def decode_packed_codes(code):
    code = hex_to_ascii(code)
    code = re.sub(r"'([A-Za-z0-9+/=]+)'\['splic'\]\('\|'\)", splic_to_split, code)
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


if __name__ == '__main__':
    raw = r"""
window["eval"](function(p,a,c,k,e,d){e=function(c){return(c<a?"":e(parseInt(c/a)))+((c=c%a)>35?String.fromCharCode(c+29):c.toString(36))};if(!''.replace(/^/,String)){while(c--)d[e(c)]=k[c]||e(c);k=[function(e){return d[e]}];e=function(){return'\\w+'};c=1;};while(c--)if(k[c])p=p.replace(new RegExp('\\b'+e(c)+'\\b','g'),k[c]);return p;}('d.g({"h":5,"e":"f","i":"5.2","l":m,"j":"4","k":["8.2.3","7.2.3","a.2.3","9.2.3","b.2.3","c.2.3"],"x":y,"z":6,"A":"/C/t/B/4/","w":1,"q":"","n":o,"u":0,"v":{"r":"s"}}).p();',39,39,'D7BWAcHNgdwUwEbmIGm8AMbB7asATATjwHYAWEcASwGMB9DHYCmjARgatrVMY4GY2m0AVn4cAbMADKAWQASwBADsAhgFs4wQJ5OgKOsAGgAVAmqaAS7UBE1oDn4wAbywcisgARJQBcl88gBN5jYJWVrgAM3IAGzgAZ293YGI6NHoFOAAPRwBJD2jmUVF6cAAnOGSFckd5IIB7SgBrakpKYBU3YQQAGTxwUEhIHIA1AC8AUTQATQAxQgB1ZjgbHpgyPIA3VOBQoOXnRwBXcMDC0IALOA9/JSDQ9RCFBic94EdQhLb9gE8Fah6Ej3BQ5iA'['splic']('|'),0,{}))
        """
    print(decode_packed_codes(raw))
