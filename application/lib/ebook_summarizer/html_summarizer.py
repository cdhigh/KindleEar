#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#用AI对文章进行摘要
#Author: cdhigh <https://github.com/cdhigh>
import re, time
import simple_ai_provider
from application.utils import loc_exc_pos

def get_summarizer_engines():
    return simple_ai_provider._PROV_AI_LIST

class HtmlSummarizer:
    def __init__(self, params: dict):
        self.params = params
        name = self.params.get('engine')
        if name not in simple_ai_provider._PROV_AI_LIST:
            default_log.warning(f'Unsupported provider {name}, fallback to gemini')
            name = 'gemini'
        self.aiAgent = self.create_engine(name, params)
    
    #创建一个AI封装实例
    def create_engine(self, name, params):
        return simple_ai_provider.SimpleAiProvider(name, params.get('api_key', ''), 
            model=params.get('model', ''), api_host=params.get('api_host', ''))

    #给一段文字做摘要，记住不要太长
    #返回 {'error': '', 'summary': ''}
    def summarize_text(self, text):
        #token是字节数根据不同的语种不能很好的对应，比如对应英语大约一个token对应4字节左右，
        #中文对应1-2字节，这里采用保守策略，一个token对应1字节，然后减去prompt的花销
        chunkSize = self.aiAgent.context_size - 200
        if chunkSize < 3500:
            chunkSize = 3500

        words = self.params.get('summary_words', 100)
        summary = ''
        errMsg = ''
        lang = self.params.get('summary_lang', '')
        if lang:
            summaryTips = f"Summarize the following text in the language of {lang}. The summary should accurately represent the content and be no more than {words} words:\n\n"
        else:
            summaryTips = f"Summarize the following text in the same language as the original text. The summary should accurately represent the content and be no more than {words} words:\n\n"

        text = re.sub(r'<[^>]+>', '', text)[:chunkSize]
        try:
            summary = self.aiAgent.chat(f"{summaryTips}{text}")
        except:
            errMsg = loc_exc_pos('Error in summarize_text')

        return {'error': errMsg, 'summary': summary}

    #使用 refine 方法生成长 HTML 文章的摘要
    #soup: BeautifulSoup实例
    #chunkSize: 每次处理的 HTML 文本块大小，可以覆盖默认值
    #maxIterations: 最大处理块数，避免执行时间过长
    def summarize_soup(self, soup, chunkSize=None, maxIterations=5):
        body = soup.find('body')
        if not body:
            return
        text = body.get_text()

        words = self.params.get('summary_words', 0) or 100

        #token是字节数根据不同的语种不能很好的对应，比如对应英语大约一个token对应4字节左右，
        #中文对应1-2字节，这里采用保守策略，一个token对应1字节，然后减去prompt的花销
        if not chunkSize:
            chunkSize = self.aiAgent.context_size - words - 300
        if chunkSize < 3500:
            chunkSize = 3500

        #将文本分块，这个分块比较粗糙，甚至会将单词断开，可能按照段落分块会更好，
        #但是考虑到AI的适应能力比较强，并且仅用于生成摘要，所以这个简单方案还是可以接受的
        chunks = [text[i:i + chunkSize] for i in range(0, len(text), chunkSize)]
        
        summaryTips = self.params.get('custom_prompt', '')
        lang = self.params.get('summary_lang', '')
        if summaryTips: #使用自定义prompt
            summaryTips = summaryTips.replace('{lang}', lang).replace('{words}', str(words))
        elif lang:
            summaryTips = f"Please improve and update the existing summary of the following text block(s), ensuring the summary is written in the language of {lang}. The updated summary should accurately reflect the content while distilling key points, arguments, and conclusions, and should not exceed {words} words:"
        else:
            summaryTips = f"Please improve and update the existing summary of the following text block(s), ensuring it is in the same language as the article and preset summary, while accurately reflecting the content and distilling key points, arguments, and conclusions. The updated summary should not exceed {words} words:"
            
        summary = None
        interval = self.aiAgent.request_interval
        iterNum = min(maxIterations, len(chunks))
        for i, chunk in enumerate(chunks[:iterNum], 1):
            prompt = f"{summaryTips}\n\nExisting summary:\n{summary}\n\nText block {i}:\n{chunk}\n\n"

            try:
                summary = self.aiAgent.chat(prompt)
            except:
                default_log.info(loc_exc_pos('Error in summarize_soup'))
                return

            if (i < iterNum) and (interval > 0.01):
                time.sleep(interval)

        #将摘要插在文章标题之后
        summaryTag = soup.new_tag('p', attrs={'class': 'ai_generated_summary', 
            'data-aiagent': str(self.aiAgent)})
        style = self.params.get('summary_style', '')
        if style:
            summaryTag['style'] = style
        b = soup.new_tag('b', attrs={'class': 'ai_summary_hint'})
        b.string = 'AI-Generated Summary: '
        summaryTag.append(b)
        summaryTag.append(summary)

        hTag = body.find(['h1','h2']) #type:ignore
        #判断此H1/H2是否在文章中间出现，如果是则不是文章标题
        if hTag and all(len(tag.get_text(strip=True)) < 100 for tag in hTag.previous_siblings): #type:ignore
            hTag.insert_after(summaryTag)
        else:
            body.insert(0, summaryTag)
