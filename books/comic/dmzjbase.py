#!/usr/bin/env python3
# encoding: utf-8

import re
import json

from bs4 import BeautifulSoup
from lib.urlopener import UrlOpener
from books.base_comic_book import BaseComicBook

class DMZJBaseBook(BaseComicBook):
    accept_domains = ("https://manhua.dmzj.com", "https://m.dmzj.com")
    host = "http://images.dmzj.com/"

    def GetChapterListFromApi(self, comicId):
        opener = UrlOpener(addreferer=False, timeout=self.timeout)
        result = opener.open("http://v3api.dmzj.com/comic/{}.json".format(comicId))

        if result.status_code != 200:
            self.log.info("fetch v3 chapter list failed: {}, try v2".format(result.status_code))
            result = opener.open("http://v2.api.dmzj.com/comic/{}.json?channel=Android&version=2.6.004".format(comicId))
            if result.status_code != 200:
                self.log.warn("Fetch v2 chapter list failed: {}".format(result.status_code))
                return []

        data = result.json
        chapterDatas = []
        for chapterData in data["chapters"]:
            chapterDatas += chapterData["data"]
        chapterDatas.sort(key=lambda d: d["chapter_id"])
        chapters = []
        for chapter in chapterDatas:
            chapter_url = "https://m.dmzj.com/view/{}/{}.html".format(comicId, chapter["chapter_id"])
            chapters.append((chapter["chapter_title"], chapter_url))
        return chapters

    def GetChapterListFromMobileUrl(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(addreferer=False, timeout=60)

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn("fetch comic page failed: %s" % result.status_code)
            return []

        content = self.AutoDecodeContent(
            result.content, decoder, self.feed_encoding, opener.realurl, result.headers
        )

        if "obj_id" not in content:
            self.log.warn(u"Can't find obj_id form {}".format(url))
            return []

        comic_id = re.search('obj_id = "(\d+)"', content).group(1)
        data_match = re.search("initIntroData\(([^;]+)\);", content)
        if not data_match:
            return self.get_chapter_list_from_api(comic_id)
        datas = json.loads(data_match.group(1))
        chapter_datas = []
        for data in datas:
            chapter_datas += data["data"]
        if not chapter_datas:
            return self.get_chapter_list_from_api(comic_id)
        chapter_datas.sort(key=lambda d: d["id"])
        chapters = []
        for chapter in chapter_datas:
            chapter_url = "https://m.dmzj.com/view/{comic_id}/{chapter_id}.html".format(
                chapter_id=chapter["id"], comic_id=comic_id
            )
            chapters.append((chapter["chapter_name"], chapter_url))
        return chapters

    # 获取漫画章节列表
    def GetChapterList(self, url):
        if url.startswith("https://m.dmzj.com"):
            return self.GetChapterListFromMobileUrl(url)
        opener = URLOpener(addreferer=False, timeout=self.timeout)
        chapterList = []

        result = opener.open(url)
        if result.status_code != 200:
            self.log.warn("Fetch comic page failed: {}".format(result.status_code))
            return chapterList

        content = result.text
        comicId = re.search('g_comic_id = "([^"]+)', content)
        if comicId:
            comicId = comicId.group(1)
        else:
            return chapterList

        # try get chapters from html
        soup = BeautifulSoup(content, "lxml")
        chapterDatas = []
        for comicClassName in ["cartoon_online_border", "cartoon_online_border_other"]:
            for div in soup.find_all("div", attrs={"class": comicClassName}):
                for link in div.find_all("a"):
                    #[(chapterId, chapterTitle)]
                    chapterDatas.append((int(re.search("\/(\d+)\.shtml", link.get("href")).group(1)), link.string))

        if chapterDatas:
            chapterDatas.sort(key=lambda d: d["chapter_id"])
            for chapter in chapterDatas:
                chapterUrl = "https://m.dmzj.com/view/{}/{}.html".format(comicId, chapter[0])
                chapterList.append((chapter[1], chapterUrl))
            return chapterList
        else:
            return self.GetChapterListFromApi(comicId)

    def GetImageListFromApi(self, url):
        comicId, chapterId = re.search(r"(\d+)/(\d+)\.html", url).groups()
        opener = UrlOpener(addreferer=False, timeout=self.timeout)

        result = opener.open("http://v3api.dmzj.com/chapter/{}/{}.json".format(comicId, chapterId))
        if result.status_code != 200:
            self.log.info("Fetch v3 api json failed: {}, try v2".format(result.status_code))
            result = opener.open("http://v2.api.dmzj.com/chapter/{}/{}.json?channel=Android&version=2.6.004".format(comicId, chapterId))
            if result.status_code != 200:
                self.log.warn("Fetch v2 api json failed: {}".format(result.status_code))
                return []

        data = result.json
        return data["page_url"]

    # 获取漫画图片列表
    def GetImgList(self, url):
        opener = UrlOpener(addreferer=False, timeout=self.timeout)

        result = opener.open(url)
        if result.status_code != 200:
            self.log.warn("fetch comic page failed: {}".format(result.status_code))
            return []

        readerDataMatch = re.search("mReader\.initData\(({.+})", result.text)
        if readerDataMatch:
            readerData = readerDataMatch.group(1)
            return json.loads(readerData)["page_url"]
        else:
            self.log.info("Failed to get images from content, try api")
            return self.GetImageListFromApi(url)
