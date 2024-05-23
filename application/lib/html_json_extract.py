#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#现在很多网页使用json保存文章内容，然后使用javascript渲染到DOM树
#这里尝试在json里面提取一些数据，尽管可能会有疏漏/多余和排版问题，但是总比什么内容都没有好
#Author: cdhigh <https://github.com/cdhigh>
import re, json
from collections import defaultdict
from operator import itemgetter
from bs4 import BeautifulSoup

def html_json_extract(html: str, language: str, url: str) -> str:
    soup = BeautifulSoup(html, 'lxml')
    scripts = sorted([tag.get_text(strip=True) for tag in soup.find_all('script')], key=lambda x: x.count('{'))
    if not scripts or scripts[-1].count('{') < 20 or (scripts[-1].count('{') != scripts[-1].count('}')):
        return html
        
    #使用大括号最多的一个代码段，因为如果js代码很复杂，一般都会放到单独的js文件，html放数据
    script = scripts[-1]
    pairs = find_bracket_pairs(script)
    #如果有大括号和中括号，优先使用更靠前的
    curlySpan = pairs['curly'][0][0] if pairs['curly'] else 0
    squareSpan = pairs['square'][0][0] if pairs['square'] else 0
    #各取三个进行测试，按出现顺序排序
    candidate = sorted(pairs['curly'][:3] + pairs['square'][:3], key=itemgetter(1))
    data = {}
    for item in candidate:
        try:
            data = json.loads(script[item[1] : item[2] + 1])
        except:
            continue
        else:
            break

    result = defaultdict(list)
    recursive_get_text(data, result)
    if not result:
        return html
    
    for key in result: #去重
        result[key] = list(dict.fromkeys(result[key]))
    longest = sorted([(sum(len(item) for item in value), key, value) 
        for key,value in result.items()], key=itemgetter(0), reverse=True)
    longest = [item for item in longest if item[0] > 2000][:3] #超过2000字才认为有正文内容
    if longest:
        finalList = []
        finals = {item[1]:item[2] for item in longest}
        for key in ['text', 'content', 'data', 'paragraph']:
            if key in finals:
                finalList = finals[key]
                break
        else:
            finalList = longest[0][2]

        finalTxt = ''.join([(item if item.startswith('<') else f'<p>{item}</p>') 
            for item in filtered(finalList, language)])

        #获取原本的title
        match = re.search(r'<title>(.*?)</title>', html, re.I|re.M|re.S)
        title = match.group(1).strip() if match else ''
        return f"""<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        <title>{title}</title></head><body>{finalTxt}
        <p style="color:#555555;font-size:60%;text-align:right;">Extracted by json algorithm.</p></body></html>"""
    else:
        return html

#查找每一对大括号和中括号的起始和终止索引号
#每个元素 (distance, start, end)
def find_bracket_pairs(string):
    cStack = []
    sStack = []
    pairs = {'curly': [], 'square': []}

    for index, char in enumerate(string):
        if char == '{':
            cStack.append(index)
        elif (char == '}') and cStack:
            startPos = cStack.pop()
            pairs['curly'].append((index - startPos, startPos, index))
        elif char == '[':
            sStack.append(index)
        elif (char == ']') and sStack:
            startPos = sStack.pop()
            pairs['square'].append((index - startPos, startPos, index))

    pairs['curly'].sort(key=itemgetter(0), reverse=True) #按照跨度排序
    pairs['square'].sort(key=itemgetter(0), reverse=True)
    return pairs

#递归获取里面的字符信息，返回一个字典，键为所有出现过的键，值为所有相同键的数值的列表
def recursive_get_text(block, result):
    if isinstance(block, dict):
        for key, value in block.items():
            if isinstance(value, str):
                result[key].append(value)
            else:
                recursive_get_text(value, result)
    elif isinstance(block, list):
        for item in block:
            recursive_get_text(item, result)


#根据段落长度，去掉文章末尾可能的样板代码
def filtered(paragraphs: list, language: str):
    #先根据段落长短进行标注
    if (language or '').lower().startswith(('zh', 'ja', 'ko')):
        lowLen = 30
        highLen = 100
    else:
        lowLen = 70
        highLen = 150

    #内嵌函数，根据内容和长度进行标识一段文本
    def flagIt(text):
        if ('\xa9' in text) or ('&copy' in text):
            return 'bad'
        else:
            size = len(text)
            return 'bad' if (size < lowLen) else ('good' if size > highLen else 'keep')
     
    flags = list(reversed([flagIt(text) for text in paragraphs]))
    for idx, flag in enumerate(flags):
        if flag == 'good':
            break
        elif flag == 'bad':
            flags[idx] = 'delete'

    #从末尾开始，删除不需要的文本
    flags.reverse()
    return [paragraphs[idx] for idx in range(len(paragraphs)) if flags[idx] != "delete"]
