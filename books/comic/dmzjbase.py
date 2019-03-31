#!/usr/bin/env python2
# encoding: utf-8

import re
import json

from bs4 import BeautifulSoup
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseComicBook


class DMZJBaseBook(BaseComicBook):
    accept_domains = ("https://manhua.dmzj.com", "https://m.dmzj.com")
    host = "http://images.dmzj.com/"

    def get_chapter_list_from_api(self, comic_id):
        opener = URLOpener(addreferer=False, timeout=60)
        json_result = opener.open(
            "http://v3api.dmzj.com/comic/{comic_id}.json".format(comic_id=comic_id)
        )

        if json_result.status_code != 200 or not json_result.content:
            self.log.info(
                "fetch v3 chapter list failed: %s, try v2" % json_result.status_code
            )
            json_result = opener.open(
                "http://v2.api.dmzj.com/comic/{comic_id}.json?channel=Android&version=2.6.004".format(
                    comic_id=comic_id
                )
            )
            if json_result.status_code != 200 or not json_result.content:
                self.log.warn(
                    "fetch v2 chapter list failed: %s" % json_result.status_code
                )
                return []

        data = json.loads(json_result.content)
        chapter_datas = []
        for chapters_data in data["chapters"]:
            chapter_datas += chapters_data["data"]
        chapter_datas.sort(key=lambda d: d["chapter_id"])
        chapters = []
        for chapter in chapter_datas:
            chapter_url = "https://m.dmzj.com/view/{comic_id}/{chapter_id}.html".format(
                chapter_id=chapter["chapter_id"], comic_id=comic_id
            )
            chapters.append((chapter["chapter_title"], chapter_url))
        return chapters

    def get_chapter_list_from_mobile_url(self, url):
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
    def getChapterList(self, url):
        if url.startswith("https://m.dmzj.com"):
            return self.get_chapter_list_from_mobile_url(url)
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(addreferer=False, timeout=60)
        chapterList = []

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn("fetch comic page failed: %s" % result.status_code)
            return chapterList

        content = self.AutoDecodeContent(
            result.content, decoder, self.feed_encoding, opener.realurl, result.headers
        )

        comic_id = re.search('g_comic_id = "([^"]+)', content).group(1)

        # try get chapters from html
        soup = BeautifulSoup(content, "html.parser")
        chapter_datas = []
        for comic_classname in ["cartoon_online_border", "cartoon_online_border_other"]:
            divs = soup.find_all("div", attrs={"class": comic_classname})
            if not divs:
                continue
            for div in divs:
                for link in div.find_all("a"):
                    chapter_datas.append(
                        {
                            "chapter_id": int(
                                re.search("\/(\d+)\.shtml", link.get("href")).group(1)
                            ),
                            "chapter_title": unicode(link.string),
                        }
                    )
        if chapter_datas:
            chapter_datas.sort(key=lambda d: d["chapter_id"])
            for chapter in chapter_datas:
                chapter_url = "https://m.dmzj.com/view/{comic_id}/{chapter_id}.html".format(
                    chapter_id=chapter["chapter_id"], comic_id=comic_id
                )
                chapterList.append((chapter["chapter_title"], chapter_url))
            return chapterList
        else:
            return self.get_chapter_list_from_api(comic_id)

    def get_image_list_from_api(self, url):
        comic_id, chapter_id = re.search(r"(\d+)/(\d+)\.html", url).groups()
        opener = URLOpener(addreferer=False, timeout=60)

        result = opener.open(
            "http://v3api.dmzj.com/chapter/{comic_id}/{chapter_id}.json".format(
                comic_id=comic_id, chapter_id=chapter_id
            )
        )
        if result.status_code != 200:
            self.log.info("fetch v3 api json failed: %s, try v2" % result.status_code)
            result = opener.open(
                "http://v2.api.dmzj.com/chapter/{comic_id}/{chapter_id}.json?channel=Android&version=2.6.004".format(
                    comic_id=comic_id, chapter_id=chapter_id
                )
            )
            if result.status_code != 200:
                self.log.warn("fetch v2 api json failed: %s" % result.status_code)
                return []

        data = json.loads(result.content)
        return data["page_url"]

    # 获取漫画图片列表
    def getImgList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(addreferer=False, timeout=60)

        result = opener.open(url)
        if result.status_code != 200:
            self.log.warn("fetch comic page failed: %s" % result.status_code)
            return []

        content = self.AutoDecodeContent(
            result.content, decoder, self.feed_encoding, opener.realurl, result.headers
        )

        reader_data_match = re.search("mReader\.initData\(({.+})", content)
        if reader_data_match:
            reader_data = reader_data_match.group(1)
            return json.loads(reader_data)["page_url"]
        self.log.info("Failed to get images from content, try api")

        return self.get_image_list_from_api(url)
