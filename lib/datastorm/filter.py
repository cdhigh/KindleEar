#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from typing import Union

class Filter:
    def __init__(self, item: str, op: str, value: Union[str, int, float, bool]):
        self.item = item
        self.op = op
        self.value = value

    def __repr__(self):
        return "< Filter: {} {} {} >".format(self.item, self.op, self.value)  # pragma: no cover
