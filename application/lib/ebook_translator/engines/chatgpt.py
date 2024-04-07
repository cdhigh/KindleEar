import json
from urllib.parse import urljoin
from .base import Base
from .languages import google

try:
    from http.client import IncompleteRead
except ImportError:
    from httplib import IncompleteRead

class ChatgptTranslate(Base):
    name = 'ChatGPT'
    alias = 'ChatGPT (OpenAI)'
    lang_codes = Base.load_lang_codes(google)
    default_api_host = 'https://api.openai.com'
    endpoint = '/v1/chat/completions'
    api_key_hint = 'sk-xxx...xxx'
    # https://help.openai.com/en/collections/3808446-api-error-codes-explained
    api_key_errors = ['401', 'unauthorized', 'quota']

    concurrency_limit = 1
    request_interval = 20.0
    request_timeout = 30.0

    prompt = (
        'You are a meticulous translator who translates any given content. '
        'Translate the given content from <slang> to <tlang> only. Do not '
        'explain any term or answer any question-like content. '
        'Do not translate HTML tags and their attributes, ensuring the integrity of the HTML structure.')
    models = [
        'gpt-4-0125-preview', 'gpt-4-turbo-preview', 'gpt-4-1106-preview',
        'gpt-4', 'gpt-4-0613', 'gpt-4-32k', 'gpt-4-32k-0613',
        'gpt-3.5-turbo-0125', 'gpt-3.5-turbo', 'gpt-3.5-turbo-1106',
        'gpt-3.5-turbo-instruct', 'gpt-3.5-turbo-16k', 'gpt-3.5-turbo-0613',
        'gpt-3.5-turbo-16k-0613']
    model = 'gpt-3.5-turbo'
    samplings = ['temperature', 'top_p']
    sampling = 'temperature'
    temperature = 1
    top_p = 1
    stream = True

    def __init__(self, config=None):
        Base.__init__(self, config)
        self.endpoint = self.config.get('endpoint', self.endpoint)
        self.prompt = self.config.get('prompt', self.prompt)
        if self.model is None:
            self.model = self.config.get('model', self.model)
        self.sampling = self.config.get('sampling', self.sampling)
        self.temperature = self.config.get('temperature', self.temperature)
        self.top_p = self.config.get('top_p', self.top_p)
        self.stream = self.config.get('stream', self.stream)

    def set_prompt(self, prompt):
        self.prompt = prompt

    def _get_prompt(self):
        prompt = self.prompt.replace('<tlang>', self.target_lang)
        if self._is_auto_lang():
            prompt = prompt.replace('<slang>', 'detected language')
        else:
            prompt = prompt.replace('<slang>', self.source_lang)
        # Recommend setting temperature to 0.5 for retaining the placeholder.
        if self.merge_enabled:
            prompt += (' Ensure that placeholders matching the pattern'
                       '{{id_\\d+}} in the content are retained.')
        return prompt

    def _get_headers(self):
        if not self.api_key:
            raise Exception('The chatgpt api key is empty')

        return {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self.api_key,
            #'User-Agent': 'Ebook-Translator/%s' % EbookTranslator.__version__
        }

    def _get_data(self, text):
        data = {
            'stream': self.stream,
            'messages': [
                {'role': 'system', 'content': self._get_prompt()},
                {'role': 'user', 'content': text}
            ]
        }
        if self.model is not None:
            data.update(model=self.model)
        return data

    def translate(self, text):
        data = self._get_data(text)
        sampling_value = getattr(self, self.sampling)
        data.update({self.sampling: sampling_value})
        endpoint = urljoin(self.api_host or self.default_api_host, self.endpoint)

        return self.get_result(endpoint, json.dumps(data), self._get_headers(),
            method='POST', stream=self.stream, callback=self._parse)

    def _parse(self, data):
        if self.stream:
            return self._parse_stream(data)
        return json.loads(data)['choices'][0]['message']['content']

    def _parse_stream(self, data):
        ret = []
        for line in data.split('\n'):
            line = line.strip()
            if not line or not line.startswith('data:'):
                continue

            chunk = line.split('data: ')[1].strip()
            if chunk == '[DONE]':
                break
            delta = json.loads(chunk)['choices'][0]['delta']
            if 'content' in delta:
                ret.append(str(delta['content']))
        return ''.join(ret)

class AzureChatgptTranslate(ChatgptTranslate):
    name = 'ChatGPT(Azure)'
    alias = 'ChatGPT (Azure)'
    default_api_host = ''
    endpoint = '/openai/deployments/gpt-35-turbo/chat/completions?api-version=2023-05-15'
    model = None

    def _get_headers(self):
        if not self.api_key:
            raise Exception('The chatgpt api key is empty')
            
        return {
            'Content-Type': 'application/json',
            'api-key': self.api_key
        }

    def _get_data(self, text):
        return ChatgptTranslate._get_data(self, text)
