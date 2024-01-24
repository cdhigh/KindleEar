#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#简单的python代码高亮插件

import re
import sys
import keyword
import tokenize
import hashlib
TOKEN_TYPES = {getattr(tokenize, q): q for q in dir(tokenize) if q.upper() == q and isinstance(getattr(tokenize, q), int)}
BUILTIN_FUNCTIONS = [d for d in dir(__builtins__) if d[0]!="_" and d.islower()]
BUILTIN_EXCEPTIONS = [d for d in dir(__builtins__) if d[0]!="_" and d[0].isupper() and not d.isupper()]
BUILTIN_VARIABLES = [d for d in dir(__builtins__) if d[0]=="_" and len(d)>1]
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"><title>{title}</title>
<style>body {{background: rgb(29, 31, 33);font-size:1.2em}}</style>
</head>
<body><code>{code}</code></body>
</html>
"""


class Outputter(object):
    """docstring for Outputter"""
    def __init__(self):
        self.indentation = 0
        self.html = ""
        self.indentation_spaces = 4
        self.whitespace = "&nbsp;"
        self.linebreak = "<br>"
        self.escape_function = escape_html

    def get_c(self, text):
        h = int(hashlib.sha1(text.encode('utf-8')).hexdigest(), 16)
        s = sum([ord(q) for q in text])+hash(text)
        c = [0, 0, 0]
        ## VER1
        # c[h%2] = 200
        # c[s%2] += 50 + s % 100 + (h % 3)*50
        # return [min(q, 220) for q in c]
        ## VER2
        # c[h%3] = 255
        # if c[2]:
        #     c[1] += 100
        # if h%7<3:
        #     c[(s%3+bool(c[s%3])>100)%3] = 255
        for q in range(3):
            c[q] = int(155+(h%255)*(100.0/255))
            h/=255
        c[s%3] = 230
        return c

    def gen_t(self, text, color, size=None, raw_css=None):
        css = "color:rgb("+", ".join([str(q) for q in color])+");"
        if size:
            css += "font-size:"+str(size)+"em;"
        if raw_css:
            css += raw_css
        return "<span style=\"{}\">{}</span>".format(css, self.escape_function(text))
        
    def input(self, ttype, text, start, end, line):
        tt = TOKEN_TYPES[ttype]

        if self.html.endswith(self.linebreak) and tt not in ["INDENT", "DETENT"]:
            self.html += self.indentation*self.indentation_spaces*self.whitespace

        if tt == "COMMENT":
            self.html += self.gen_t(text, [160, 160, 160])
        elif tt == "STRING":
            self.html += self.gen_t(text, (181, 189, 104))
        elif tt == "NAME":
            if keyword.iskeyword(text) or text in ["self"]:
                self.html += self.gen_t(text, [255, 255, 255])
            elif text in BUILTIN_FUNCTIONS:
                self.html += self.gen_t(text, [150, 255, 150])
            elif text in BUILTIN_EXCEPTIONS:
                self.html += self.gen_t(text, [255, 150, 150])
            elif text in BUILTIN_VARIABLES:
                self.html += self.gen_t(text, [150, 150, 255])
            else:
                self.html += self.gen_t(text, self.get_c(text))
        elif tt == "OP":
            self.html += self.gen_t(text, [255, 255, 255])
        elif tt == "NUMBER":
            self.html += self.gen_t(text, [150, 100, 0])
        elif tt in ["NEWLINE", "NL"]:
            self.html += self.linebreak
        elif tt == "ENDMARKER":
            # self.html += "<hr>"
            pass
        elif tt == "INDENT":
            self.indentation += 1
        elif tt == "DEDENT":
            self.indentation -= 1
            self.html = self.html[:-(self.indentation_spaces*len(self.whitespace))]
        else:
            raise ValueError("Invalid token: {} {}".format(tt, repr(text)))

        if end[1] < len(line) and line[end[1]] == " ":
            self.html += self.whitespace

        # fix dedent whitespace (FIXME: dentented comments)
        self.html = re.sub(r"("+re.escape(self.whitespace)+r")+?"+re.escape(self.linebreak), self.linebreak, self.html)

def escape_html(html):
    for q in [("&", "amp"), ("<", "lt"), (">", "gt"), (" ", "nbsp")]:
        html = html.replace(q[0], "&"+q[1]+";")
    return html

def make_html(f, title="Untitled"):
    out = Outputter()
    for token in tokenize.generate_tokens(f.readline):
        out.input(*token)
    return HTML_TEMPLATE.format(title=escape_html(title), code=out.html)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        exit("Usage: python hl.py <file-to-hl>")
    with open(sys.argv[1], 'r', encoding='utf-8') as fo:
        result = make_html(fo, sys.argv[1])

    with open(sys.argv[1]+".html", "w", encoding='utf-8') as fo:
        fo.write(result)
