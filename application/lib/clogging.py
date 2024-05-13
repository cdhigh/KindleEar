#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Author: cdhigh <https://github.com/cdhigh>
#Calibre使用的Logger和python的不兼容，不方便管理
#使用此定制的类来将Calibre的Log和其他部分的融合起来
#兼容方案主要有两点：
#1. 支持多个位置参数的msg(借用*args)
#2. 支持直接调用 __call__
import os, logging

#设置所有需要的logging的level
#level: 字符串或整形level
#only: 是否仅设置某个Logger的配置
def set_log_level(level, only=None):
    level = logging._nameToLevel.get(level.upper(), logging.WARNING) if isinstance(level, str) else level
    if os.environ.get('DATABASE_URL') == 'datastore': #GAE平台上的日志已经有日期了，不需要添加
        formatter = logging.Formatter('[%(filename)s:%(lineno)d] %(message)s')
    else:
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(filename)s:%(lineno)d] %(message)s', datefmt='%Y-%m-%d %H:%M:%S %z')
    names = [only] if only else [None, 'gunicorn.error', 'calibre']
    for name in names:
        for handler in logging.getLogger(name).handlers:
            handler.setLevel(level)
            handler.setFormatter(formatter)

class CalibreLogger(logging.Logger):
    #calibre定义的级别：0,1,2,3
    _calibre_level = {logging.DEBUG: 0, logging.INFO: 1, logging.WARNING: 2, logging.ERROR: 3}

    def __init__(self, name='calibre', level=logging.WARNING):
        super().__init__(name, level)
        self.orig_level = self.level
        self.propagate = False

    def debug(self, *args, **kwargs):
        msg = ' '.join([str(e) for e in args])
        if self.isEnabledFor(logging.DEBUG):
            self._log(logging.DEBUG, msg, (), **kwargs)
    def info(self, *args, **kwargs):
        msg = ' '.join([str(e) for e in args])
        if self.isEnabledFor(logging.INFO):
            self._log(logging.INFO, msg, (), **kwargs)
    __call__ = info

    def warning(self, *args, **kwargs):
        msg = ' '.join([str(e) for e in args])
        if self.isEnabledFor(logging.WARNING):
            self._log(logging.WARNING, msg, (), **kwargs)
    warn = warning
    
    def error(self, *args, **kwargs):
        msg = ' '.join([str(e) for e in args])
        if self.isEnabledFor(logging.ERROR):
            self._log(logging.ERROR, msg, (), **kwargs)

    def exception(self, *args, exc_info=True, **kwargs):
        msg = ' '.join([str(e) for e in args])
        if self.isEnabledFor(logging.ERROR):
            self._log(logging.ERROR, msg, (), **kwargs)

    def critical(self, *args, **kwargs):
        msg = ' '.join([str(e) for e in args])
        if self.isEnabledFor(logging.CRITICAL):
            self._log(logging.CRITICAL, msg, (), **kwargs)
    fatal = critical

    #底下的函数都是calibre新增的
    @property
    def filter_level(self):
        return self._calibre_level.get(self.level, 1)
    @filter_level.setter
    def filter_level(self, value):
        for level, clvl in self._calibre_level.items():
            if clvl == value:
                self.setLevel(level)
                break

    def __enter__(self):
        self.orig_level = self.level
        self.setLevel(logging.CRITICAL)

    def __exit__(self, *args):
        self.setLevel(self.orig_level)

    def flush(self):
        pass
    def close(self):
        pass
