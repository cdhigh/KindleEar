#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#从recipe生成对应的输出格式
#Author: cdhigh <https://github.com/cdhigh>
import io, os
from typing import Union
from calibre.ebooks.conversion.plumber import Plumber
from calibre.utils.logging import Log

#从输入格式生成对应的输出格式
#input: recipe的文件名(后缀为recipe)，或包含recipe内容的BytesIO实例
#output: 输出文件名或BytesIO实例，如果使用BytesIO，则需要指定book_type参数
#input_fmt: 输入格式，如果输入是BytesIO实例，则需要提供这个参数：'recipe', 'epub', 'mobi'
#output_fmt: 如果output为BytesIO，则需要提供这个参数: 'epub', 'mobi'
#options: 如果需要配置电子书生成过程中的一些参数，可以使用此字典传递
# extra_options={'debug_pipeline': path, 'verbose': 1}
def ConvertToEbook(input: Union[str, io.BytesIO], output: Union[str, io.BytesIO], 
                    input_fmt: str=None,  output_fmt: str='epub', options: dict=None):
    #calibre里面使用的log和python标准库使用的logging不兼容
    #可以直接调用log()，标准库必须使用log.info()
    #可以输出多个参数，标准库必须使用字符串格式化组合为一个字符串
    log = Log()
    input_fmt = 'recipe' if isinstance(input, io.BytesIO) and not input_fmt else input_fmt
    plumber = Plumber(input, output, log, input_fmt='recipe', output_fmt=output_fmt)
    plumber.merge_ui_recommendations(options)
    plumber.run()
