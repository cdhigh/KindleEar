#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import io
from functools import partial

try:
    import gtts
except ImportError:
    gtts = None

try:
    from google.cloud import texttospeech
except ImportError:
    texttospeech = None

from .tts_base import TTSBase

#键为BCP-47语种代码，值为语音名字列表，因为gtts不支持语音选择，所以列表为空
gtts_languages = {
    'af': [],
    'ar': [],
    'bg': [],
    'bn': [],
    'bs': [],
    'ca': [],
    'cs': [],
    'da': [],
    'de': [],
    'el': [],
    'en': [],
    'es': [],
    'et': [],
    'fi': [],
    'fr': [],
    'gu': [],
    'hi': [],
    'hr': [],
    'hu': [],
    'id': [],
    'is': [],
    'it': [],
    'iw': [],
    'ja': [],
    'jw': [],
    'km': [],
    'kn': [],
    'ko': [],
    'la': [],
    'lv': [],
    'ml': [],
    'mr': [],
    'ms': [],
    'my': [],
    'ne': [],
    'nl': [],
    'no': [],
    'pl': [],
    'pt': [],
    'ro': [],
    'ru': [],
    'si': [],
    'sk': [],
    'sq': [],
    'sr': [],
    'su': [],
    'sv': [],
    'sw': [],
    'ta': [],
    'te': [],
    'th': [],
    'tl': [],
    'tr': [],
    'uk': [],
    'ur': [],
    'vi': [],
    'zh-CN': [],
    'zh-TW': [],
    'zh': [],
}

#键为BCP-47语种代码，值为语音名字列表
googletts_languages = {
    'af-ZA': ['af-ZA-Standard-A'],
    'am-ET': ['am-ET-Standard-A', 'am-ET-Standard-B', 'am-ET-Wavenet-A', 'am-ET-Wavenet-B'],
    'ar-XA': ['ar-XA-Standard-A', 'ar-XA-Standard-B', 'ar-XA-Standard-C', 'ar-XA-Standard-D', 'ar-XA-Wavenet-A', 'ar-XA-Wavenet-B', 'ar-XA-Wavenet-C', 'ar-XA-Wavenet-D'],
    'bg-BG': ['bg-BG-Standard-A'],
    'bn-IN': ['bn-IN-Standard-A', 'bn-IN-Standard-B', 'bn-IN-Standard-C', 'bn-IN-Standard-D', 'bn-IN-Wavenet-A', 'bn-IN-Wavenet-B', 'bn-IN-Wavenet-C', 'bn-IN-Wavenet-D'],
    'ca-ES': ['ca-ES-Standard-A'],
    'cmn-CN': ['cmn-CN-Standard-A', 'cmn-CN-Standard-B', 'cmn-CN-Standard-C', 'cmn-CN-Standard-D', 'cmn-CN-Wavenet-A', 'cmn-CN-Wavenet-B', 'cmn-CN-Wavenet-C', 'cmn-CN-Wavenet-D'],
    'cmn-TW': ['cmn-TW-Standard-A', 'cmn-TW-Standard-B', 'cmn-TW-Standard-C', 'cmn-TW-Wavenet-A', 'cmn-TW-Wavenet-B', 'cmn-TW-Wavenet-C'],
    'cs-CZ': ['cs-CZ-Standard-A', 'cs-CZ-Wavenet-A'],
    'da-DK': ['da-DK-Neural2-D', 'da-DK-Standard-A', 'da-DK-Standard-C', 'da-DK-Standard-D', 'da-DK-Standard-E', 'da-DK-Wavenet-A', 'da-DK-Wavenet-C', 'da-DK-Wavenet-D', 'da-DK-Wavenet-E'],
    'de-DE': ['de-DE-Neural2-A', 'de-DE-Neural2-B', 'de-DE-Neural2-C', 'de-DE-Neural2-D', 'de-DE-Neural2-F', 'de-DE-Polyglot-1', 'de-DE-Standard-A', 'de-DE-Standard-B', 'de-DE-Standard-C', 'de-DE-Standard-D', 'de-DE-Standard-E', 'de-DE-Standard-F', 'de-DE-Studio-B', 'de-DE-Studio-C', 'de-DE-Wavenet-A', 'de-DE-Wavenet-B', 'de-DE-Wavenet-C', 'de-DE-Wavenet-D', 'de-DE-Wavenet-E', 'de-DE-Wavenet-F'],
    'el-GR': ['el-GR-Standard-A', 'el-GR-Wavenet-A'],
    'en-AU': ['en-AU-Neural2-A', 'en-AU-Neural2-B', 'en-AU-Neural2-C', 'en-AU-Neural2-D', 'en-AU-News-E', 'en-AU-News-F', 'en-AU-News-G', 'en-AU-Polyglot-1', 'en-AU-Standard-A', 'en-AU-Standard-B', 'en-AU-Standard-C', 'en-AU-Standard-D', 'en-AU-Wavenet-A', 'en-AU-Wavenet-B', 'en-AU-Wavenet-C', 'en-AU-Wavenet-D'],
    'en-GB': ['en-GB-Neural2-A', 'en-GB-Neural2-B', 'en-GB-Neural2-C', 'en-GB-Neural2-D', 'en-GB-Neural2-F', 'en-GB-News-G', 'en-GB-News-H', 'en-GB-News-I', 'en-GB-News-J', 'en-GB-News-K', 'en-GB-News-L', 'en-GB-News-M', 'en-GB-Standard-A', 'en-GB-Standard-B', 'en-GB-Standard-C', 'en-GB-Standard-D', 'en-GB-Standard-F', 'en-GB-Studio-B', 'en-GB-Studio-C', 'en-GB-Wavenet-A', 'en-GB-Wavenet-B', 'en-GB-Wavenet-C', 'en-GB-Wavenet-D', 'en-GB-Wavenet-F'],
    'en-IN': ['en-IN-Neural2-A', 'en-IN-Neural2-B', 'en-IN-Neural2-C', 'en-IN-Neural2-D', 'en-IN-Standard-A', 'en-IN-Standard-B', 'en-IN-Standard-C', 'en-IN-Standard-D', 'en-IN-Wavenet-A', 'en-IN-Wavenet-B', 'en-IN-Wavenet-C', 'en-IN-Wavenet-D'],
    'en-US': ['en-US-Casual-K', 'en-US-Journey-D', 'en-US-Journey-F', 'en-US-Neural2-A', 'en-US-Neural2-C', 'en-US-Neural2-D', 'en-US-Neural2-E', 'en-US-Neural2-F', 'en-US-Neural2-G', 'en-US-Neural2-H', 'en-US-Neural2-I', 'en-US-Neural2-J', 'en-US-News-K', 'en-US-News-L', 'en-US-News-N', 'en-US-Polyglot-1', 'en-US-Standard-A', 'en-US-Standard-B', 'en-US-Standard-C', 'en-US-Standard-D', 'en-US-Standard-E', 'en-US-Standard-F', 'en-US-Standard-G', 'en-US-Standard-H', 'en-US-Standard-I', 'en-US-Standard-J', 'en-US-Studio-O', 'en-US-Studio-Q', 'en-US-Wavenet-A', 'en-US-Wavenet-B', 'en-US-Wavenet-C', 'en-US-Wavenet-D', 'en-US-Wavenet-E', 'en-US-Wavenet-F', 'en-US-Wavenet-G', 'en-US-Wavenet-H', 'en-US-Wavenet-I', 'en-US-Wavenet-J'],
    'es-ES': ['es-ES-Neural2-A', 'es-ES-Neural2-B', 'es-ES-Neural2-C', 'es-ES-Neural2-D', 'es-ES-Neural2-E', 'es-ES-Neural2-F', 'es-ES-Polyglot-1', 'es-ES-Standard-A', 'es-ES-Standard-B', 'es-ES-Standard-C', 'es-ES-Standard-D', 'es-ES-Studio-C', 'es-ES-Studio-F', 'es-ES-Wavenet-B', 'es-ES-Wavenet-C', 'es-ES-Wavenet-D'],
    'es-US': ['es-US-Neural2-A', 'es-US-Neural2-B', 'es-US-Neural2-C', 'es-US-News-D', 'es-US-News-E', 'es-US-News-F', 'es-US-News-G', 'es-US-Polyglot-1', 'es-US-Standard-A', 'es-US-Standard-B', 'es-US-Standard-C', 'es-US-Studio-B', 'es-US-Wavenet-A', 'es-US-Wavenet-B', 'es-US-Wavenet-C'],
    'eu-ES': ['eu-ES-Standard-A'],
    'fi-FI': ['fi-FI-Standard-A', 'fi-FI-Wavenet-A'],
    'fil-PH': ['fil-PH-Standard-A', 'fil-PH-Standard-B', 'fil-PH-Standard-C', 'fil-PH-Standard-D', 'fil-PH-Wavenet-A', 'fil-PH-Wavenet-B', 'fil-PH-Wavenet-C', 'fil-PH-Wavenet-D', 'fil-ph-Neural2-A', 'fil-ph-Neural2-D'],
    'fr-CA': ['fr-CA-Neural2-A', 'fr-CA-Neural2-B', 'fr-CA-Neural2-C', 'fr-CA-Neural2-D', 'fr-CA-Standard-A', 'fr-CA-Standard-B', 'fr-CA-Standard-C', 'fr-CA-Standard-D', 'fr-CA-Wavenet-A', 'fr-CA-Wavenet-B', 'fr-CA-Wavenet-C', 'fr-CA-Wavenet-D'],
    'fr-FR': ['fr-FR-Neural2-A', 'fr-FR-Neural2-B', 'fr-FR-Neural2-C', 'fr-FR-Neural2-D', 'fr-FR-Neural2-E', 'fr-FR-Polyglot-1', 'fr-FR-Standard-A', 'fr-FR-Standard-B', 'fr-FR-Standard-C', 'fr-FR-Standard-D', 'fr-FR-Standard-E', 'fr-FR-Studio-A', 'fr-FR-Studio-D', 'fr-FR-Wavenet-A', 'fr-FR-Wavenet-B', 'fr-FR-Wavenet-C', 'fr-FR-Wavenet-D', 'fr-FR-Wavenet-E'],
    'gl-ES': ['gl-ES-Standard-A'],
    'gu-IN': ['gu-IN-Standard-A', 'gu-IN-Standard-B', 'gu-IN-Standard-C', 'gu-IN-Standard-D', 'gu-IN-Wavenet-A', 'gu-IN-Wavenet-B', 'gu-IN-Wavenet-C', 'gu-IN-Wavenet-D'],
    'he-IL': ['he-IL-Standard-A', 'he-IL-Standard-B', 'he-IL-Standard-C', 'he-IL-Standard-D', 'he-IL-Wavenet-A', 'he-IL-Wavenet-B', 'he-IL-Wavenet-C', 'he-IL-Wavenet-D'],
    'hi-IN': ['hi-IN-Neural2-A', 'hi-IN-Neural2-B', 'hi-IN-Neural2-C', 'hi-IN-Neural2-D', 'hi-IN-Standard-A', 'hi-IN-Standard-B', 'hi-IN-Standard-C', 'hi-IN-Standard-D', 'hi-IN-Wavenet-A', 'hi-IN-Wavenet-B', 'hi-IN-Wavenet-C', 'hi-IN-Wavenet-D'],
    'hu-HU': ['hu-HU-Standard-A', 'hu-HU-Wavenet-A'],
    'id-ID': ['id-ID-Standard-A', 'id-ID-Standard-B', 'id-ID-Standard-C', 'id-ID-Standard-D', 'id-ID-Wavenet-A', 'id-ID-Wavenet-B', 'id-ID-Wavenet-C', 'id-ID-Wavenet-D'],
    'is-IS': ['is-IS-Standard-A'],
    'it-IT': ['it-IT-Neural2-A', 'it-IT-Neural2-C', 'it-IT-Standard-A', 'it-IT-Standard-B', 'it-IT-Standard-C', 'it-IT-Standard-D', 'it-IT-Wavenet-A', 'it-IT-Wavenet-B', 'it-IT-Wavenet-C', 'it-IT-Wavenet-D'],
    'ja-JP': ['ja-JP-Neural2-B', 'ja-JP-Neural2-C', 'ja-JP-Neural2-D', 'ja-JP-Standard-A', 'ja-JP-Standard-B', 'ja-JP-Standard-C', 'ja-JP-Standard-D', 'ja-JP-Wavenet-A', 'ja-JP-Wavenet-B', 'ja-JP-Wavenet-C', 'ja-JP-Wavenet-D'],
    'kn-IN': ['kn-IN-Standard-A', 'kn-IN-Standard-B', 'kn-IN-Standard-C', 'kn-IN-Standard-D', 'kn-IN-Wavenet-A', 'kn-IN-Wavenet-B', 'kn-IN-Wavenet-C', 'kn-IN-Wavenet-D'],
    'ko-KR': ['ko-KR-Neural2-A', 'ko-KR-Neural2-B', 'ko-KR-Neural2-C', 'ko-KR-Standard-A', 'ko-KR-Standard-B', 'ko-KR-Standard-C', 'ko-KR-Standard-D', 'ko-KR-Wavenet-A', 'ko-KR-Wavenet-B', 'ko-KR-Wavenet-C', 'ko-KR-Wavenet-D'],
    'lt-LT': ['lt-LT-Standard-A'],
    'lv-LV': ['lv-LV-Standard-A'],
    'ml-IN': ['ml-IN-Standard-A', 'ml-IN-Standard-B', 'ml-IN-Standard-C', 'ml-IN-Standard-D', 'ml-IN-Wavenet-A', 'ml-IN-Wavenet-B', 'ml-IN-Wavenet-C', 'ml-IN-Wavenet-D'],
    'mr-IN': ['mr-IN-Standard-A', 'mr-IN-Standard-B', 'mr-IN-Standard-C', 'mr-IN-Wavenet-A', 'mr-IN-Wavenet-B', 'mr-IN-Wavenet-C'],
    'ms-MY': ['ms-MY-Standard-A', 'ms-MY-Standard-B', 'ms-MY-Standard-C', 'ms-MY-Standard-D', 'ms-MY-Wavenet-A', 'ms-MY-Wavenet-B', 'ms-MY-Wavenet-C', 'ms-MY-Wavenet-D'],
    'nb-NO': ['nb-NO-Standard-A', 'nb-NO-Standard-B', 'nb-NO-Standard-C', 'nb-NO-Standard-D', 'nb-NO-Standard-E', 'nb-NO-Wavenet-A', 'nb-NO-Wavenet-B', 'nb-NO-Wavenet-C', 'nb-NO-Wavenet-D', 'nb-NO-Wavenet-E'],
    'nl-BE': ['nl-BE-Standard-A', 'nl-BE-Standard-B', 'nl-BE-Wavenet-A', 'nl-BE-Wavenet-B'],
    'nl-NL': ['nl-NL-Standard-A', 'nl-NL-Standard-B', 'nl-NL-Standard-C', 'nl-NL-Standard-D', 'nl-NL-Standard-E', 'nl-NL-Wavenet-A', 'nl-NL-Wavenet-B', 'nl-NL-Wavenet-C', 'nl-NL-Wavenet-D', 'nl-NL-Wavenet-E'],
    'pa-IN': ['pa-IN-Standard-A', 'pa-IN-Standard-B', 'pa-IN-Standard-C', 'pa-IN-Standard-D', 'pa-IN-Wavenet-A', 'pa-IN-Wavenet-B', 'pa-IN-Wavenet-C', 'pa-IN-Wavenet-D'],
    'pl-PL': ['pl-PL-Standard-A', 'pl-PL-Standard-B', 'pl-PL-Standard-C', 'pl-PL-Standard-D', 'pl-PL-Standard-E', 'pl-PL-Wavenet-A', 'pl-PL-Wavenet-B', 'pl-PL-Wavenet-C', 'pl-PL-Wavenet-D', 'pl-PL-Wavenet-E'],
    'pt-BR': ['pt-BR-Neural2-A', 'pt-BR-Neural2-B', 'pt-BR-Neural2-C', 'pt-BR-Standard-A', 'pt-BR-Standard-B', 'pt-BR-Standard-C', 'pt-BR-Studio-B', 'pt-BR-Studio-C', 'pt-BR-Wavenet-A', 'pt-BR-Wavenet-B', 'pt-BR-Wavenet-C'],
    'pt-PT': ['pt-PT-Standard-A', 'pt-PT-Standard-B', 'pt-PT-Standard-C', 'pt-PT-Standard-D', 'pt-PT-Wavenet-A', 'pt-PT-Wavenet-B', 'pt-PT-Wavenet-C', 'pt-PT-Wavenet-D'],
    'ro-RO': ['ro-RO-Standard-A', 'ro-RO-Wavenet-A'],
    'ru-RU': ['ru-RU-Standard-A', 'ru-RU-Standard-B', 'ru-RU-Standard-C', 'ru-RU-Standard-D', 'ru-RU-Standard-E', 'ru-RU-Wavenet-A', 'ru-RU-Wavenet-B', 'ru-RU-Wavenet-C', 'ru-RU-Wavenet-D', 'ru-RU-Wavenet-E'],
    'sk-SK': ['sk-SK-Standard-A', 'sk-SK-Wavenet-A'],
    'sr-RS': ['sr-RS-Standard-A'],
    'sv-SE': ['sv-SE-Standard-A', 'sv-SE-Standard-B', 'sv-SE-Standard-C', 'sv-SE-Standard-D', 'sv-SE-Standard-E', 'sv-SE-Wavenet-A', 'sv-SE-Wavenet-B', 'sv-SE-Wavenet-C', 'sv-SE-Wavenet-D', 'sv-SE-Wavenet-E'],
    'ta-IN': ['ta-IN-Standard-A', 'ta-IN-Standard-B', 'ta-IN-Standard-C', 'ta-IN-Standard-D', 'ta-IN-Wavenet-A', 'ta-IN-Wavenet-B', 'ta-IN-Wavenet-C', 'ta-IN-Wavenet-D'],
    'te-IN': ['te-IN-Standard-A', 'te-IN-Standard-B'],
    'th-TH': ['th-TH-Neural2-C', 'th-TH-Standard-A'],
    'tr-TR': ['tr-TR-Standard-A', 'tr-TR-Standard-B', 'tr-TR-Standard-C', 'tr-TR-Standard-D', 'tr-TR-Standard-E', 'tr-TR-Wavenet-A', 'tr-TR-Wavenet-B', 'tr-TR-Wavenet-C', 'tr-TR-Wavenet-D', 'tr-TR-Wavenet-E'],
    'uk-UA': ['uk-UA-Standard-A', 'uk-UA-Wavenet-A'],
    'vi-VN': ['vi-VN-Neural2-A', 'vi-VN-Neural2-D', 'vi-VN-Standard-A', 'vi-VN-Standard-B', 'vi-VN-Standard-C', 'vi-VN-Standard-D', 'vi-VN-Wavenet-A', 'vi-VN-Wavenet-B', 'vi-VN-Wavenet-C', 'vi-VN-Wavenet-D'],
    'yue-HK': ['yue-HK-Standard-A', 'yue-HK-Standard-B', 'yue-HK-Standard-C', 'yue-HK-Standard-D'],
}
        
class GoogleWebTTSFree(TTSBase):
    name = 'GoogleWebTTS(Free)'
    alias = 'Google Web TTS (Free)'
    need_api_key = False
    api_key_hint = ''
    default_api_host = 'https://translate.google.com'
    default_timeout = 60
    request_interval = 10 #额外的，好像每天只允许50个请求
    max_len_per_request = 1666
    languages = gtts_languages
    
    def __init__(self, params):
        super().__init__(params)
        params = params or {}
        self.params = params
        host = self.host or 'google.com'
        self.tld = host.split('google.')[-1] if 'google.' in host else 'com'
        if self.language not in self.languages:
            self.language = 'en'
        slow = self.rate in ('slow', 'x-slow')
        self.ttsFunc = partial(gtts.gTTS, tld=self.tld, lang=self.language, slow=slow, 
            lang_check=False, timeout=self.timeout)
        
    #开始进行tts转换，返回 (mime，音频二进制)
    def tts(self, text):
        buf = io.BytesIO()
        self.ttsFunc(text=text).write_to_fp(buf)
        return ('audio/mpeg', buf.getvalue())

#https://cloud.google.com/text-to-speech/docs/create-audio#text-to-speech-text-python
#https://cloud.google.com/text-to-speech/pricing
#需要先启用 'Cloud Text-to-Speech API'
#https://console.cloud.google.com/apis/api/texttospeech.googleapis.com/overview
class GoogleTextToSpeech(TTSBase):
    name = 'GoogleTextToSpeech(GAE only)'
    alias = 'Google Text To Speech (GAE only)'
    need_api_key = False
    api_key_hint = ''
    default_api_host = ''
    default_timeout = 60
    #https://cloud.google.com/text-to-speech/quotas
    request_interval = 2
    max_len_per_request = 1666
    languages = googletts_languages
    
    def __init__(self, params):
        super().__init__(params)
        if self.language not in self.languages:
            self.language = 'en'
        self.client = texttospeech.TextToSpeechClient()
        #Names of voices can be retrieved with client.list_voices().
        #omit ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        self.voiceCfg = texttospeech.VoiceSelectionParams(language_code=self.language, name=self.voice)
        self.audioCfg = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        self.reqDict = {"voice": self.voice, "audio_config": self.audioCfg}

    #开始进行tts转换，返回 (mime，音频二进制)
    #Limit is 5000 bytes per request
    #https://cloud.google.com/text-to-speech/quotas
    def tts(self, text):
        self.reqDict["ssml"] = self.ssml(text)
        resp = self.client.synthesize_speech(request=self.reqDict)
        return ('audio/mpeg', resp.audio_content)

    #获取支持的语音列表，注意，这个会返回一个超级大的json对象
    #或者可以直接到网页去查询
    #https://cloud.google.com/text-to-speech/docs/voices
    def voice_list(self):
        voices = self.client.list_voices()
        return voices
