#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#从recipe生成对应的输出格式
#Author: cdhigh <https://github.com/cdhigh>
import io, os
from calibre.ebooks.conversion.plumber import Plumber

#从输入格式生成对应的输出格式
#recipes: 编译后的recipe，为一个列表
#output: 输出文件名或BytesIO实例
#options: 额外的一些参数，为一个字典
# 如: options={'debug_pipeline': path, 'verbose': 1}
def ConvertRecipeToEbook(recipes, output, user, options=None):
    options = options or {}
    options.setdefault('output_profile', user.device)
    options.setdefault('input_profile', 'kindle')
    options.setdefault('remove_hyperlinks', user.remove_hyperlinks)
    options.setdefault('dont_compress', True)

    if not isinstance(recipes, list):
        recipes = [recipes]
    plumber = Plumber(recipes, output, user, output_fmt=user.book_type)
    plumber.merge_ui_recommendations(options)
    plumber.run()
