#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import os, re, textwrap, time
import xml.etree.ElementTree as ET

def py3_repr(x):
    ans = repr(x)
    if isinstance(x, bytes) and not ans.startswith('b'):
        ans = 'b' + ans
    if isinstance(x, str) and ans.startswith('u'):
        ans = ans[1:]
    return ans


def GenerateRecipeSource(title, feeds, user, max_articles=30, isfulltext=False):
    classname = 'BasicUserRecipe%d' % int(time.time())
    title = str(title).strip() or classname
    indent = ' ' * 8
    feedTitles = []
    feedsStr = []
    if feeds:
        if len(feeds[0]) > 1:
            for title, url in feeds:
                feedsStr.append(f'{indent}({py3_repr(title)}, {py3_repr(url)}),')
                feedTitles.append(title)
        else:
            feedsStr = [f'{indent}{py3_repr(url)},' for url in feeds]
    
    feeds = 'feeds          = [\n{}\n    ]'.format('\n'.join(feedsStr)) if feedsStr else ''
    desc = 'News from {}'.format(', '.join(feedTitles)) if feedTitles else 'Deliver from KindleEar'
        
    isfulltext = 'True' if isfulltext else 'None'
    src = textwrap.dedent('''\
    #!/usr/bin/env python3
    # vim:fileencoding=utf-8
    from calibre.web.feeds.news import {base}
    class {classname}({base}):
        title          = {title}
        description    = '{desc}'
        language       = '{language}'
        oldest_article = {oldest_article}
        max_articles_per_feed = {max_articles_per_feed}
        use_embedded_content  = {isfulltext}
        timefmt               = '{timefmt}'
        auto_cleanup   = True
        {feeds}''').format(
            classname=classname, title=py3_repr(title), desc=desc, oldest_article=user.oldest_article, feeds=feeds,
            max_articles_per_feed=max_articles_per_feed, base='AutomaticNewsRecipe',
            isfulltext=isfulltext, language=user.book_language, timefmt=user.time_fmt)
    return src

#能使用点号访问的字典
class DotDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getattr__(self, key):
        try:
            return self[key]
        except:
            return None
        #if isinstance(value, dict):
        #    value = DotDict(value)
        #return value

#根据ID查询内置Recipe基本信息，返回一个字典
#{title:, author:, language:, needs_subscription:, description:, id:}
def GetBuiltinRecipeInfo(id_: str):
    if not id_:
        return None

    try:
        tree = ET.parse(os.path.join(appDir, 'books/builtin_recipes.xml'))
        root = tree.getroot()
    except:
        return None

    id_ = id_ if id_.startswith('builtin:') else f'builtin:{id_}'
    for child in root:
        attrs = child.attrib
        if attrs.get('id', '') == id_:
            return DotDict(attrs) #方便上层使用点号访问
    return None

#返回特定ID的内置Recipe源码字符串
def GetBuiltinRecipeSource(id_: str):
    if not id_:
        return None

    id_ = id_[8:] if id_.startswith('builtin:') else id_
    filename = f'{id_}.recipe'
    try:
        with zipfile.ZipFile(os.path.join(appDir, 'books', 'builtin_recipes.zip'), 'r') as zf:
            return zf.read(filename).decode('utf-8')
    except Exception as e:
        default_log.warning('Read {} failed: {}'.format(filename, str(e)))
        return None
