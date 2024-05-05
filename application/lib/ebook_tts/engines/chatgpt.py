#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#chatgpt text-to-speech api interface
#Author: cdhigh<https://github.com/cdhigh>
import json
from urllib.parse import urljoin
from urlopener import UrlOpener
from .tts_base import TTSBase

#键为BCP-47语种代码，值为语音名字列表，chatgpt暂不支持语言选择
chatgpt_languages = {'und': ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']}

class ChatGptTTS(TTSBase):
    name = 'ChatGptTTS'
    alias = 'ChatGPT TTS'
    need_api_key = True
    api_key_hint = 'Api key'
    default_api_host = 'https://api.openai.com/v1/audio/speech'
    default_timeout = 60
    request_interval = 20
    max_len_per_request = 1600
    languages = chatgpt_languages
    regions = {}
    engine_url = 'https://platform.openai.com/docs/api-reference/audio/createSpeech'
    region_url = ''
    voice_url = 'https://platform.openai.com/docs/guides/text-to-speech/voice-options'
    language_url = ''
    
    def __init__(self, params):
        super().__init__(params)
        self.headers = {'Authorization': f'Bearer {self.key}',
            'Content-Type': 'application/json'}

        #相对百分比转换为小数
        speed = self.prosody_attributes['rate'].get(self.rate, '+0%')
        self.data = {'model': self.model or 'tts-1',
            'voice': self.voice or 'nova',
            'response_format': 'mp3',
            'speed': (int(speed.strip('%')) / 100) + 1}
        self.opener = UrlOpener(timeout=self.timeout, headers=self.headers)

    #获取支持的语音列表
    def voice_list(self):
        return self.languages.get('und')

    #文本转换为语音，返回(mime, audio)
    def tts(self, text):
        self.data['input'] = text
        resp = self.opener.open(self.host, data=json.dumps(self.data))
        if resp.status_code == 200:
            #返回的是stream流形式
            content = b''.join(line for line in resp.iter_content(chunk_size=None))
            return ('audio/mpeg', content)
        else:
            default_log.debug(resp.text)
            raise Exception(self.opener.CodeMap(resp.status_code))
