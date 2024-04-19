#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from .google import GoogleWebTTSFree, GoogleTextToSpeech
builtin_tts_engines = {
    GoogleWebTTSFree.name: GoogleWebTTSFree,
    GoogleTextToSpeech.name: GoogleTextToSpeech,
}
