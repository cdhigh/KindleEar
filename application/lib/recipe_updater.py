#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#自动更新已订阅的内置Calibre Recipe，并将更新结果缓存到Recipe表(type_='builtin_cache')
import datetime
import os
from calibre.web.feeds.recipes import compile_recipe
from application.back_end.db_models import AppInfo, BookedRecipe, Recipe
from application.ke_utils import utcnow
from application.lib.recipe_helper import (
    BUILTIN_CACHE_TYPE,
    BUILTIN_CACHE_USER,
    CleanupUnusedBuiltinCache,
    ClearStaleBuiltinCache,
    GetBuiltinRecipesBuildId,
    GetBuiltinRecipeZipSource,
    GetRecipesUpdateReport,
    SaveRecipesUpdateReport,
)
from application.lib.urlopener import UrlOpener

DEFAULT_RAW_RECIPE_URL = 'https://raw.githubusercontent.com/kovidgoyal/calibre/master/recipes/{name}.recipe'
GITHUB_COMMITS_API_URL = 'https://api.github.com/repos/kovidgoyal/calibre/commits?path=recipes&per_page=1'
GITHUB_COMPARE_API_URL = 'https://api.github.com/repos/kovidgoyal/calibre/compare/{old_sha}...{new_sha}'


def _fetch_changed_recipe_names(opener: UrlOpener):
    """Return (changed_names_set_or_None, latest_sha).

    Returns (set(), sha) when recipes/ commit SHA is unchanged.
    Returns (None, sha_or_empty) when API fails/rate-limits/exceeds 300 files so caller falls back to ETag.
    """
    apiHeaders = {'Accept': 'application/vnd.github.v3+json'}
    try:
        resp = opener.open(GITHUB_COMMITS_API_URL, headers=apiHeaders)
        if resp.status_code != 200:
            return None, ''
        commits = resp.json()
        if not isinstance(commits, list) or not commits:
            return None, ''
        latestSha = commits[0].get('sha', '')
        if not latestSha:
            return None, ''
    except Exception as e:
        default_log.warning(f'Check calibre recipes commit SHA failed, falling back to ETag: {e}')
        return None, ''

    oldSha = AppInfo.get_value(AppInfo.lastRecipesCommitSha, '')
    if oldSha == latestSha:
        return set(), latestSha

    if oldSha:
        try:
            cmpUrl = GITHUB_COMPARE_API_URL.format(old_sha=oldSha, new_sha=latestSha)
            cmpResp = opener.open(cmpUrl, headers=apiHeaders)
            if cmpResp.status_code == 200:
                files = cmpResp.json().get('files', [])
                if isinstance(files, list) and len(files) < 300:
                    changed = {
                        os.path.basename(f['filename'])[:-7]
                        for f in files
                        if f.get('status') != 'removed'
                        and f.get('filename', '').startswith('recipes/')
                        and f.get('filename', '').endswith('.recipe')
                    }
                    return changed, latestSha
        except Exception as e:
            default_log.warning(f'Compare calibre recipes commits failed, falling back to ETag: {e}')

    return None, latestSha


def _should_skip_by_schedule(force: bool) -> str:
    if force:
        return ''
    mode = AppInfo.get_value(AppInfo.autoUpdateRecipes, '1').strip()
    days = int(mode) if mode.isdigit() else 1
    if days <= 0:
        return 'Auto update of builtin recipes is disabled.'
    if days > 1:
        lastStr = AppInfo.get_value(AppInfo.lastRecipesUpdateTime, '')
        if lastStr:
            try:
                lastDt = datetime.datetime.strptime(lastStr, '%Y-%m-%d %H:%M:%S')
                if (utcnow() - lastDt) < datetime.timedelta(hours=days * 24 - 12):
                    return f'Skipped builtin recipe update ({days}-day interval not reached).'
            except Exception:
                pass
    return ''


def _collect_subscribed_builtin_ids():
    ids = set()
    for item in BookedRecipe.select():
        rid = getattr(item, 'recipe_id', '') or ''
        if rid.startswith('builtin:'):
            ids.add(rid)
    return sorted(ids)


def _upsert_cached_recipe(canonical_id: str, src: str, recipe_cls, build_id: str, etag: str):
    name = canonical_id[8:] if canonical_id.startswith('builtin:') else canonical_id
    title = getattr(recipe_cls, 'title', '') or name
    if isinstance(title, bytes):
        title = title.decode('utf-8', 'replace')
    desc = getattr(recipe_cls, 'description', '') or ''
    if isinstance(desc, bytes):
        desc = desc.decode('utf-8', 'replace')
    lang = getattr(recipe_cls, 'language', '') or ''
    if isinstance(lang, bytes):
        lang = lang.decode('utf-8', 'replace')
    raw_ns = getattr(recipe_cls, 'needs_subscription', False)
    needs_sub = (raw_ns in (True, 'yes', 'optional')) if isinstance(raw_ns, (bool, str)) else bool(raw_ns)
    custom = {'build_id': build_id, 'etag': etag}

    existing = Recipe.select().where((Recipe.type_ == BUILTIN_CACHE_TYPE) & (Recipe.url == canonical_id)).first()
    if existing:
        existing.title = title
        existing.description = desc
        existing.language = lang
        existing.needs_subscription = needs_sub
        existing.src = src
        existing.time = utcnow()
        existing.custom = custom
        existing.save()
    else:
        Recipe.create(
            title=title,
            url=canonical_id,
            description=desc,
            isfulltext=False,
            type_=BUILTIN_CACHE_TYPE,
            needs_subscription=needs_sub,
            src=src,
            user=BUILTIN_CACHE_USER,
            language=lang,
            custom=custom,
        )

    #同步更新已订阅该recipe用户的BookedRecipe.needs_subscription，确保前端能显示账号密码输入框
    for booked in BookedRecipe.select().where(BookedRecipe.recipe_id == canonical_id):
        if bool(booked.needs_subscription) != needs_sub:
            booked.needs_subscription = needs_sub
            booked.save()


def UpdateSubscribedBuiltinRecipes(force: bool = False) -> str:
    """Fetch latest upstream .recipe files for subscribed builtin recipes and cache in DB."""
    ClearStaleBuiltinCache()
    CleanupUnusedBuiltinCache()

    skipMsg = _should_skip_by_schedule(force)
    if skipMsg:
        return skipMsg

    builtinIds = _collect_subscribed_builtin_ids()
    nowStr = utcnow().strftime('%Y-%m-%d %H:%M:%S')
    if not builtinIds:
        AppInfo.set_value(AppInfo.lastRecipesUpdateTime, nowStr)
        AppInfo.set_value(AppInfo.lastRecipesCommitSha, '')
        SaveRecipesUpdateReport({})
        return 'No builtin recipes subscribed.'

    customUrl = os.environ.get('CALIBRE_RECIPE_RAW_URL', '').strip()
    urlTpl = customUrl or DEFAULT_RAW_RECIPE_URL
    buildId = GetBuiltinRecipesBuildId()
    opener = UrlOpener(timeout=30)

    prevReport = GetRecipesUpdateReport()
    prevChecked = set(prevReport.get('checked') or [])
    prevFailedMap = prevReport.get('failed_map') or {}

    changedNames, latestSha = (None, '') if customUrl else _fetch_changed_recipe_names(opener)
    targetIds = []
    unchangedNames = []
    updatedNames = []
    failedMap = {}
    checkedIds = set()
    transientFailed = False

    if changedNames is not None:
        for rid in builtinIds:
            name = rid[8:]
            if (rid not in prevChecked) or (name in changedNames) or (force and name in prevFailedMap):
                targetIds.append(rid)
            else:
                checkedIds.add(rid)
                if name in prevFailedMap:
                    failedMap[name] = prevFailedMap[name]
                else:
                    unchangedNames.append(name)
    else:
        targetIds = list(builtinIds)

    for canonicalId in targetIds:
        name = canonicalId[8:]
        url = urlTpl.format(name=name)
        existing = Recipe.select().where((Recipe.type_ == BUILTIN_CACHE_TYPE) & (Recipe.url == canonicalId)).first()
        etag = (existing.custom or {}).get('etag', '') if existing else ''
        headers = {'If-None-Match': etag} if etag else None

        try:
            resp = opener.open(url, headers=headers)
        except Exception as e:
            default_log.warning(f'Fetch recipe {name} failed: {e}')
            failedMap[name] = f'{name} ({e})'
            transientFailed = True
            continue

        if resp.status_code == 304:
            checkedIds.add(canonicalId)
            unchangedNames.append(name)
            continue
        if resp.status_code != 200:
            default_log.warning(f'Fetch recipe {name} returned HTTP {resp.status_code}')
            failedMap[name] = f'{name} (HTTP {resp.status_code})'
            if resp.status_code >= 500 or resp.status_code in (408, 429):
                transientFailed = True
            else:
                checkedIds.add(canonicalId)
            continue

        newSrc = resp.content.decode('utf-8', 'replace')
        newEtag = resp.headers.get('ETag', '') or etag
        zipSrc = GetBuiltinRecipeZipSource(canonicalId)
        if zipSrc and newSrc == zipSrc:
            if existing:
                existing.delete_instance()
            checkedIds.add(canonicalId)
            unchangedNames.append(name)
            continue

        try:
            recipeCls = compile_recipe(newSrc)
        except Exception as e:
            default_log.warning(f'Compile updated recipe {name} failed, skipped: {e}')
            failedMap[name] = f'{name} (compile error: {e})'
            checkedIds.add(canonicalId)
            continue

        if recipeCls is None:
            default_log.warning(f'Compile updated recipe {name} returned None, skipped.')
            failedMap[name] = f'{name} (compile returned None)'
            checkedIds.add(canonicalId)
            continue

        _upsert_cached_recipe(canonicalId, newSrc, recipeCls, buildId, newEtag)
        checkedIds.add(canonicalId)
        updatedNames.append(name)

    if latestSha and not transientFailed:
        AppInfo.set_value(AppInfo.lastRecipesCommitSha, latestSha)
    failedDetails = [failedMap[k] for k in sorted(failedMap.keys())]
    AppInfo.set_value(AppInfo.lastRecipesUpdateTime, nowStr)
    SaveRecipesUpdateReport({
        'updated': updatedNames,
        'unchanged': unchangedNames,
        'failed': failedDetails,
        'failed_map': failedMap,
        'checked': sorted(checkedIds),
    })

    summary = f'Checked {len(builtinIds)} builtin recipes: {len(updatedNames)} updated, {len(unchangedNames)} unchanged, {len(failedDetails)} failed.'
    default_log.info(summary)
    return summary
