#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#中文讨论贴：http://www.hi-pda.com/forum/viewthread.php?tid=1213082
#Author:
# cdhigh <https://github.com/cdhigh>
#Contributors:
# rexdf <https://github.com/rexdf>

import __builtin__, sys
from google.appengine.ext import vendor

__Version__ = '1.26.6'

__builtin__.__dict__['__Version__'] = __Version__

sys.path.insert(0, 'lib')
vendor.add('lib')
