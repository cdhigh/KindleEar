#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import io

try:
    import gtts
except ImportError:
    gtts = None

try:
    from google.cloud import texttospeech
except ImportError:
    texttospeech = None

gtts_languages = {
  "af": "Afrikaans",
  "ar": "Arabic",
  "bg": "Bulgarian",
  "bn": "Bengali",
  "bs": "Bosnian",
  "ca": "Catalan",
  "cs": "Czech",
  "da": "Danish",
  "de": "German",
  "el": "Greek",
  "en": "English",
  "es": "Spanish",
  "et": "Estonian",
  "fi": "Finnish",
  "fr": "French",
  "gu": "Gujarati",
  "hi": "Hindi",
  "hr": "Croatian",
  "hu": "Hungarian",
  "id": "Indonesian",
  "is": "Icelandic",
  "it": "Italian",
  "iw": "Hebrew",
  "ja": "Japanese",
  "jw": "Javanese",
  "km": "Khmer",
  "kn": "Kannada",
  "ko": "Korean",
  "la": "Latin",
  "lv": "Latvian",
  "ml": "Malayalam",
  "mr": "Marathi",
  "ms": "Malay",
  "my": "Myanmar (Burmese)",
  "ne": "Nepali",
  "nl": "Dutch",
  "no": "Norwegian",
  "pl": "Polish",
  "pt": "Portuguese",
  "ro": "Romanian",
  "ru": "Russian",
  "si": "Sinhala",
  "sk": "Slovak",
  "sq": "Albanian",
  "sr": "Serbian",
  "su": "Sundanese",
  "sv": "Swedish",
  "sw": "Swahili",
  "ta": "Tamil",
  "te": "Telugu",
  "th": "Thai",
  "tl": "Filipino",
  "tr": "Turkish",
  "uk": "Ukrainian",
  "ur": "Urdu",
  "vi": "Vietnamese",
  "zh-CN": "Chinese (Simplified)",
  "zh-TW": "Chinese (Mandarin/Taiwan)",
  "zh": "Chinese (Mandarin)"
}

class GoogleWebTTSFree:
    name = 'GoogleWebTTS(Free)'
    alias = 'Google Web TTS (Free)'
    need_api_key = False
    api_key_hint = ''
    default_api_host = 'https://translate.google.com'
    default_timeout = 60
    request_interval = 0
    languages = gtts_languages
    
    def __init__(self, params):
        params = params or {}
        self.params = params
        host = params.get('api_host', 'google.com')
        self.tld = host.split('google.')[-1] if 'google.' in host else 'com'
        lang = params.get('language', 'en')
        self.lang = lang if lang in self.languages else 'en'
        self.timeout = self.params.get('timeout', self.default_timeout)
        self.slow = (self.params.get('speed', 'normal') == 'slow')

    #开始进行tts转换，返回 (mime，音频二进制)
    def tts(self, text):
        tts = gtts.gTTS(text=text, tld=self.tld, lang=self.lang, slow=self.slow, 
            lang_check=False, timeout=self.timeout)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        return ('audio/mpeg', buf.getvalue())

#https://cloud.google.com/text-to-speech/docs/create-audio#text-to-speech-text-python
#https://cloud.google.com/text-to-speech/pricing
class GoogleTextToSpeech:
    name = 'GoogleTextToSpeech(GAE only)'
    alias = 'Google Text To Speech (GAE only)'
    need_api_key = False
    api_key_hint = ''
    default_api_host = ''
    default_timeout = 60
    request_interval = 0
    languages = gtts_languages
    
    def __init__(self, params):
        params = params or {}
        self.params = params
        lang = params.get('language', 'en')
        self.lang = lang if lang in self.languages else 'en'
        self.timeout = self.params.get('timeout', self.default_timeout)
        self.slow = (self.params.get('speed', 'normal') == 'slow')
        self.client = texttospeech.TextToSpeechClient()

    #开始进行tts转换，返回 (mime，音频二进制)
    #Limit is 5000 bytes per request
    #https://cloud.google.com/text-to-speech/quotas
    def tts(self, text):
        input_text = texttospeech.SynthesisInput(text=text)

        # Note: the voice can also be specified by name.
        # Names of voices can be retrieved with client.list_voices().
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Standard-C",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        response = client.synthesize_speech(
            request={"input": input_text, "voice": voice, "audio_config": audio_config}
        )
        
        return ('audio/mpeg', response.audio_content)