#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import json, os, textwrap, time, zipfile
import xml.etree.ElementTree as ET

BUILTIN_CACHE_TYPE = 'builtin_cache'
BUILTIN_CACHE_USER = '__system__'
RECIPES_REPORT_BLOB_NAME = 'recipes_update_report'

def py3_repr(x):
    ans = repr(x)
    if isinstance(x, bytes) and not ans.startswith('b'):
        ans = 'b' + ans
    if isinstance(x, str) and ans.startswith('u'):
        ans = ans[1:]
    return ans

#根据输入的一些信息，自动创建一个recipe的源码
def GenerateRecipeSource(title, feeds, user, isfulltext=False, language=None, max_articles=30, 
    cover_url=None, base='BasicNewsRecipe'):
    className = f'UserRecipe{int(time.time())}'
    title = py3_repr(str(title).strip() or className)
    indent = ' ' * 8
    feedTitles = []
    feedsStr = []
    if feeds and isinstance(feeds[0], (tuple, list)):
        for t, url in feeds:
            feedsStr.append(f"{indent}({py3_repr(t)}, {py3_repr(url)}),")
            feedTitles.append(t)
    else:
        feedsStr = [f"{indent}{py3_repr(url)}," for url in feeds]
    
    feeds = 'feeds          = [\n{}\n    ]'.format('\n'.join(feedsStr)) if feedsStr else ''
    desc = 'News from {}'.format(', '.join(feedTitles)) if feedTitles else 'Deliver from KindleEar'
    desc = desc[:100].replace('"', "'")
    oldest_article = user.book_cfg('oldest_article')
    auto_cleanup = 'False' if isfulltext else 'True'
    use_embedded_content = 'True' if isfulltext else 'None'
    language = language or user.book_cfg('language')
    timefmt = user.book_cfg('time_fmt')
    if timefmt and (user.book_cfg('title_fmt') == 'title_[time]'):
        timefmt = f'[{timefmt}]'
    cover_url = f"'{cover_url}'" if isinstance(cover_url, str) else cover_url
    src = textwrap.dedent(f'''\
    #!/usr/bin/env python3
    # -*- coding:utf-8 -*-
    from calibre.web.feeds.news import {base}
    class {className}({base}):
        title          = {title}
        description    = "{desc}"
        language       = "{language}"
        max_articles_per_feed = {max_articles}
        oldest_article = {oldest_article}
        use_embedded_content  = {use_embedded_content}
        auto_cleanup          = {auto_cleanup}
        timefmt               = '{timefmt}'
        cover_url             = {cover_url}
        {feeds}''')
    #with open('d:/reci.py', 'w', encoding='utf-8') as f:
    #    f.write(src)
    return src

#能使用点号访问的字典
class DotDict(dict):
    #__setattr__ = dict.__setitem__
    #__getattr__ = dict.__getitem__
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
        tree = ET.parse(os.path.join(appDir, 'application', 'recipes', 'builtin_recipes.xml'))
        root = tree.getroot()
    except Exception as e:
        default_log.warning('Cannot open builtin_recipes.xml: {}'.format(e))
        return None

    id_ = id_ if id_.startswith('builtin:') else f'builtin:{id_}'
    info = None
    for child in root:
        if child.attrib.get('id', '') == id_:
            attrs = child.attrib.get
            subs = attrs('needs_subscription', 'no')
            subs = (subs in ('yes', 'optional'))
            info = {'id': id_, 'title': attrs('title', ''), 'author': attrs('author', ''), 'description': attrs('description'),
                'language': attrs('language', ''), 'needs_subscription': subs}
            break

    try:
        from application.back_end.db_models import Recipe
        cached = Recipe.select().where((Recipe.type_ == 'builtin_cache') & (Recipe.url == id_)).first()
        if cached:
            currentBuildId = GetBuiltinRecipesBuildId()
            cachedBuildId = (cached.custom or {}).get('build_id', '')
            if not currentBuildId or cachedBuildId == currentBuildId:
                if info is None:
                    info = {'id': id_, 'title': cached.title, 'author': 'Unknown',
                        'description': cached.description, 'language': cached.language,
                        'needs_subscription': bool(cached.needs_subscription)}
                else:
                    info['title'] = cached.title or info['title']
                    info['description'] = cached.description or info['description']
                    info['language'] = cached.language or info['language']
                    info['needs_subscription'] = bool(cached.needs_subscription)
    except Exception as e:
        default_log.warning('Read builtin recipe info cache for {} failed: {}'.format(id_, e))

    return DotDict(info) if info else None #方便上层使用点号访问

#返回内置Recipe包(builtin_recipes.xml/zip)的构建标识，用于判断重新部署后是否需要清理旧缓存
def GetBuiltinRecipesBuildId() -> str:
    xmlPath = os.path.join(appDir, 'application', 'recipes', 'builtin_recipes.xml')
    if os.path.exists(xmlPath):
        try:
            for event, elem in ET.iterparse(xmlPath, events=('start',)):
                built_at = elem.attrib.get('built_at', '') or elem.attrib.get('commit_sha', '')
                if built_at:
                    return built_at
                break
        except Exception as e:
            default_log.warning('Cannot read built_at from builtin_recipes.xml: {}'.format(e))
    zipPath = os.path.join(appDir, 'application', 'recipes', 'builtin_recipes.zip')
    if os.path.exists(zipPath):
        try:
            return str(int(os.path.getmtime(zipPath)))
        except Exception:
            pass
    return ''

#读写内置recipe更新报告（保存在UserBlob，避免AppInfo.value在MySQL/PG/Datastore下的长度限制）
def GetRecipesUpdateReport() -> dict:
    try:
        from application.back_end.db_models import UserBlob
        blob = UserBlob.get_or_none((UserBlob.user == BUILTIN_CACHE_USER) & (UserBlob.name == RECIPES_REPORT_BLOB_NAME))
        if blob and blob.data:
            raw = blob.data.decode('utf-8') if isinstance(blob.data, (bytes, bytearray)) else str(blob.data)
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
    except Exception as e:
        default_log.warning('GetRecipesUpdateReport failed: {}'.format(e))
    return {}

def SaveRecipesUpdateReport(report: dict):
    try:
        from application.back_end.db_models import UserBlob
        from application.ke_utils import utcnow
        blob = UserBlob.get_or_none((UserBlob.user == BUILTIN_CACHE_USER) & (UserBlob.name == RECIPES_REPORT_BLOB_NAME))
        if not report:
            if blob:
                blob.delete_instance()
            return
        payload = json.dumps(report, ensure_ascii=False).encode('utf-8')
        if blob:
            blob.data = payload
            blob.time = utcnow()
            blob.save()
        else:
            UserBlob.create(name=RECIPES_REPORT_BLOB_NAME, user=BUILTIN_CACHE_USER, data=payload)
    except Exception as e:
        default_log.warning('SaveRecipesUpdateReport failed: {}'.format(e))

#将指定builtin recipe的BookedRecipe.needs_subscription同步为当前生效的元数据值
def SyncBookedNeedsSubscription(canonical_ids):
    try:
        from application.back_end.db_models import BookedRecipe
        for cid in canonical_ids:
            info = GetBuiltinRecipeInfo(cid)
            if info:
                for booked in BookedRecipe.select().where(BookedRecipe.recipe_id == cid):
                    if bool(booked.needs_subscription) != bool(info.needs_subscription):
                        booked.needs_subscription = bool(info.needs_subscription)
                        booked.save()
    except Exception as e:
        default_log.warning('SyncBookedNeedsSubscription failed: {}'.format(e))

#若检测到重新部署（build_id变化），自动清理数据库中的内置recipe更新缓存
def ClearStaleBuiltinCache() -> bool:
    try:
        from application.back_end.db_models import AppInfo, Recipe
        currentBuildId = GetBuiltinRecipesBuildId()
        savedBuildId = AppInfo.get_value(AppInfo.builtinRecipesBuildId, '')
        if currentBuildId and currentBuildId != savedBuildId:
            cachedUrls = [r.url for r in Recipe.select().where(Recipe.type_ == BUILTIN_CACHE_TYPE)]
            Recipe.delete().where(Recipe.type_ == BUILTIN_CACHE_TYPE).execute()
            AppInfo.set_value(AppInfo.builtinRecipesBuildId, currentBuildId)
            AppInfo.set_value(AppInfo.lastRecipesCommitSha, '')
            AppInfo.set_value(AppInfo.lastRecipesUpdateTime, '')
            SaveRecipesUpdateReport({})
            if cachedUrls:
                SyncBookedNeedsSubscription(cachedUrls)
                default_log.info(f'Cleared {len(cachedUrls)} stale builtin recipe cache entries (build={currentBuildId}).')
            return True
    except Exception as e:
        default_log.warning('ClearStaleBuiltinCache failed: {}'.format(e))
    return False

#清理无人再订阅的内置recipe更新缓存；传入recipe_id时只检查该条，否则清理全部孤立缓存
def CleanupUnusedBuiltinCache(recipe_id: str = ''):
    try:
        from application.back_end.db_models import BookedRecipe, Recipe
        removedIds = set()
        if recipe_id:
            if not recipe_id.startswith('builtin:'):
                return
            if not BookedRecipe.select().where(BookedRecipe.recipe_id == recipe_id).first():
                Recipe.delete().where((Recipe.type_ == BUILTIN_CACHE_TYPE) & (Recipe.url == recipe_id)).execute()
                removedIds.add(recipe_id)
        else:
            subscribed = {b.recipe_id for b in BookedRecipe.select() if b.recipe_id and b.recipe_id.startswith('builtin:')}
            for cached in list(Recipe.select().where(Recipe.type_ == BUILTIN_CACHE_TYPE)):
                if cached.url not in subscribed:
                    removedIds.add(cached.url)
                    cached.delete_instance()

        if removedIds:
            report = GetRecipesUpdateReport()
            if report:
                removedNames = {rid[8:] for rid in removedIds if rid.startswith('builtin:')}
                changed = False
                for key in ('checked',):
                    oldList = report.get(key) or []
                    newList = [x for x in oldList if x not in removedIds]
                    if len(newList) != len(oldList):
                        report[key] = newList
                        changed = True
                for key in ('updated', 'unchanged'):
                    oldList = report.get(key) or []
                    newList = [x for x in oldList if x not in removedNames]
                    if len(newList) != len(oldList):
                        report[key] = newList
                        changed = True
                failedMap = report.get('failed_map') or {}
                if isinstance(failedMap, dict):
                    for name in list(failedMap.keys()):
                        if name in removedNames:
                            failedMap.pop(name, None)
                            changed = True
                    report['failed_map'] = failedMap
                    report['failed'] = [failedMap[k] for k in sorted(failedMap.keys())]
                if changed:
                    SaveRecipesUpdateReport(report)
    except Exception as e:
        default_log.warning('CleanupUnusedBuiltinCache failed: {}'.format(e))

#仅从内置zip读取Recipe源码
def GetBuiltinRecipeZipSource(id_: str):
    if not id_:
        return None

    id_ = id_[8:] if id_.startswith('builtin:') else id_
    filename = f'{id_}.recipe'
    recipesZip = os.path.join(appDir, 'application', 'recipes', 'builtin_recipes.zip')
    try:
        with zipfile.ZipFile(recipesZip, 'r') as zf:
            return zf.read(filename).decode('utf-8')
    except Exception as e:
        default_log.warning('Read {} failed: {}'.format(filename, str(e)))
        return None

#返回特定ID的内置Recipe源码字符串（优先使用数据库中的最新更新缓存）
def GetBuiltinRecipeSource(id_: str):
    if not id_:
        return None

    canonicalId = id_ if id_.startswith('builtin:') else f'builtin:{id_}'
    try:
        from application.back_end.db_models import Recipe
        cached = Recipe.select().where((Recipe.type_ == 'builtin_cache') & (Recipe.url == canonicalId)).first()
        if cached and cached.src:
            currentBuildId = GetBuiltinRecipesBuildId()
            cachedBuildId = (cached.custom or {}).get('build_id', '')
            if not currentBuildId or cachedBuildId == currentBuildId:
                return cached.src
            if not ClearStaleBuiltinCache():
                cached.delete_instance()
    except Exception as e:
        default_log.warning('Read builtin recipe cache for {} failed: {}'.format(canonicalId, e))

    return GetBuiltinRecipeZipSource(canonicalId)
