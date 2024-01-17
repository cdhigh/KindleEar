#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#从recipe生成对应的输出格式
#Author: cdhigh <https://github.com/cdhigh>
import io
from calibre.ebooks.conversion.plumber import Plumber
from calibre.utils.logging import Log

#从recipe生成对应的输出格式
#input: recipe的文件名(后缀为recipe)，或包含recipe内容的BytesIO实例
#output: 输出文件名或BytesIO实例，如果使用BytesIO，则需要指定book_type参数
def BuildEbookFromRecipe(input, output, book_type='epub'):
    #calibre里面使用的log和python标准库使用的logging不兼容
    #可以直接调用log()，标准库必须使用log.info()
    #可以输出多个参数，标准库必须使用字符串格式化组合为一个字符串
    log = Log()
    log.filter_level = Log.DEBUG #DEBUG, INFO, WARN, ERROR
    plumber = Plumber(input, output, log, input_fmt='recipe', output_fmt=book_type)
    #plumber.merge_ui_recommendations(recommendations)
    plumber.run()
