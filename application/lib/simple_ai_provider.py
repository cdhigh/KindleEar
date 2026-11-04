#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#简单封装几个流行的AI服务接口，对外提供一个统一的接口
#Author: cdhigh <https://github.com/cdhigh>
# 使用示例：
#provider = SimpleAiProvider("openai", apiKey="xxxxxx")
#response = provider.chat("你好，请讲一个笑话")
#response = provider.chat([{"role": "system", "content": "你是一个专业的物理学家。"},{"role": "user", "content": "黑洞是怎么形成的？"}])
#import requests
from urllib.parse import urljoin, urlsplit, urlunsplit
from urlopener import UrlOpener

#支持的AI服务商列表，models里面的第一项请设置为默认要使用的model
#rpm(requests per minute)与context(上下文分段预算)设置偏向保守，以降低超时和429错误，提高摘要成功率
#只收录纯文本生成与对话模型
#{'name': '', 'rpm': , 'context': },
AI_LIST = {
    'google': {'host': 'https://generativelanguage.googleapis.com', 'models': [
        {'name': 'gemini-3.8-flash', 'rpm': 15, 'context': 64000},
        {'name': 'gemini-3.5-flash-lite', 'rpm': 30, 'context': 64000},
        {'name': 'gemini-3.1-pro', 'rpm': 5, 'context': 64000},],},
    'openai': {'host': 'https://api.openai.com', 'models': [
        {'name': 'gpt-5.4-mini', 'rpm': 30, 'context': 64000},
        {'name': 'gpt-5.4', 'rpm': 20, 'context': 64000},
        {'name': 'gpt-5.5', 'rpm': 15, 'context': 64000},
        {'name': 'o3-mini', 'rpm': 15, 'context': 64000},],},
    'deepseek': {'host': 'https://api.deepseek.com', 'models': [
        {'name': 'deepseek-flash', 'rpm': 30, 'context': 64000},
        {'name': 'deepseek-v4-pro', 'rpm': 15, 'context': 64000},
        {'name': 'deepseek-v4', 'rpm': 15, 'context': 64000},],},
    'anthropic': {'host': 'https://api.anthropic.com', 'models': [
        {'name': 'claude-haiku-5-5', 'rpm': 30, 'context': 64000},
        {'name': 'claude-sonnet-5-5', 'rpm': 20, 'context': 64000},
        {'name': 'claude-opus-5-5', 'rpm': 10, 'context': 64000},],},
    'xai': {'host': 'https://api.x.ai', 'models': [
        {'name': 'grok-4.7', 'rpm': 20, 'context': 64000},
        {'name': 'grok-4.3', 'rpm': 30, 'context': 64000},
        {'name': 'grok-beta', 'rpm': 20, 'context': 64000},],},
    'mistral': {'host': 'https://api.mistral.ai', 'models': [
        {'name': 'mistral-small-latest', 'rpm': 30, 'context': 32000},
        {'name': 'mistral-large-latest', 'rpm': 15, 'context': 64000},
        {'name': 'codestral-latest', 'rpm': 20, 'context': 64000},
        {'name': 'ministral-8b-latest', 'rpm': 30, 'context': 32000},],},
    'groq': {'host': 'https://api.groq.com', 'models': [
        {'name': 'llama-3.3-70b-versatile', 'rpm': 30, 'context': 32000},
        {'name': 'llama-3.1-8b-instant', 'rpm': 30, 'context': 32000},
        {'name': 'deepseek-r1-distill-llama-70b', 'rpm': 20, 'context': 32000},
        {'name': 'mixtral-8x7b-32768', 'rpm': 30, 'context': 32000},],},
    'perplexity': {'host': 'https://api.perplexity.ai', 'models': [
        {'name': 'sonar', 'rpm': 20, 'context': 32000},
        {'name': 'sonar-pro', 'rpm': 15, 'context': 64000},
        {'name': 'sonar-reasoning', 'rpm': 15, 'context': 32000},],},
    'alibaba': {'host': 'https://dashscope.aliyuncs.com', 'models': [
        {'name': 'qwen3.5-flash', 'rpm': 30, 'context': 64000},
        {'name': 'qwen-plus', 'rpm': 25, 'context': 64000},
        {'name': 'qwen-turbo', 'rpm': 30, 'context': 64000},
        {'name': 'qwen-max', 'rpm': 15, 'context': 32000},],},
}

class SimpleAiProvider:
    #name: AI提供商的名字
    #apiHost: 支持自搭建的API转发服务器，传入以分号分割的地址列表字符串，则逐个使用
    #singleTurn: 一些API转发服务不支持多轮对话模式，设置此标识，当前仅支持 openai
    def __init__(self, name, apiKey, model=None, apiHost=None, singleTurn=False):
        name = name.lower()
        if name not in AI_LIST:
            raise ValueError(f"Unsupported provider: {name}")
        self.name = name
        self.apiKey = apiKey
        self.singleTurn = singleTurn
        self.apiHosts = (apiHost or AI_LIST[name]['host']).split(';')
        self.hostIdx = 0
        self.host = '' #如果提供多个api host，这个变量保存当前使用的host
        self._models = AI_LIST[name]['models']
        
        #如果传入的model不在列表中，默认使用第一个的参数
        item = next((m for m in self._models if m['name'] == model), self._models[0])
        #self.model = item['name']
        self.model = model or item['name']
        self.rpm = item['rpm']
        self.context_size = item['context']
        if self.rpm <= 0:
            self.rpm = 2
        if self.context_size < 1000:
            self.context_size = 1000
        
        self.opener = UrlOpener()

    @property
    def request_interval(self):
        return (60 / self.rpm) if (self.rpm >= 1) else 20

    def __repr__(self):
        return f'{self.name}/{self.model}'

    #返回支持的AI供应商列表，返回一个python字典
    def ai_list(self):
        return AI_LIST

    #返回需要使用的api host，自动轮换使用多host
    @property
    def apiHost(self):
        self.host = self.apiHosts[self.hostIdx]
        self.hostIdx += 1
        if self.hostIdx >= len(self.apiHosts):
            self.hostIdx = 0
        return self.host

    #智能解析并组装完整 API 请求 URL
    @classmethod
    def build_api_url(cls, host: str, default_path: str = 'v1/chat/completions', model: str = '') -> str:
        if not host:
            return ''
        url = host.strip()
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        if '{model}' in url and model:
            url = url.replace('{model}', model)

        parsed = urlsplit(url)
        path = parsed.path.rstrip('/')

        # 1. 已是完整 endpoint 或带 query 参数（如 Azure）
        if path.endswith(('chat/completions', '/completions', '/chat', ':generateContent')) or parsed.query:
            return url

        # 2. 常见以 /v1 结尾的 base_url，追加 /chat/completions
        if path.endswith(('/v1', '/v2', '/v3', '/v4')):
            new_path = f"{path}/chat/completions"
        elif not path:
            # 3. 纯域名，追加默认 path
            new_path = '/' + default_path.lstrip('/')
        else:
            # 4. 自定义子路径网关
            new_path = f"{path}/chat/completions" if default_path.endswith('chat/completions') else f"{path}/{default_path.lstrip('/')}"

        return urlunsplit((parsed.scheme, parsed.netloc, new_path, parsed.query, parsed.fragment))

    #外部调用此函数即可调用简单聊天功能
    #message: 如果是文本，则使用各项默认参数
    #传入 list/dict 可以定制 role 等参数
    #返回 respTxt，如果要获取当前使用的主机，可以使用 host 属性
    def chat(self, message):
        name = self.name
        if name in ("openai", "deepseek"):
            return self._openai_chat(message)
        elif name == "anthropic":
            return self._anthropic_chat(message)
        elif name == "google":
            return self._google_chat(message)
        elif name == "xai":
            return self._xai_chat(message)
        elif name == "mistral":
            return self._mistral_chat(message)
        elif name == 'groq':
            return self._groq_chat(message)
        elif name == 'perplexity':
            ret = self._perplexity_chat(message)
        elif name == "alibaba":
            return self._alibaba_chat(message)
        elif name == "atlascloud":
            return self._atlascloud_chat(message)
        elif name == "cheaperinference":
            return self._cheaperinference_chat(message)
        elif name == "api-route":
            return self._openai_chat(message)
        elif name == "opper":
            return self._opper_chat(message)
        else:
            raise ValueError(f"Unsupported provider: {name}")

    #返回当前服务提供商支持的models列表
    def models(self, prebuild=True):
        if self.name in ('openai', 'deepseek', 'xai', 'atlascloud', 'cheaperinference', 'api-route'):
            return self._openai_models()
        elif self.name == 'google':
            return self._google_models()
        else:
            return [item['name'] for item in self._models]

    #openai的chat接口
    def _openai_chat(self, message, path='v1/chat/completions'):
        url = self.build_api_url(self.apiHost, default_path=path, model=self.model)
        headers = {'Authorization': f'Bearer {self.apiKey}', 'api-key': self.apiKey, 'Content-Type': 'application/json'}
        if isinstance(message, str):
            msg = [{"role": "user", "content": message}]
        elif self.singleTurn and (len(message) > 1): #将多轮对话手动拼接为单一轮对话
            msgArr = ['Previous conversions:\n']
            roleMap = {'system': 'background', 'assistant': 'Your responsed'}
            msgArr.extend([f'{roleMap.get(e["role"], "I asked")}:\n{e["content"]}\n' for e in message[:-1]])
            msgArr.append(f'\nPlease continue this conversation based on the previous information:\n')
            msgArr.append("I ask:")
            msgArr.append(message[-1]['content'])
            msgArr.append("You Response:\n")
            msg = [{"role": "user", "content": '\n'.join(msgArr)}]
        else:
            msg = message
        payload = {"model": self.model, "messages": msg}
        resp = self.opener.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    #openai的models接口
    def _openai_models(self):
        url = urljoin(self.apiHost, 'v1/models')
        headers = {'Authorization': f'Bearer {self.apiKey}', 'api-key': self.apiKey, 'Content-Type': 'application/json'}
        resp = self.opener.get(url, headers=headers)
        resp.raise_for_status()
        return [item['id'] for item in resp.json()['data']]

    #anthropic的chat接口
    def _anthropic_chat(self, message, path='v1/complete'):
        url = self.build_api_url(self.apiHost, default_path=path, model=self.model)
        headers = {'Accept': 'application/json', 'Anthropic-Version': '2023-06-01',
            'Content-Type': 'application/json', 'x-api-key': self.apiKey}

        if isinstance(message, list): #将openai的payload格式转换为anthropic的格式
            msg = []
            for item in message:
                role = 'Human' if (item.get('role') != 'assistant') else 'Assistant'
                content = item.get('content', '')
                msg.append(f"\n\n{role}: {content}")
            prompt = ''.join(msg) + "\n\nAssistant:"
            payload = {"prompt": prompt, "model": self.model, "max_tokens_to_sample": 256}
        elif isinstance(message, dict):
            payload = message
        else:
            prompt = f"\n\nHuman: {message}\n\nAssistant:"
            payload = {"prompt": prompt, "model": self.model, "max_tokens_to_sample": 256}

        resp = self.opener.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["completion"]

    #google的chat接口
    def _google_chat(self, message):
        url = urljoin(self.apiHost, f'v1beta/models/{self.model}:generateContent?key={self.apiKey}')
        if isinstance(message, list): #将openai的payload格式转换为gemini的格式
            msg = []
            for item in message:
                role = 'user' if (item.get('role') != 'assistant') else 'model'
                content = item.get('content', '')
                msg.append({'role': role, 'parts': [{'text': content}]})
            payload = {'contents': msg}
        elif isinstance(message, dict):
            payload = message
        else:
            payload = {'contents': [{'role': 'user', 'parts': [{'text': message}]}]}
        resp = self.opener.post(url, json=payload)
        resp.raise_for_status()
        contents = resp.json()["candidates"][0]["content"]
        return contents['parts'][0]['text']

    #google的models接口
    def _google_models(self):
        url = urljoin(self.apiHost, f'v1beta/models?key={self.apiKey}&pageSize=100')
        headers = {'Content-Type': 'application/json'}
        resp = self.opener.get(url, headers=headers)
        resp.raise_for_status()
        _trim = lambda x: x[7:] if x.startswith('models/') else x
        return [_trim(item['name']) for item in resp.json()['models']]

    #xai的chat接口
    def _xai_chat(self, message):
        return self._openai_chat(message, path='v1/chat/completions')

    #mistral的chat接口
    def _mistral_chat(self, message):
        return self._openai_chat(message, path='v1/chat/completions')
        
    #groq的chat接口
    def _groq_chat(self, message):
        return self._openai_chat(message, path='openai/v1/chat/completions')
    
    #perplexity的chat接口
    def _perplexity_chat(self, message):
        return self._openai_chat(message, path='chat/completions')

    #通义千问
    def _alibaba_chat(self, message):
        return self._openai_chat(message, path='compatible-mode/v1/chat/completions')

    #Atlas Cloud (OpenAI兼容网关)
    def _atlascloud_chat(self, message):
        return self._openai_chat(message, path='v1/chat/completions')

    #Cheaper Inference (OpenAI兼容网关)
    def _cheaperinference_chat(self, message):
        return self._openai_chat(message, path='v1/chat/completions')

    #Opper (OpenAI兼容网关)
    def _opper_chat(self, message):
        return self._openai_chat(message, path='v3/compat/chat/completions')

if __name__ == '__main__':
    client = SimpleAiProvider("gemini", apiKey="xxx")
    resp = client.chat("你好，请讲一个笑话")
    print(resp)
