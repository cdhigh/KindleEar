#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


from datetime import datetime, timedelta, timezone
from dateutil import parser

utc_tz = timezone.utc
local_tz = datetime.now().astimezone().tzinfo
UNDEFINED_DATE = datetime(101,1,1, tzinfo=utc_tz)


def parse_iso8601(date_string, assume_utc=False, as_utc=True, require_aware=False):
    if not date_string:
        return UNDEFINED_DATE
    yourdate = parser.parse(date_string)
    return yourdate.astimezone(utc_tz if as_utc else local_tz)


if __name__ == '__main__':
    import sys
    print(parse_iso8601(sys.argv[-1]))
