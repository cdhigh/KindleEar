#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#简单封装几个流行的AI服务接口，对外提供一个统一的接口
#Author: cdhigh <https://github.com/cdhigh>
# 使用示例：
#provider = SimpleAiProvider("openai", api_key="xxxxxx")
#response = provider.chat("你好，请讲一个笑话")
#response = provider.chat([{"role": "system", "content": "你是一个专业的物理学家。"},{"role": "user", "content": "黑洞是怎么形成的？"}])
#import requests
from urlopener import UrlOpener

#支持的AI服务商列表，models里面的第一项请设置为默认要使用的model
#rpm(requests per minute)是针对免费用户的，如果是付费用户，一般会高很多，可以自己修改
#大语言模型发展迅速，估计没多久这些数据会全部过时
#{'name': '', 'rpm': , 'context': },
_PROV_AI_LIST = {
    'Gemini': [
        {'name': 'gemini-1.5-flash', 'rpm': 15, 'context': 128000}, #其实支持100万
        {'name': 'gemini-1.5-flash-8b', 'rpm': 15, 'context': 128000}, 
        {'name': 'gemini-1.5-pro', 'rpm': 2, 'context': 128000},],
    'Openai': [
        {'name': 'gpt-4o-mini', 'rpm': 3, 'context': 128000},
        {'name': 'gpt-4o', 'rpm': 3, 'context': 128000},
        {'name': 'gpt-4-turbo', 'rpm': 3, 'context': 128000},
        {'name': 'gpt-3.5-turbo', 'rpm': 3, 'context': 16000},
        {'name': 'gpt-3.5-turbo-instruct', 'rpm': 3, 'context': 4000},],
    'Anthropic': [
        {'name': 'claude-2', 'rpm': 5, 'context': 100000},
        {'name': 'claude-3', 'rpm': 5, 'context': 200000},
        {'name': 'claude-2.1', 'rpm': 5, 'context': 100000},],
    'Grok': [
        {'name': 'grok-beta', 'rpm': 10, 'context': 128000},],
    'Mistral': [
        {'name': 'open-mistral-7b', 'rpm': 60, 'context': 32000},
        {'name': 'mistral-small-latest', 'rpm': 60, 'context': 32000},
        {'name': 'open-mixtral-8x7b', 'rpm': 60, 'context': 32000},
        {'name': 'open-mixtral-8x22b', 'rpm': 60, 'context': 64000},
        {'name': 'mistral-medium-latest', 'rpm': 60, 'context': 32000},
        {'name': 'mistral-large-latest', 'rpm': 60, 'context': 128000},
        {'name': 'pixtral-12b-2409', 'rpm': 60, 'context': 128000},],
    'Groq': [
        {'name': 'gemma2-9b-it', 'rpm': 30, 'context': 8000},
        {'name': 'gemma-7b-it', 'rpm': 30, 'context': 8000},
        {'name': 'llama-guard-3-8b', 'rpm': 30, 'context': 8000},
        {'name': 'llama3-70b-8192', 'rpm': 30, 'context': 8000},
        {'name': 'llama3-8b-8192', 'rpm': 30, 'context': 8000},
        {'name': 'mixtral-8x7b-32768', 'rpm': 30, 'context': 32000},],
    'Alibaba': [
        {'name': 'qwen-turbo', 'rpm': 60, 'context': 128000}, #其实支持100万
        {'name': 'qwen-plus', 'rpm': 60, 'context': 128000},
        {'name': 'qwen-long', 'rpm': 60, 'context': 128000},
        {'name': 'qwen-max', 'rpm': 60, 'context': 32000},],
}

class SimpleAiProvider:
    #name: AI提供商的名字
    def __init__(self, name, api_key, model=None, api_host=None):
        if name not in _PROV_AI_LIST:
            raise ValueError(f"Unsupported provider: {name}")
        self.name = name
        self.api_key = api_key
        
        index = 0
        for idx, item in enumerate(_PROV_AI_LIST[name]):
            if model == item['name']:
                index = idx
                break
        
        item = _PROV_AI_LIST[name][index]
        self._model = item['name']
        self._rpm = item['rpm']
        self._context = item['context']
        if self._rpm <= 0:
            self._rpm = 2
        if self._context < 4000:
            self._context = 4000
        self.api_host = api_host
        self.opener = UrlOpener()

    @property
    def model(self):
        return self._model
    @property
    def rpm(self):
        return self._rpm
    @property
    def request_interval(self):
        return (60 / self._rpm) if (self._rpm > 0) else 30
    @property
    def context_size(self):
        return self._context

    def __repr__(self):
        return f'{self.name}({self._model})'

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
        else:
            raise ValueError(f"Unsupported provider: {name}")

    #openai的chat接口
    def _openai_chat(self, message, defaultUrl='https://api.openai.com/v1/chat/completions'):
        url = self.api_host if self.api_host else defaultUrl
        headers = {'Authorization': f"Bearer {self.api_key}",
            'Content-Type': 'application/json'}
        payload = {
            "model": self._model,
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
            "model": self._model,
            "max_tokens_to_sample": 256,
        }
        response = self.opener.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["completion"]

    #gemini的chat接口
    def _gemini_chat(self, message):
        if self.api_host:
            url = f'{self.api_host}?key={self.api_key}'
        else:
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self.api_key}'
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
            "model": self._model,
            "max_tokens": 300
        }
        response = self.opener.post(url, headers=headers, params=params, json=payload)
        response.raise_for_status()
        return response.json()["result"]["content"]

if __name__ == '__main__':
    provider = SimpleAiProvider("gemini", api_key="xxx")
    response = provider.chat("你好，请讲一个笑话")
    print(response)
