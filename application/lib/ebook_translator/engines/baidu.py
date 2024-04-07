import re
import json
import random
import hashlib
from urllib.parse import urljoin
from .base import Base
from .languages import baidu

class BaiduTranslate(Base):
    name = 'Baidu'
    alias = 'Baidu'
    lang_codes = Base.load_lang_codes(baidu)
    default_api_host = 'https://fanyi-api.baidu.com'
    endpoint = '/api/trans/vip/translate'
    api_key_hint = 'appid|appkey'
    api_key_pattern = r'^[^\s:\|]+?[:\|][^\s:\|]+$'
    api_key_errors = ['54004']

    def translate(self, text):
        try:
            app_id, app_key = re.split(r'[:\|]', self.api_key)
        except Exception:
            raise Exception(self.api_key_error_message())

        salt = random.randint(32768, 65536)
        sign_str = app_id + text + str(salt) + app_key
        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'appid': app_id,
            'q': text,
            'from': self._get_source_code(),
            'to': self._get_target_code(),
            'salt': salt,
            'sign': sign
        }
        
        endpoint = urljoin(self.api_host or self.default_api_host, self.endpoint)
        return self.get_result(endpoint, data, headers, method='POST',
            callback=lambda r: json.loads(r)['trans_result'][0]['dst'])
