from .google import (
    GoogleFreeTranslate, GoogleBasicTranslate, GoogleBasicTranslateADC,
    GoogleAdvancedTranslate, GeminiPro)
from .chatgpt import ChatgptTranslate, AzureChatgptTranslate
from .deepl import DeeplTranslate, DeeplProTranslate, DeeplFreeTranslate
from .youdao import YoudaoTranslate
from .baidu import BaiduTranslate
from .microsoft import MicrosoftEdgeTranslate

builtin_translate_engines = (GoogleFreeTranslate, ChatgptTranslate, AzureChatgptTranslate,
    GeminiPro, DeeplTranslate, DeeplProTranslate, DeeplFreeTranslate,
    MicrosoftEdgeTranslate, YoudaoTranslate, BaiduTranslate)
