#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#用AI对文章进行摘要
#Author: cdhigh <https://github.com/cdhigh>
import re, time
import simple_ai_provider

def get_summarizer_engines():
    return simple_ai_provider._PROV_AI_LIST

class HtmlSummarizer:
    def __init__(self, params: dict):
        self.params = params
        engineName = self.params.get('engine')
        if engineName not in simple_ai_provider._PROV_AI_LIST:
            engineName = 'gemini'
        self.engineName = engineName
        self.engineProperty = simple_ai_provider._PROV_AI_LIST.get(engineName, {})
        self.aiAgent = self.create_engine(self.engineName, params)
    
    #创建一个AI封装实例
    def create_engine(self, engineName, params):
        return simple_ai_provider.SimpleAiProvider(engineName, params.get('api_key', ''), 
            model=params.get('model', ''), api_host=params.get('api_host', ''))

    #给一段文字做摘要，记住不要太长
    #返回 {'error': '', 'summary': ''}
    def summarize_text(self, text):
        #token是字节数根据不同的语种不能很好的对应，比如对应英语大约一个token对应4字节左右，
        #中文对应1-2字节，这里采用保守策略，一个token对应1字节，然后减去prompt的花销
        chunkSize = self.engineProperty.get('context_size', 4096) - 200
        if chunkSize < 2000:
            chunkSize = 2000

        summarySize = self.params.get('summary_size', 200)
        summary = ''
        errMsg = ''
        lang = self.params.get('summary_lang', '')
        if lang:
            summaryTips = (f"Summarize the following text in {lang}. The summary should accurately represent the content "
                f"and be no more than {summarySize} words:\n\n")
        else:
            summaryTips = (f"Summarize the following text in the same language as the original text. The summary should accurately represent the content "
            f"and be no more than {summarySize} words:\n\n")

        text = re.sub(r'<[^>]+>', '', text)[:chunkSize]
        #try:
        summary = self.aiAgent.chat(f"{summaryTips}{text}")
        #except Exception as e:
        #errMsg = str(e)

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

        #token是字节数根据不同的语种不能很好的对应，比如对应英语大约一个token对应4字节左右，
        #中文对应1-2字节，这里采用保守策略，一个token对应1字节，然后减去prompt的花销大约500字节
        if not chunkSize:
            chunkSize = self.engineProperty.get('context_size', 4096) - 500
        if chunkSize < 2000:
            chunkSize = 2000

        #将文本分块，这个分块比较粗糙，可能按照段落分块会更好，但是考虑到AI的适应能力比较强，
        #并且仅用于生成摘要，所以这个简单方案还是可以接受的
        chunks = [text[i:i + chunkSize] for i in range(0, len(text), chunkSize)]
        summarySize = self.params.get('summary_size', 200)
        interval = self.engineProperty.get('request_interval', 0)
        summary = None

        lang = self.params.get('summary_lang', '')
        if lang:
            summaryTips = f"Please refine or update the summary based on the following text block, ensuring the summary is in the language: {lang}, and make it more accurately reflect the article content:\n\n"
        else:
            summaryTips = f"Please refine or update the summary based on the following text block, ensuring the summary is in the same language as the article/preset summary, and make it more accurately reflect the article content:\n\n"
        errMsg = ''
        for i, chunk in enumerate(chunks[:maxIterations]):
            prompt = (
                f"The current summary is:\n{summary}\n\n{summaryTips}"
                f"Text block {i + 1}:\n{chunk}\n\n"
                f"Please generate an updated summary of no more than {summarySize} words."
            )
            try:
                summary = self.aiAgent.chat(prompt)
            except Exception as e:
                errMsg = str(e)
                break
            if interval > 0:
                time.sleep(interval)

        if errMsg:
            default_log.info(f'Error in summary_soup: {errMsg}')
            return

        #将摘要插在文章标题之后
        summaryTag = soup.new_tag('p', attrs={'class': 'ai_generated_summary'})
        style = self.params.get('summary_style', '')
        if style:
            summaryTag['style'] = style
        b = soup.new_tag('b')
        b.string = 'AI-Generated Summary: '
        summaryTag.append(b)
        summaryTag.append(summary)

        hTag = body.find(['h1','h2']) #type:ignore
        #判断此H1/H2是否在文章中间出现，如果是则不是文章标题
        if hTag and all(len(tag.get_text(strip=True)) < 100 for tag in hTag.previous_siblings): #type:ignore
            hTag.insert_after(summaryTag)
        else:
            body.insert(0, summaryTag)
