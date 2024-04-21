#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#因为html5_parser不提供二进制安装包，所以KindleEar使用html5lib代替
#为了让依赖html5_parser的recipe可以继续使用，使用此文件做桩
from calibre.ebooks.oeb.polish.parsing import parse

