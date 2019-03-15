#!/usr/bin/env python2
# encoding: utf-8

import re
import json
from urlparse import urljoin, unquote

from bs4 import BeautifulSoup
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseComicBook
from packer import decode_packed_codes


class DMZJBaseBook(BaseComicBook):
    accept_domains = ("https://manhua.dmzj.com",)
    host = "http://images.dmzj.com/"

    def get_chapter_list_from_api(self, url, comic_id):
        opener = URLOpener(self.host, addreferer=False, timeout=60)
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
            chapter_url = urljoin(
                url,
                "{chapter_id}.shtml?cid={comic_id}".format(
                    chapter_id=chapter["chapter_id"], comic_id=comic_id
                ),
            )
            chapters.append((chapter["chapter_title"], chapter_url))
        return chapters

    # 获取漫画章节列表
    def getChapterList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host, addreferer=False, timeout=60)
        chapterList = []

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn("fetch comic page failed: %s" % url)
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
                chapter_url = urljoin(
                    url,
                    "{chapter_id}.shtml?cid={comic_id}".format(
                        chapter_id=chapter["chapter_id"], comic_id=comic_id
                    ),
                )
                chapterList.append((chapter["chapter_title"], chapter_url))
            return chapterList
        else:
            return self.get_chapter_list_from_api(url, comic_id)

    def get_image_list_from_api(self, url):
        chapter_id, comic_id = re.search(r"(\d+)\.shtml\?cid=(\d+)", url).groups()
        opener = URLOpener(self.host, addreferer=False, timeout=60)

        result = opener.open(
            "http://v3api.dmzj.com/chapter/{comic_id}/{chapter_id}.json".format(
                comic_id=comic_id, chapter_id=chapter_id
            )
        )
        if result.status_code != 200 or not result.content:
            self.log.info("fetch v3 api json failed: %s, try v2" % result.status_code)
            result = opener.open(
                "http://v2.api.dmzj.com/chapter/{comic_id}/{chapter_id}.json?channel=Android&version=2.6.004".format(
                    comic_id=comic_id, chapter_id=chapter_id
                )
            )
            if result.status_code != 200 or not result.content:
                self.log.warn("fetch v2 api json failed: %s" % result.status_code)
                return []

        data = json.loads(result.content)
        return data["page_url"]

    # 获取漫画图片列表
    def getImgList(self, url):
        return self.get_image_list_from_api(url)
