#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#从recipe生成对应的输出格式
#Author: cdhigh <https://github.com/cdhigh>
import io, os
from calibre.ebooks.conversion.plumber import Plumber

#从输入格式生成对应的输出格式
#input_: recipe的文件名(后缀为recipe)，或包含recipe内容的StringIO实例，也可以是一个列表
#output: 输出文件名或BytesIO实例，如果使用BytesIO，则需要指定output_fmt参数
#input_fmt: 输入格式，如果输入是StringIO实例，则需要提供这个参数：'recipe', 'epub', 'mobi'
#output_fmt: 如果output为BytesIO，则需要提供这个参数: 'epub', 'mobi'
#options: 如果需要配置电子书生成过程中的一些参数，可以使用此字典传递
# 如: options={'debug_pipeline': path, 'verbose': 1}
def ConvertToEbook(input_, output, user, input_fmt=None, output_fmt='epub', options=None):
    input_fmt = 'recipe' if isinstance(input_, (list, io.StringIO)) and not input_fmt else input_fmt
    plumber = Plumber(input_, output, user, input_fmt='recipe', output_fmt=output_fmt)
    plumber.merge_ui_recommendations(options)
    plumber.run()
