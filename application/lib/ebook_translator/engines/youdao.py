import re
import json
import time
import uuid
import hashlib
from urllib.parse import urljoin
from .base import Base
from .languages import youdao

class YoudaoTranslate(Base):
    name = 'Youdao'
    alias = 'Youdao'
    lang_codes = Base.load_lang_codes(youdao)
    default_api_host = 'https://openapi.youdao.com'
    endpoint = '/api'
    api_key_hint = 'appid|appsecret'
    api_key_pattern = r'^[^\s:\|]+?[:\|][^\s:\|]+$'
    api_key_errors = ['401']

    def _encrypt(self, signStr):
        hash_algorithm = hashlib.sha256()
        hash_algorithm.update(signStr.encode('utf-8'))
        return hash_algorithm.hexdigest()

    def _truncate(self, text):
        if text is None:
            return None
        size = len(text)
        return text if size <= 20 else \
            text[0:10] + str(size) + text[size - 10:size]

    def translate(self, text):
        try:
            app_key, app_secret = re.split(r'[:\|]', self.api_key)
        except Exception:
            raise Exception(self.api_key_error_message())

        curtime = str(int(time.time()))
        salt = str(uuid.uuid1())
        sign_str = app_key + self._truncate(text) + salt + curtime + app_secret
        sign = self._encrypt(sign_str)

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        data = {
            'from': self._get_source_code(),
            'to': self._get_target_code(),
            'signType': 'v3',
            'curtime': curtime,
            'appKey': app_key,
            'q': text,
            'salt': salt,
            'sign': sign,
            'vocabId': False,
        }

        endpoint = urljoin(self.api_host or self.default_api_host, self.endpoint)
        return self.get_result(endpoint, data, headers, method='POST',
            callback=lambda r: json.loads(r)['translation'][0])
