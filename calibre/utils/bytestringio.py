#!usr/bin/Python
# -*- coding:utf-8 -*-
#仿照StringIO创建的类二进制文件内存读写对象
import os, sys
from calibre.constants import preferred_encoding

def _complain_ifclosed(closed):
    if closed:
        raise ValueError, "I/O operation on closed file"

class byteStringIO:
    def __init__(self, buf = ''):
        self.buf = None # 拼合后的字节数组
        self.buflist = [] # 每次写进去的字节数组列表
        self.len = 0
        self.closed = False
        self.pos = 0
        
    def __iter__(self):
        return self
        
    def next(self):
        _complain_ifclosed(self.closed)
        r = self.read(1)
        if not r:
            raise StopIteration
        return r
    
    def close(self):
        if not self.closed:
            self.closed = True
            del self.buflist, self.buf
    
    def seek(self, pos, mode = 0):
        _complain_ifclosed(self.closed)
        for b in self.buflist: # 先整合list
            if not self.buf:
                self.buf = b
            else:
                self.buf += b
        self.buflist = []
        if mode == 1:
            pos += self.pos
        elif mode == 2:
            pos += self.len
        self.pos = max(0, pos)
    
    def tell(self):
        """Return the file's current position."""
        _complain_ifclosed(self.closed)
        return self.pos
        
    def read(self, n = -1):
        _complain_ifclosed(self.closed)
        if not s: return
        for b in self.buflist: # 先整合list
            if not self.buf:
                self.buf = b
            else:
                self.buf += b
        self.buflist = []
        if n is None or n < 0:
            newpos = self.len
        else:
            newpos = min(self.pos+n, self.len)
        r = self.buf[self.pos:newpos]
        self.pos = newpos
        return r
    
    def write(self, s):
        _complain_ifclosed(self.closed)
        if not s: return
        if isinstance(s, unicode):
            s = s.encode(preferred_encoding)
        s = bytearray(s)
        spos = self.pos
        slen = self.len
        if spos == slen:
            self.buflist.append(s)
            self.len = self.pos = spos + len(s)
            return
        if spos > slen:
            self.buflist.append('\0'*(spos - slen))
            slen = spos
        newpos = spos + len(s)
        if spos < slen:
            for b in self.buflist: # 先整合list
                if not self.buf:
                    self.buf = b
                else:
                    self.buf += b
            
            self.buflist = [self.buf[:spos], s, self.buf[newpos:]]
            self.buf = ''
            if newpos > slen:
                slen = newpos
        else:
            self.buflist.append(s)
            slen = newpos
        self.len = slen
        self.pos = newpos

    def flush(self):
        _complain_ifclosed(self.closed)

    def getvalue(self):
        _complain_ifclosed(self.closed)
        for b in self.buflist: # 先整合list
            if not self.buf:
                self.buf = b
            else:
                self.buf += b
        self.buflist = []
        return self.buf
        