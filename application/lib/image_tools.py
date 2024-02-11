#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""几个常用图像处理函数
"""
import io
from PIL import Image

#将一个超长图分割成多个图片，方便在电子书上阅读
#imgInst: 原始图像PIL的Image实例
#eachHeight: 每个图像的高度
#如果有分割，返回一个子图片二进制内容列表，否则返回None
def split_image_by_height(self, imgInst, eachHeight):
    fmt = imgInst.format
    imagesData = []
    top = 0
    while top < height:
        bottom = top + threshold
        if bottom > height:
            bottom = height
                
        part = imgInst.crop((0, top, width, bottom))
        part.load()
        partData = io.BytesIO()
        part.save(partData, fmt) #, **info)
        imagesData.append(partData.getvalue())
        
        #分图和分图重叠20个像素，保证一行字符能显示在其中一个分图中
        top = bottom - 20 if bottom < height else bottom
        
    return imagesData

#将图片缩小
#data: 二进制内容或BytesIO实例
#reduceTo: 需要缩小后的尺寸(width,height)
#pngToJpg: 有些型号的电子书对PNG支持不好，有些PNG显示不出来，可以使用此选项将图像转换为JPG
#graying: 将图像转换为灰度图，可以显著减小图像大小
#返回修改后的图像二进制内容
def compress_image(data, reduceTo=(600, 800), pngToJpg=False, graying=True):
    if not isinstance(data, io.BytesIO):
        data = io.BytesIO(data)
    imgInst = Image.open(data)
    width, height = imgInst.size
    fmt = imgInst.format
    if graying and imgInst.mode != "L":
        imgInst = imgInst.convert("L")
    
    if reduceTo:
        newWidth, newHeight = reduceTo
        if width > newWidth or height > newHeight:
            #按比率缩小，避免失真
            ratio = min(newWidth / width, newHeight / height)
            imgInst = imgInst.resize((int(width * ratio), int(height * ratio)), Image.Resampling.LANCZOS)

    if pngToJpg and fmt == 'PNG':
        data = io.BytesIO()
        imgInst.save(data, 'JPEG')
    else:
        data = io.BytesIO()
        imgInst.save(data, fmt)
    
    return data.getvalue()
