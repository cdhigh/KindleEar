#!/usr/bin/env python3
# encoding: utf-8
import re, json
from lib.urlopener import URLOpener
from lib.autodecoder import AutoDecoder
from books.base import BaseComicBook
from bs4 import BeautifulSoup
from packer import decode_packed_codes


class ManHuaRenBaseBook(BaseComicBook):
    accept_domains = ("https://www.manhuaren.com", "http://www.dm5.com")
    host = "https://www.manhuaren.com"

    def getChapterList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(self.host)
        chapterList = []

        url = url.replace("http://www.dm5.com", "https://www.manhuaren.com")

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn(
                "fetch comic page failed: {} (status code {}, content {})".format(
                    url, result.status_code, result.content
                )
            )
            return chapterList

        content = self.AutoDecodeContent(
            result.content, decoder, self.feed_encoding, opener.realurl, result.headers
        )

        soup = BeautifulSoup(content, "html.parser")

        chapter_datas = []
        for link in soup.find_all("a", {"class": "chapteritem"}):
            chapter_datas.append(
                {
                    "chapter_id": int(re.search("m(\d+)", link.get("href")).group(1)),
                    "chapter_title": unicode(link.string),
                }
            )
        chapter_datas.sort(key=lambda d: d["chapter_id"])
        for chapter in chapter_datas:
            chapter_url = "http://www.manhuaren.com/m{}/".format(chapter["chapter_id"])
            chapterList.append((chapter["chapter_title"], chapter_url))
        return chapterList

    def getImgList(self, url):
        decoder = AutoDecoder(isfeed=False)
        opener = URLOpener(url)

        result = opener.open(url)
        if result.status_code != 200 or not result.content:
            self.log.warn(
                "fetch comic page failed: {} (status code {}, content {})".format(
                    url, result.status_code, result.content
                )
            )
            return []

        content = self.AutoDecodeContent(
            result.content, decoder, self.feed_encoding, opener.realurl, result.headers
        )
        soup = BeautifulSoup(content, "html.parser")
        scripts = soup.findAll("script", {"type": "text/javascript"})
        packed_js = None
        for script in scripts:
            if "newImgs" in script.text:
                packed_js = script.text
                break
        if not packed_js:
            self.log.warn("Can't find js")
            return []
        codes = decode_packed_codes(packed_js)
        return re.findall("'(.+?)'", codes)
