#!/usr/bin/env python
# -*- coding:utf-8 -*-
import re

from base import *
from StringIO import StringIO
from PIL import Image

def getBook():
    return Qiushibaike

class Qiushibaike(WebpageBook):
    title                 = u'糗事百科'
    description           = u'快乐就是要建立在别人的痛苦之上'
    language = 'zh-cn'
    feed_encoding = "utf-8"
    page_encoding = "utf-8"
    mastheadfile = "mh_qiushibaike.gif"
    coverfile = "cv_qiushibaike.jpg"
    network_timeout       = 30
    keep_only_tags = [dict(name='div', attrs={'class':['main']}), # qiushibaike
        dict(name='div',attrs={'class':['block joke-item']}), # haha.mx
            ]
    remove_tags = []
    remove_ids = ['bdshare',]
    remove_classes = ['sharebox','comment','share','up','down', #qiushibaike
            'backtop','close','author','col2','sponsor','pagebar', #qiushibaike
            'toolkit fr','fr','clearfix mt-15',] # hah.mx
    remove_attrs = []
    
    feeds = [
            #(u'8小时最热', r'http://www.qiushibaike.com'),
            (u'24小时最热Page1', r'http://www.qiushibaike.com/hot'),
            (u'24小时最热Page2', r'http://www.qiushibaike.com/hot/page/2'),
            #(u'哈哈MX', r'http://www.haha.mx/'),
            (u'哈哈MX(24Hrs)Page1', r'http://www.haha.mx/good/day'),
            (u'哈哈MX(24Hrs)Page2', r'http://www.haha.mx/good/day/2'),
           ]
    
    def processtitle(self, title):
        title = re.sub(r'(\n)+', '', title)
        title = title.replace(u' :: 糗事百科 :: 快乐减压 健康生活', u'')
        return title.replace(u'——分享所有好笑的事情', u'')
        
    def soupbeforeimage(self, soup):
        for img in list(soup.find_all('img')): #HAHA.MX切换为大图链接
            src = img['src']
            if src.find(r'/small/') > 0:
                img['src'] = src.replace(r'/small/', r'/big/')
        
    def soupprocessex(self, soup):
        for article in soup.find_all("a", attrs={"href":re.compile(r'^/article')}):
            p = soup.new_tag("p", style='color:grey;text-decoration:underline;')
            p.string = article.string
            article.replace_with(p)
        
        first = True
        for detail in soup.find_all("div", attrs={"class":"detail"}):
            if not first:
                hr = soup.new_tag("hr")
                detail.insert(0, hr)
            first = False
        
        first = True
        for item in soup.find_all("div", attrs={"class":"block joke-item"}):
            if not first:
                hr = soup.new_tag("hr")
                item.insert(0, hr)
            first = False
    
    def process_image(self, data, opts):
        try:
            if not opts or not opts.process_images or not opts.process_images_immediately:
                return data
            elif opts.mobi_keep_original_images:
                return mobify_image(data)
            else:
                return rescale_image_QSBK(data, png2jpg=opts.image_png_to_jpg,
                                graying=opts.graying_image,
                                reduceto=opts.reduce_image_to)
        except Exception:
            return None

def rescale_image_QSBK(data, maxsizeb=4000000, dimen=None, 
                png2jpg=False, graying=True, reduceto=(600,800)):
    if not isinstance(data, StringIO):
        data = StringIO(data)
    img = Image.open(data)
    width, height = img.size
    fmt = img.format
    if graying and img.mode != "L":
        img = img.convert("L")
    
    reducewidth, reduceheight = reduceto
    
    if dimen is not None:
        if hasattr(dimen, '__len__'):
            width, height = dimen
        else:
            width = height = dimen
        img.thumbnail((width, height))
        if png2jpg and fmt == 'PNG':
            fmt = 'JPEG'
        data = StringIO()
        img.save(data, fmt)
    elif width > reducewidth or height > reduceheight:
        ratio = min(float(reducewidth)/float(width), float(reduceheight)/float(height))
        neww,newh = int(width*ratio),int(height*ratio)
        if newh >= reduceheight-1 and float(height)/float(width) >= 18.0:
            imgnew = Image.new('L' if graying else 'RGB', (int(width*4), int(height/4)), 'white')
            region1 = img.crop((0,0,width,int(height/4)))
            region2 = img.crop((0,int(height/4),width,int(height/2)))
            region3 = img.crop((0,int(height/2),width,int(height*3/4)))
            region4 = img.crop((0,int(height*3/4),width,height))
            region1.load()
            region2.load()
            region3.load()
            region4.load()
            imgnew.paste(region1,(0,0))
            imgnew.paste(region2,(width,0))
            imgnew.paste(region3,(width*2,0))
            imgnew.paste(region4,(width*3,0))
            ratio = min(float(reducewidth)/float(width*4), float(reduceheight)/float(height/4))
            neww,newh = int(width*4*ratio),int(height/4*ratio)
            img = imgnew.resize((neww, newh))
        elif newh >= reduceheight-1 and float(height)/float(width) >= 11.0:
            imgnew = Image.new('L' if graying else 'RGB', (int(width*3), int(height/3)), 'white')
            region1 = img.crop((0,0,width,int(height/3)))
            region2 = img.crop((0,int(height/3),width,int(height*2/3)))
            region3 = img.crop((0,int(height*2/3),width,height))
            region1.load()
            region2.load()
            region3.load()
            imgnew.paste(region1,(0,0))
            imgnew.paste(region2,(width,0))
            imgnew.paste(region3,(width*2,0))
            ratio = min(float(reducewidth)/float(width*3), float(reduceheight)/float(height/3))
            neww,newh = int(width*3*ratio),int(height/3*ratio)
            img = imgnew.resize((neww, newh))
        elif newh >= reduceheight-1 and float(height)/float(width) >= 4.0:
            imgnew = Image.new('L' if graying else 'RGB', (int(width*2), int(height/2)), 'white')
            region1 = img.crop((0,0,width,int(height/2)))
            region2 = img.crop((0,int(height/2),width,height))
            region1.load()
            region2.load()
            imgnew.paste(region1,(0,0))
            imgnew.paste(region2,(width,0))
            ratio = min(float(reducewidth)/float(width*2), float(reduceheight)/float(height/2))
            neww,newh = int(width*2*ratio),int(height/2*ratio)
            img = imgnew.resize((neww, newh))
        else:
            img = img.resize((neww, newh))
        if png2jpg and fmt == 'PNG':
            fmt = 'JPEG'
        data = StringIO()
        img.save(data, fmt)
    elif png2jpg and fmt == 'PNG':
        data = StringIO()
        img.save(data, 'JPEG')
    else:
        data = StringIO()
        img.save(data, fmt)
    
    return data.getvalue()