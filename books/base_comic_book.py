#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
KindleEar电子书基类，每本投递到kindle的书籍抽象为这里的一个类。
可以继承BaseFeedBook类而实现自己的定制书籍。
cdhigh <https://github.com/cdhigh>
"""
import io
from collections import namedtuple
from books.base_book import *

#漫画书章节列表返回的每一项的结构
ComicItemTuple = namedtuple("ComicItemTuple", "name title imgList url nextChapterIndex")


#漫画专用，漫画的主要特征是全部为图片，而且图片默认全屏呈现
#由 insert0003 <https://github.com/insert0003> 贡献代码
#如果要处理连载的话，可以使用 ComicUpdateLog 数据库表来记录和更新
class BaseComicBook(BaseFeedBook):
    # 子类填充： (https://www.manhuagui.com", "https://m.manhuagui.com")
    accept_domains = tuple()

    title         = ""
    description   = ""
    language      = ""
    masthead_file = "mh_default.gif"
    cover_file    = "cv_bound.jpg"
    feeds = []  # 子类填充此列表[('name', mainurl),...]
    min_image_size = (150, 150)  # 小于这个尺寸的图片会被删除，用于去除广告图片或按钮图片之类的

    # 子类必须实现此函数，返回 [ComicItemTuple, ...]
    def ParseFeedUrls(self):
        chapters = []  # 用于返回

        username = self.UserName
        for item in self.feeds:
            bookName, url = item[0], item[1]
            self.log.info("Parsing Feed {} for {}".format(url, bookName))

            lastDeliver = LastDelivered.all().filter("username = ", username).filter("bookname = ", bookName).get()
            if not lastDeliver:
                self.log.info("These is no log in db LastDelivered for name: {}, set to 0".format(bookName))
                nextChapterIndex = 0
            else:
                nextChapterIndex = lastDeliver.num

            chapterList = self.GetChapterList(url)
            if nextChapterIndex < len(chapterList):
                chapterTitle, chapterUrl = chapterList[nextChapterIndex]
                self.log.info("Add {}: {}".format(chapterTitle, chapterUrl))
                imgList = self.GetImgList(chapterUrl)
                if not imgList:
                    self.log.warning("can not found image list: {}".format(chapterUrl))
                    break
                nextChapterIndex += 1
                chapters.append(ComicItemTuple(bookName, chapterTitle, imgList, chapterUrl, nextChapterIndex))
            else:
                self.log.info("No new chapter for {} (total {}, pushed {})".format(bookName, len(chapterList), nextChapterIndex))
        return chapters

    #生成器，返回电子书中的每一项内容，包括HTML或图像文件，
    #每次返回一个命名元组，可能为 ItemHtmlTuple, ItemImageTuple, ItemCssTuple
    def Items(self):
        for comicItem in self.ParseFeedUrls():
            self.UpdateLastDelivered(comicItem.name, comicItem.title, comicItem.nextChapterIndex)
            yield from self.GenImageItems(comicItem.imgList, comicItem.url)

    #获取漫画章节列表，返回[(title, url),...]
    def GetChapterList(self, url):
        return []

    #获取漫画图片列表，返回[url,...]
    def GetImgList(self, url):
        return []
    
    #获取漫画图片内容，返回二进制图像数据
    def AdjustImgContent(self, content):
        return content

    # 生成器
    def GenImageItems(self, imgList, referer):
        opener = UrlOpener(referer, timeout=self.timeout, headers=self.extra_header)
        minWidth, minHeight = self.min_image_size
        if self.needs_subscription:
            self.login(opener)

        for i, url in enumerate(imgList):
            result = opener.open(url)
            if result.status_code != 200:
                raise Exception("Download failed ({}): code {}".format(result.status_code, url))
                
            content = self.AdjustImgContent(result.content)

            #先判断是否是图片
            imgType = imghdr.what(None, content)
            if imgType:
                yield from self.PrepareComicImageManifest(content, url)

            else: #不是图片，有可能是包含图片的网页，抽取里面的图片
                soup = BeautifulSoup(result.text, 'lxml')
                self.RectifyImageSrcInSoup(soup, result.url)
                
                #有可能一个网页有多个漫画图片，而且还有干扰项(各种按钮/广告等)，所以先全部保存再判断好了
                #列表格式[(url, content),...]
                imgContentList = []
                for img in soup.find_all('img'):
                    imgUrl = img['src'] if 'src' in img.attrs else None
                    if not imgUrl:
                        continue
                        
                    #为了省时间，如果图片属性中有width/height，则也可以先初步判断是不是漫画图片
                    if 'width' in img.attrs:
                        width = img.attrs['width'].replace('"', '').replace("'", '').replace('px', '').strip()
                        try:
                            if int(width) < minWidth:
                                continue
                        except:
                            pass
                            
                    if 'height' in img.attrs:
                        height = img.attrs['height'].replace('"', '').replace("'", '').replace('px', '').strip()
                        try:
                            if int(height) < minHeight:
                                continue
                        except:
                            pass
                            
                    imgResult = opener.open(imgUrl)
                    if imgResult.status_code == 200:
                        imgContentList.append((imgUrl, imgResult.content))
                
                if not imgContentList:
                    continue

                #判断图片里面哪些是真正的漫画图片
                isComics = [True for n in range(len(imgContentList))]
                for idx, (imgUrl, imgContent) in enumerate(imgContentList):
                    imgInstance = Image.open(io.BytesIO(imgContent))
                    width, height = imgInstance.size
                    #图片太小则排除
                    #一般横幅广告图片都是横长条，可以剔除
                    if any((width < minWidth, height < minHeight, width > height * 4)):
                        isComics[idx] = False
                    
                #如果所有的图片都被排除了，则使用所有图片里面尺寸最大的
                if not any(isComics):
                    imgContentList.sort(key=lambda x: len(x[1]), reverse=True)
                    imgContentList = [imgContentList[0]]
                else:
                    imgContentList = [item for idx, item in enumerate(imgContentList) if isComics[idx]]
                                    
                #列表中的就是漫画图片
                for imgUrl, imgContent in imgContentList:
                    imgType = imghdr.what(None, imgContent)
                    if imgType:
                        yield from self.PrepareComicImageManifest(imgContent, url)

    #处理单个图像，然后使用生成器模式返回一个或多个 ItemImageTuple/ItemHtmlTuple 实例
    #data: 图像二进制内容
    #url: 文章的URL
    def PrepareComicImageManifest(self, data, url):
        imgContent = self.TransformImage(data, self.SplitComicWideImage)
        if not isinstance(imgContent, list):
            imgContent = [imgContent]

        imgType = imghdr.what(None, imgContent[0])
        imgIndex = self.AutoImageIndex
        imgPartUrl = url
        imgMime = "image/{}".format(imgType)
        imgType = imgType.replace("jpeg", "jpg")

        for idx, imgPartContent in enumerate(imgContent):
            imgName = "img{}_{}.{}".format(imgIndex, idx, imgType)
            if idx == 0:
                imgPartUrl = url
            else:
                imgPartUrl += '_'

            yield ItemImageTuple(imgMime, imgPartUrl, imgName, imgPartContent, False)
            #每个图片当做一篇文章，否则全屏模式下图片会挤到同一页
            tmpHtml = imageHtmlTemplate.format(title=imgName, imgFilename=imgName)
            yield ItemHtmlTuple(imgName, url, imgName, BeautifulSoup(tmpHtml, 'lxml'), "", "")

    # 更新已经推送的序号和标题到数据库
    def UpdateLastDelivered(self, bookname, chapterTitle, num):
        userName = self.UserName
        dbItem = (
            LastDelivered.all()
            .filter("username = ", userName)
            .filter("bookname = ", bookname)
            .get()
        )
        self.last_delivered_volume = chapterTitle
        now = datetime.datetime.utcnow() + datetime.timedelta(
            hours=TIMEZONE
        )
        if dbItem:
            dbItem.num = num
            dbItem.record = self.last_delivered_volume
            dbItem.datetime = now
        else:
            dbItem = LastDelivered(
                username=userName,
                bookname=bookname,
                num=num,
                record=self.last_delivered_volume,
                datetime=now,
            )
        dbItem.put()

    #如果一个漫画图片为横屏，则将其分隔成2个图片
    def SplitComicWideImage(self, data):
        if not isinstance(data, io.BytesIO):
            data = io.BytesIO(data)

        img = Image.open(data)
        width, height = img.size
        fmt = img.format
        #宽>高才认为是横屏
        if height > width:
            return data

        imagesData = []
        part2 = img.crop((width / 2 - 10, 0, width, height))
        part2.load()
        part2Data = io.BytesIO()
        part2.save(part2Data, fmt)
        imagesData.append(part2Data.getvalue())

        part1 = img.crop((0, 0, width / 2 + 10, height))
        part1.load()
        part1Data = io.BytesIO()
        part1.save(part1Data, fmt)
        imagesData.append(part1Data.getvalue())

        return imagesData
