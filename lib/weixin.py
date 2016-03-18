#!/usr/bin/env python
# -*- coding:utf-8 -*-

import re, base64

from Crypto.Cipher import AES

def process_eqs(html):
    pattern = (
        r'SogouEncrypt.setKv\("(\w+)","(\d)"\)'
        r'.*?'
        r'SogouEncrypt.encryptquery\("(\w+)","(\w+)"\)'
    )
    m = re.findall(pattern, html, re.S)
    key, level, secret, setting = m[0]

    eqs = _cipher_eqs(key, secret, setting)

    return eqs, level   


def _cipher_eqs(key, secret, setting='sogou'):
    """
    SogouEncrypt.encryptquery
    """
    assert len(key) == 11

    ss = setting.split('-')

    # function g
    if len(ss) > 2:
        h = ss[2]
    else:
        h = ss[0]

    # function f
    if len(h) > 5:
        n = h[:-5]
    else:
        n = h + (5 - len(h)) * 's'

    key += n

    data = secret + 'hdq=' + setting
    # padding data
    length = 16 - (len(data) % 16)
    data += chr(length) * length

    IV = b'0000000000000000'
    cipher = AES.new(_to_bytes(key), AES.MODE_CBC, IV)
    # encrypt data
    data = cipher.encrypt(_to_bytes(data))
    data = _to_unicode(base64.b64encode(data))

    # function e
    rv = ''
    i = 0
    for m in range(len(data)):
        rv += data[m]
        if (m == pow(2, i)) and i < 5:
            rv += n[i]
            i += 1
    return rv


def _to_bytes(text):
    if isinstance(text, bytes):
        return text
    return text.encode('utf-8')


def _to_unicode(text):
    if isinstance(text, str):
        return text
    return text.decode('utf-8')