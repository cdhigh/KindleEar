#!/usr/bin/env python
# -*- coding:utf-8 -*-
from .dmzjbase import DMZJBaseBook


def getBook():
    return SaberFGO


class SaberFGO(DMZJBaseBook):
    title = u"[漫画]玩FGO的Saber桑"
    description = u"沉迷于抽卡辣鸡游戏FGO的骑士王的日常记事"
    feeds = [(u"[漫画]玩FGO的Saber桑", "https://manhua.dmzj.com/wanfgodesabersang")]
