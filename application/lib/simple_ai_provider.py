#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#简单封装几个流行的AI服务接口，对外提供一个统一的接口
#Author: cdhigh <https://github.com/cdhigh>
# 使用示例：
#provider = SimpleAiProvider("openai", api_key="xxxxxx")
#response = provider.chat("你好，请告诉我天气预报")
#response = provider.chat([{"role": "system", "content": "你是一个专业的物理学家。"},{"role": "user", "content": "黑洞是怎么形成的？"}])
#import requests
from urlopener import UrlOpener

#支持的AI服务商列表，models里面的第一项请设置为默认要实现的model
#这里的 context_size 其实应该根据model不同而设置，为简单起见，就使用一个最低值
_PROV_AI_LIST = {
    'Gemini': {
        'models': ['gemini-1.5-flash', 'gemini-1.5-flash-8b', 'gemini-1.5-pro'], 
        'request_interval': 4,
        'context_size': 8000},
    'Openai': {
        'models': ['GPT-4o mini', 'GPT-4o', 'GPT-4 Turbo', 'gpt-3.5-turbo', 'GPT-3.5 Turbo Instruct'],
        'request_interval': 10,
        'context_size': 4000},
    'Anthropic': {
        'models': ['claude-2', 'claude-3', 'claude-1'],
        'request_interval': 6,
        'context_size': 100000},
    'Grok': {
        'models': ['grok-beta'], 
        'request_interval': 6,
        'context_size': 4000},
    'Mistral': {
        'models': ['open-mistral-7b', 'mistral-small-latest', 'open-mixtral-8x7b', 'open-mixtral-8x22b', 'mistral-small-2402',
            'mistral-small-2409', 'mistral-medium', 'mistral-large-2402', 'mistral-large-2407',
            'mistral-large-2411'],
        'request_interval': 1,
        'context_size': 32000},
    'Groq': {
        'models': ['gemma2-9b-it', 'gemma-7b-it', 'llama-guard-3-8b', 'llama3-70b-8192', 'llama3-8b-8192',
            'mixtral-8x7b-32768'], 
        'request_interval': 2,
        'context_size': 8000},
    'Alibaba': {
        'models': ['qwen-turbo', 'qwen-plus', 'qwen-long'],
        'request_interval': 1,
        'context_size': 130000},
    # 'Baidu': {
    #     'models': ['ernie-bot'],
    #     'request_interval': 6,
    #     'context_size': 4000},
}

class SimpleAiProvider:
    #name: AI提供商的名字
    def __init__(self, name, api_key, model=None, api_host=None):
        self.name = name
        self.api_key = api_key
        self.model = model if model in _PROV_AI_LIST.get(name, {}).get('models', []) else ''
        self.api_host = api_host
        self.opener = UrlOpener()

    def __repr__(self):
        return f'{self.name}({self.model})'

    #返回支持的AI供应商列表，返回一个python字典
    def ai_list(self):
        return _PROV_AI_LIST

    #外部调用此函数即可调用简单聊天功能
    #message: 如果是文本，则使用各项默认参数
    #传入 list/dict 可以定制 role 等参数
    def chat(self, message):
        name = self.name
        if name == "Openai":
            return self._openai_chat(message)
        elif name == "Anthropic":
            return self._anthropic_chat(message)
        elif name == "Gemini":
            return self._gemini_chat(message)
        elif name == "Grok":
            return self._grok_chat(message)
        elif name == "Mistral":
            return self._mistral_chat(message)
        elif name == 'Groq':
            return self._groq_chat(message)
        elif name == "Alibaba":
            return self._alibaba_chat(message)
        # elif name == "Baidu":
        #     return self._baidu_chat(message)
        else:
            raise ValueError(f"Unsupported provider: {name}")

    #openai的chat接口
    def _openai_chat(self, message, defaultUrl='https://api.openai.com/v1/chat/completions'):
        url = self.api_host if self.api_host else defaultUrl
        headers = {'Authorization': f"Bearer {self.api_key}",
            'Content-Type': 'application/json'}
        payload = {
            "model": self.model or _PROV_AI_LIST['openai']['models'][0],
            "messages": [{"role": "user", "content": message}] if isinstance(message, str) else message
        }
        response = self.opener.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    #anthropic的chat接口
    def _anthropic_chat(self, message):
        url = self.api_host if self.api_host else 'https://api.anthropic.com/v1/complete'
        headers = {'Accept': 'application/json',
            'Anthropic-Version': '2023-06-01',
            'Content-Type': 'application/json',
            'x-api-key': self.api_key}
        payload = {
            "prompt": f"\n\nHuman: {message}\n\nAssistant:",
            "model": self.model or _PROV_AI_LIST['anthropic']['models'][0],
            "max_tokens_to_sample": 256,
        }
        response = self.opener.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["completion"]

    #gemini的chat接口
    def _gemini_chat(self, message):
        model = self.model or _PROV_AI_LIST['gemini']['models'][0]
        if self.api_host:
            url = f'{self.api_host}?key={self.api_key}'
        else:
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}'
        payload = {'contents': [{'parts': [{'text': message}]}]}
        response = self.opener.post(url, json=payload)
        response.raise_for_status()
        contents = response.json()["candidates"][0]["content"]
        return contents['parts'][0]['text']

    #grok的chat接口
    def _grok_chat(self, message):
        #直接使用openai兼容接口
        return self._openai_chat(message, defaultUrl='https://api.x.ai/v1/chat/completions')

    #mistral的chat接口
    def _mistral_chat(self, message):
        #直接使用openai兼容接口
        return self._openai_chat(message, defaultUrl='https://api.mistral.ai/v1/chat/completions')

    #groq的chat接口
    def _groq_chat(self, message):
        #直接使用openai兼容接口
        return self._openai_chat(message, defaultUrl='https://api.groq.com/openai/v1/chat/completions')

    #通义千问
    def _alibaba_chat(self, message):
        #直接使用openai兼容接口
        return self._openai_chat(message, defaultUrl='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
        
    def _baidu_chat(self, message):
        url = self.api_host if self.api_host else 'https://aip.baidubce.com/rpc/2.0/ai_custom/v1/ernie-bot'
        headers = {"Content-Type": "application/json"}
        params = {"access_token": self.api_key}
        payload = {
            "messages": [{"role": "user", "content": message}] if isinstance(message, str) else message,
            "model": self.model or _PROV_AI_LIST['baidu']['models'][0],
            "max_tokens": 300
        }
        response = self.opener.post(url, headers=headers, params=params, json=payload)
        response.raise_for_status()
        return response.json()["result"]["content"]

if __name__ == '__main__':
    provider = SimpleAiProvider("gemini", api_key="xxx")
    response = provider.chat("你好，请告诉我天气预报")
    print(response)
