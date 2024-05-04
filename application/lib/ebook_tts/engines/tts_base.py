#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# 调用在线文本转语音TTS基类
from xml.etree import ElementTree as ET

class TTSBase:
    name = ''
    alias = ''
    need_api_key = False
    api_key_hint = ''
    default_api_host = ''
    default_timeout = 60
    request_interval = 1
    max_len_per_request = 500
    languages = {}
    regions = {}
    engine_url = '' #一个链接，关于引擎的介绍链接网页
    region_url = '' #一个链接，可以在这个链接网页上找到可用的区域
    voice_url = '' #一个链接，可以在这个网页上找到语音名称列表
    language_url = '' #一个链接，可以在这个网页上找到支持的语种列表

    #语音语调的允许常量值列表，除了使用常量值，也可以使用一个正负数值，比如 100%, +1.5, -30.00% 等
    prosody_attributes = {
        'rate': {'x-slow': '-50%', 'slow': '-25%', 'medium': '+0%', 'fast': '+25%', 'x-fast': '+50%'},
        'pitch': {'x-low': '-50Hz', 'low': '-25Hz', 'medium': '+0Hz', 'high': '+25Hz', 'x-high': '+50Hz'},
        'volume': {'silent': '-100%', 'x-soft': '-50%', 'soft': '-25%', 'medium': '+0%', 'loud': '+25%', 'x-loud': '+50%'}
    }

    def __init__(self, params):
        params = params or {}
        self.params = params
        self.language = params.get('language', 'en-US')
        self.voice = params.get('voice', '')
        self.rate = params.get('rate', 'medium')
        self.pitch = params.get('pitch', 'medium')
        self.volume = params.get('volume', 'medium')
        self.key = params.get('api_key', '')
        self.host = params.get('api_host', TTSBase.default_api_host)
        self.timeout = params.get('timeout', TTSBase.default_timeout)
        self.region = params.get('region', '')

    #构建一个简单的ssml字符串，返回一个utf-8编码后的二进制字节串
    #text, language, voice: 要转换的文本，语种代码，语音名字
    #pitch: 音调, rate: 语速, volume: 音量
    def ssml(self, text):
        root = ET.Element('speak', version='1.0', xmlns='http://www.w3.org/2001/10/synthesis')
        root.set('xml:lang', self.language)
        voiceNode = ET.SubElement(root, 'voice', name=self.voice)
        prosody = ET.SubElement(voiceNode, 'prosody', pitch=self.pitch, rate=self.rate, volume=self.volume)
        prosody.text = text #xml模块会自动转义非法字符串
        return ET.tostring(root, encoding="utf-8", method="xml", xml_declaration=False)
