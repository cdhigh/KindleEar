# -*- coding: utf-8 -*-
#https://github.com/Reverseblade/ssml-builder

import re


class Speech:

    VALID_INTERPRET_AS = ('characters', 'spell-out', 'cardinal', 'number',
                          'ordinal', 'digits', 'fraction', 'unit', 'date',
                          'time', 'telephone', 'address', 'interjection', 'expletive')

    VALID_PROSODY_ATTRIBUTES = {
        'rate': ('x-slow', 'slow', 'medium', 'fast', 'x-fast'),
        'pitch': ('x-low', 'low', 'medium', 'high', 'x-high'),
        'volume': ('silent', 'x-soft', 'soft', 'medium', 'loud', 'x-loud')
    }

    VALID_VOICE_NAMES = ('Ivy', 'Joanna', 'Joey', 'Justin', 'Kendra', 'Kimberly',
                        'Matthew', 'Salli', 'Nicole', 'Russell', 'Amy', 'Brian', 'Emma',
                        'Aditi', 'Raveena', 'Hans', 'Marlene', 'Vicki', 'Conchita', 'Enrique',
                        'Carla', 'Giorgio', 'Mizuki', 'Takumi', 'Celine', 'Lea', 'Mathieu')

    VALID_EMPHASIS_LEVELS = ('strong', 'moderate', 'reduced')

    def __init__(self):
        self.speech = ""

    def speak(self):
        """
        <speak>
        :return:
        """
        return '<speak>{}</speak>'.format(self.speech)

    def add_text(self, value):
        """
        add text
        :return:
        """
        self.speech += value
        return self

    def say_as(self, value, interpret_as, is_nested=False):
        """
        <say_as>
        :param value:
        :param interpret_as:
        :param is_nested:
        :return:
        """

        if interpret_as not in self.VALID_INTERPRET_AS:
            raise ValueError('The interpret-as provided to say_as is not valid')

        ssml = '<say-as interpret-as="{interpret_as}">' \
               '{value}</say-as>'.format(interpret_as=interpret_as, value=value)

        if is_nested:
            return ssml

        self.speech += ssml
        return self

    def prosody(self, value, rate='medium', pitch='medium', volume='medium', is_nested=False):
        """
        <prosody>
        :param value:
        :param rate:
        :param pitch:
        :param volume:
        :param is_nested:
        :return:
        """

        if rate not in self.VALID_PROSODY_ATTRIBUTES['rate']:
            if re.match(r'^\d+%$', rate) is None:
                raise ValueError('The rate provided to prosody is not valid')

        if pitch not in self.VALID_PROSODY_ATTRIBUTES['pitch']:
            if re.match(r'^(\+|\-)+\d+(\.\d+)*%$', pitch) is None:
                raise ValueError('The pitch provided to prosody is not valid')

        if volume not in self.VALID_PROSODY_ATTRIBUTES['volume']:
            raise ValueError('The volume provided to prosody is not valid')

        ssml = '<prosody rate="{rate}" pitch="{pitch}" volume="{volume}">' \
               '{value}</prosody>'.format(rate=rate, pitch=pitch, volume=volume, value=value)

        if is_nested:
            return ssml

        self.speech += ssml
        return self

    def sub(self, value, alias, is_nested=False):
        """
        <sub>
        :param value:
        :param alias:
        :param is_nested:
        :return:
        """

        ssml = '<sub alias="{}">{}</sub>'.format(alias, value)

        if is_nested:
            return ssml

        self.speech += ssml
        return self

    def lang(self, value, lang, is_nested=False):
        """
        <lang>
        :param value:
        :param lang:
        :param is_nested:
        :return:
        """

        ssml = '<lang xml:lang="{}">{}</lang>'.format(lang, value)

        if is_nested:
            return ssml

        self.speech += ssml
        return self

    def voice(self, value, name, is_nested=False):
        """
        <voice>
        :param value:
        :param name:
        :return:
        """

        #if name not in self.VALID_VOICE_NAMES:
        #    raise ValueError('The name provided to voice is not valid')

        ssml = '<voice name="{}">{}</voice>'.format(name, value)

        if is_nested:
            return ssml

        self.speech += '<voice name="{}">{}</voice>'.format(name, value)
        return self

    def pause(self, time, is_nested=False):
        """
        <break>
        :param time:
        :param is_nested:
        :return:
        """

        ssml = '<break time="{}"/>'.format(time)

        if is_nested:
            return ssml

        self.speech += ssml
        return self

    def whisper(self, value, is_nested=False):
        """
        :param value:
        :param is_nested:
        :return:
        """

        ssml = '<amazon:effect name="whispered">{}</amazon:effect>'.format(value)

        if is_nested:
            return ssml

        self.speech += ssml
        return self

    def audio(self, src, is_nested=False):
        """
        :param src:
        :param is_nested:
        :return:
        """

        ssml = '<audio src="{}" />'.format(src)

        if is_nested:
            return ssml

        self.speech += ssml
        return self

    def emphasis(self, value, level, is_nested=False):

        if level not in self.VALID_EMPHASIS_LEVELS:
            raise ValueError('The level provided to emphasis is not valid')

        ssml = '<emphasis level="strong">{}</emphasis>'.format(value)

        if is_nested:
            return ssml

        self.speech += ssml
        return self

    def p(self, value,is_nested=False):
        """
        :param value:
        :param is_nested:
        :return:
        """
        ssml = '<p>{}</p>'.format(value)

        if is_nested:
            return ssml

        self.speech += ssml
        return self

    def escape(self):
        """
        escapes any special characters that will cause SSML to be invalid
        :return:
        """
        pass
