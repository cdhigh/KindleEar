#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import os, traceback
from urllib.parse import urljoin
from urlopener import UrlOpener

class Base:
    name = None
    alias = None
    lang_codes = {}
    endpoint = None
    need_api_key = True
    default_api_host = ''
    api_key_hint = _('API Keys')
    api_key_pattern = r'^[^\s]+$'
    api_key_errors = ['401']
    separator = '\n\n'
    placeholder = ('{{{{id_{}}}}}', r'({{\s*)+id\s*_\s*{}\s*(\s*}})+')
    using_tip = None

    concurrency_limit = 0
    request_interval = 0.0
    request_attempt = 3
    request_timeout = 10.0
    max_error_count = 10

    def __init__(self, config=None):
        self.source_lang = None #语种显示的名字
        self.target_lang = None
        self.source_code = None #语种代码
        self.target_code = None
        self.proxy_uri = None
        self.search_paths = []

        self.merge_enabled = False

        self.set_config(config)

    @classmethod
    def load_lang_codes(cls, codes):
        if not ('source' in codes or 'target' in codes):
            codes = {'source': codes, 'target': codes}
        return codes

    @classmethod
    def get_source_code(cls, lang):
        source_codes = cls.lang_codes.get('source', {}).values()
        return lang if lang in source_codes else 'auto'

    @classmethod
    def get_target_code(cls, lang):
        target_codes = cls.lang_codes.get('target', {}).values()
        return lang if lang in target_codes else 'en'

    #设置源语种代码
    def set_source_code(self, code):
        for name, scode in self.lang_codes.get('source', {}).items():
            if scode == code:
                self.source_code = scode
                self.source_lang = name
                break
        else:
            self.source_code = 'auto'
            self.source_lang = ''

    def set_target_code(self, code):
        for name, tcode in self.lang_codes.get('target', {}).items():
            if tcode == code:
                self.target_code = tcode
                self.target_lang = name
                break
        else:
            self.target_code = 'en'
            self.target_lang = 'en'

    @classmethod
    def get_iso639_target_code(cls, lang):
        return lang_as_iso639_1(cls.get_target_code(lang))

    def set_config(self, config=None):
        self.config = config or {}
        self.api_keys = self.config.get('api_keys', [])[:]
        self.api_host = self.config.get('api_host', self.default_api_host)
        self.bad_api_keys = []
        self.api_key = self._get_api_key()

        concurrency_limit = self.config.get('concurrency_limit')
        if concurrency_limit is not None:
            self.concurrency_limit = int(concurrency_limit)
        request_interval = self.config.get('request_interval')
        if request_interval is not None:
            self.request_interval = request_interval
        request_attempt = self.config.get('request_attempt')
        if request_attempt is not None:
            self.request_attempt = int(request_attempt)
        request_timeout = self.config.get('request_timeout')
        if request_timeout is not None:
            self.request_timeout = request_timeout
        max_error_count = self.config.get('max_error_count')
        if max_error_count is not None:
            self.max_error_count = max_error_count

    @classmethod
    def api_key_error_message(cls):
        return _('A correct key format "{}" is required.') \
            .format(cls.api_key_hint)

    @classmethod
    def is_chatgpt(cls):
        return 'chatgpt' in cls.__name__.lower()

    @classmethod
    def is_custom(cls):
        return cls.__name__ == 'CustomTranslate'

    def change_api_key(self):
        """Change the API key if the previous one cannot be used."""
        if self.api_keys and self.api_key not in self.bad_api_keys:
            self.bad_api_keys.append(self.api_key)
            self.api_key = self._get_api_key()
            if self.api_key is not None:
                return True
        return False

    def need_change_api_key(self, error_message):
        if self.need_api_key and self.api_keys:
            for error in self.api_key_errors:
                if error in error_message:
                    return True
        return False

    def set_search_paths(self, paths):
        self.search_paths = paths

    def get_external_program(self, name, paths=[]):
        for path in paths + self.search_paths:
            if not path.endswith('%s%s' % (os.path.sep, name)):
                path = os.path.join(path, name)
            if os.path.isfile(path):
                return path
        return None

    def set_endpoint(self, endpoint):
        self.endpoint = endpoint

    def set_merge_enabled(self, enable):
        self.merge_enabled = enable

    def set_source_lang(self, source_lang):
        self.source_lang = source_lang or ''

    def set_target_lang(self, target_lang):
        self.target_lang = target_lang or ''

    def get_target_lang(self):
        return self.target_lang

    def set_proxy(self, proxy):
        if isinstance(proxy, list) and len(proxy) == 2:
            self.proxy_uri = '%s:%s' % tuple(proxy)
            if not self.proxy_uri.startswith('http'):
                self.proxy_uri = 'http://%s' % self.proxy_uri

    def set_concurrency_limit(self, limit):
        self.concurrency_limit = limit

    def set_request_attempt(self, limit):
        self.request_attempt = limit

    def set_request_interval(self, seconds):
        self.request_interval = seconds

    def set_request_timeout(self, seconds):
        self.request_timeout = seconds

    def _get_source_code(self):
        return self.source_code

    def _get_target_code(self):
        return self.target_code

    def _is_auto_lang(self):
        return self._get_source_code() in ('auto', '')

    def _get_api_key(self):
        if self.need_api_key and self.api_keys:
            return self.api_keys.pop(0).strip()
        return None

    def get_result(self, url, data=None, headers=None, method='GET',
                   stream=False, silence=False, callback=None):
        result = ''
        br = UrlOpener(headers=headers, timeout=self.request_timeout)
        resp = br.open(url, data=data, method=method, stream=stream)
        if resp.status_code == 200:
            text = []
            if stream:
                for line in resp.iter_content(chunk_size=None):
                    text.append(line if isinstance(line, str) else line.decode('utf-8'))
                text = ''.join(text)
            else:
                text = resp.text

            try:
                return callback(text) if callback else text
            except:
                raise Exception('Can not parse translation. Raw data: {text}')
            finally:
                resp.close()
        elif silence:
            return None
        else:
            raise Exception(f'get translation result failed: {UrlOpener.CodeMap(resp.status_code)}')

    def get_usage(self):
        return None

    def translate(self, text):
        raise NotImplementedError()
