import re
import os
import sys
import time
import json
import os.path
import traceback
from urllib.parse import urljoin
from .base import Base
from .languages import google, gemini

class GoogleFreeTranslate(Base):
    name = 'Google(Free)'
    alias = 'Google (Free)'
    lang_codes = Base.load_lang_codes(google)
    default_api_host = 'https://translate.googleapis.com'
    endpoint = '/translate_a/single'
    need_api_key = False

    def translate(self, text):
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'DeepLBrowserExtension/1.3.0 Mozilla/5.0 (Macintosh;'
            ' Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'
            ' Chrome/111.0.0.0 Safari/537.36',
        }

        data = {
            'client': 'gtx',
            'sl': self._get_source_code(),
            'tl': self._get_target_code(),
            'dt': 't',
            'dj': 1,
            'q': text,
        }

        # The POST method is unstable, despite its ability to send more text.
        # However, it can be used occasionally with an unacceptable length.
        method = 'GET' if len(text) <= 1800 else 'POST'
        endpoint = urljoin(self.default_api_host, self.endpoint)
        return self.get_result(endpoint, data, headers, method=method, callback=self._parse)

    def _parse(self, data):
        # return ''.join(i[0] for i in json.loads(data)[0])
        return ''.join(i['trans'] for i in json.loads(data)['sentences'])


class GoogleTranslate:
    api_key_errors = ['429']
    api_key_cache = []
    gcloud = None
    project_id = None
    using_tip = _(
        'This plugin uses Application Default Credentials (ADC) in your local '
        'environment to access your Google Translate service. To set up the '
        'ADC, follow these steps:\n'
        '1. Install the gcloud CLI by checking out its instructions {}.\n'
        '2. Run the command: gcloud auth application-default login.\n'
        '3. Sign in to your Google account and grant needed privileges.') \
        .format('<sup><a href="https://cloud.google.com/sdk/docs/install">[^]'
                '</a></sup>').replace('\n', '<br />')

    def _run_command(self, command, silence=False):
        message = _('Cannot run the command "{}".')
        try:
            startupinfo = None
            # Prevent the popping console window on Windows.
            if sys.platform == 'win32':
                from subprocess import STARTUPINFO, STARTF_USESHOWWINDOW
                startupinfo = STARTUPINFO()
                startupinfo.dwFlags |= STARTF_USESHOWWINDOW
            process = Popen(
                command, stdout=PIPE, stderr=PIPE, universal_newlines=True,
                startupinfo=startupinfo)
        except Exception:
            if silence:
                return None
            raise Exception(
                message.format(command, '\n\n%s' % traceback.format_exc()))
        if process.wait() != 0:
            if silence:
                return None
            raise Exception(
                message.format(command, '\n\n%s' % process.stderr.read()))
        return process.stdout.read().strip()

    def _get_gcloud_command(self):
        if self.gcloud is not None:
            return self.gcloud
        if sys.platform == 'win32':
            name = 'gcloud.cmd'
            which = 'where'
            base = r'google-cloud-sdk\bin\%s' % name
            paths = [
                r'"%s\Google\Cloud SDK\%s"'
                % (os.environ.get('programfiles(x86)'), base),
                r'"%s\AppData\Local\Google\Cloud SDK\%s"'
                % (os.environ.get('userprofile'), base)]
        else:
            name = 'gcloud'
            which = 'which'
            paths = ['/usr/local/bin/%s' % name]
        gcloud = self.get_external_program(name, paths)
        if gcloud is None:
            gcloud = self._run_command([which, name], silence=True)
            if gcloud is not None:
                gcloud = gcloud.split('\n')[0]
        if gcloud is None:
            raise Exception(_('Cannot find the command "{}".').format(name))
        self.gcloud = gcloud
        return gcloud

    def _get_project_id(self):
        if self.project_id is not None:
            return self.project_id
        self.project_id = self._run_command(
            [self._get_gcloud_command(), 'config', 'get', 'project'])
        return self.project_id

    def _get_credential(self):
        """The default lifetime of the API key is 3600 seconds. Once an
        available key is generated, it will be cached until it expired.
        """
        timestamp, old_api_key = self.api_key_cache or (None, None)
        if old_api_key is not None and time.time() - timestamp < 3600:
            return old_api_key
        # Temporarily add existing proxies.
        self.proxy_uri and os.environ.update(
            http_proxy=self.proxy_uri, https_proxy=self.proxy_uri)
        new_api_key = self._run_command([
            self._get_gcloud_command(), 'auth', 'application-default',
            'print-access-token'])
        # Cleanse the proxies after use.
        for proxy in ('http_proxy', 'https_proxy'):
            if proxy in os.environ:
                del os.environ[proxy]
        self.api_key_cache[:] = [time.time(), new_api_key]
        return new_api_key


class GoogleBasicTranslateADC(GoogleTranslate, Base):
    name = 'Google(Basic)ADC'
    alias = 'Google (Basic) ADC'
    lang_codes = Base.load_lang_codes(google)
    default_api_host = 'https://translation.googleapis.com'
    endpoint = '/language/translate/v2'
    api_key_hint = 'API key'
    need_api_key = False

    def get_headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self._get_credential(),
            'x-goog-user-project': self._get_project_id(),
        }

    def get_data(self, data):
        return json.dumps(data)

    def translate(self, text):
        data = {
            'format': 'html',
            'model': 'nmt',
            'target': self._get_target_code(),
            'q': text
        }

        if not self._is_auto_lang():
            data.update(source=self._get_source_code())
        endpoint = urljoin(self.api_host or self.default_api_host, self.endpoint)
        return self.get_result(endpoint, self.get_data(data), self.get_headers(),
            method='POST', callback=self._parse)

    def _parse(self, data):
        translations = json.loads(data)['data']['translations']
        return ''.join(i['translatedText'] for i in translations)


class GoogleBasicTranslate(GoogleBasicTranslateADC):
    name = 'Google(Basic)'
    alias = 'Google (Basic)'
    need_api_key = True
    using_tip = None

    def get_headers(self):
        return {'Content-Type': 'application/x-www-form-urlencoded'}

    def get_data(self, data):
        data.update(key=self.api_key)
        return data


class GoogleAdvancedTranslate(GoogleTranslate, Base):
    name = 'Google(Advanced)'
    alias = 'Google (Advanced) ADC'
    lang_codes = Base.load_lang_codes(google)
    default_api_host = 'https://translation.googleapis.com'
    endpoint = '/v3/projects/{}'
    api_key_hint = 'PROJECT_ID'
    need_api_key = False

    def translate(self, text):
        project_id = self._get_project_id()
        endpoint = self.endpoint.format('%s:translateText' % project_id)
        endpoint = urljoin(self.api_host or self.default_api_host, endpoint)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self._get_credential(),
            'x-goog-user-project': project_id,
        }

        data = {
            'targetLanguageCode': self._get_target_code(),
            'contents': [text],
            'mimeType': 'text/plain',
        }

        if not self._is_auto_lang():
            data.update(sourceLanguageCode=self._get_source_code())

        return self.get_result(
            endpoint, json.dumps(data), headers, method='POST',
            callback=self._parse)

    def _parse(self, data):
        translations = json.loads(data)['translations']
        return ''.join(i['translatedText'] for i in translations)


class GeminiPro(Base):
    name = 'GeminiPro'
    alias = 'Gemini Pro'
    lang_codes = Base.load_lang_codes(gemini)
    default_api_host = 'https://generativelanguage.googleapis.com'
    endpoint = '/v1beta/models/gemini-pro:{}?key={}'
    need_api_key = True

    concurrency_limit = 1
    request_interval = 1

    prompt = (
        'You are a meticulous translator who translates any given content from'
        ' <slang> to <tlang> only. Do not explain any term, and do not answer'
        ' any question. '
        ' Do not translate HTML tags and their attributes, ensuring the integrity of the HTML structure.')
    temperature = 0.9
    top_k = 1
    top_p = 1
    stream = True

    def __init__(self, config=None):
        Base.__init__(self, config)
        self.prompt = self.config.get('prompt', self.prompt)
        self.temperature = self.config.get('temperature', self.temperature)
        self.top_k = self.config.get('top_k', self.top_k)
        self.top_p = self.config.get('top_p', self.top_p)
        self.stream = self.config.get('stream', self.stream)

    def _endpoint(self):
        method = 'streamGenerateContent' if self.stream else 'generateContent'
        endpoint = self.endpoint.format(method, self.api_key)
        return urljoin(self.api_host or self.default_api_host, self.endpoint)

    def _prompt(self, text):
        prompt = self.prompt.replace('<tlang>', self.target_lang)
        if self._is_auto_lang():
            prompt = prompt.replace('<slang>', 'detected language')
        else:
            prompt = prompt.replace('<slang>', self.source_lang)
        # Recommend setting temperature to 0.5 for retaining the placeholder.
        if self.merge_enabled:
            prompt += (' Ensure that placeholders matching the pattern'
                '{{id_\\d+}} in the content are retained.')
        return prompt + ' Start translating: ' + text

    def _headers(self):
        return {
            'Content-Type': 'application/json'
        }

    def _data(self, text):
        return {
            "contents": [
                {"role": "user", "parts": [{"text": self._prompt(text)}]},
            ],
            "generationConfig": {
                # "stopSequences": ["Test"],
                # "maxOutputTokens": 2048,
                "temperature": self.temperature,
                "topP": self.top_p,
                "topK": self.top_k,
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                },
            ],
        }

    def translate(self, text):
        return self.get_result(
            self._endpoint(), json.dumps(self._data(text)), self._headers(),
            method='POST', callback=self._parse)

    def _parse(self, data):
        if self.stream:
            parts = []
            for item in json.loads(data):
                for part in item['candidates'][0]['content']['parts']:
                    parts.append(part)
        else:
            parts = json.loads(data)['candidates'][0]['content']['parts']
        return ''.join([part['text'] for part in parts])
