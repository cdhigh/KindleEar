#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from .tts_base import TTSBase
from .azure import AzureTTS, EdgeTTSFree
from .google import GoogleWebTTSFree, GoogleTextToSpeech
builtin_tts_engines = {
    GoogleWebTTSFree.name: GoogleWebTTSFree,
    GoogleTextToSpeech.name: GoogleTextToSpeech,
    EdgeTTSFree.name: EdgeTTSFree,
    AzureTTS.name: AzureTTS,
}
