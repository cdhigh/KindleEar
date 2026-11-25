#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import json
from unittest import mock
from test_base import *
from application.lib.recipe_helper import (
    BUILTIN_CACHE_TYPE,
    BUILTIN_CACHE_USER,
    ClearStaleBuiltinCache,
    GetBuiltinRecipesBuildId,
    GetBuiltinRecipeInfo,
    GetBuiltinRecipeSource,
    GetBuiltinRecipeZipSource,
    GetRecipesUpdateReport,
    SaveRecipesUpdateReport,
)
from application.lib.recipe_updater import UpdateSubscribedBuiltinRecipes

VALID_RECIPE_SRC = """#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from calibre.web.feeds.news import BasicNewsRecipe
class UpdatedTestNews(BasicNewsRecipe):
    title = 'Updated Test News'
    language = 'en'
    oldest_article = 7
    max_articles_per_feed = 10
    needs_subscription = True
    feeds = [('Test', 'https://example.com/rss')]
"""

INVALID_RECIPE_SRC = """#!/usr/bin/env python3
class BrokenRecipe(:
    pass
"""


class FakeResp:
    def __init__(self, status_code, text='', headers=None, json_data=None):
        self.status_code = status_code
        self.content = (json.dumps(json_data) if json_data is not None else text).encode('utf-8')
        self.headers = headers or {}
        self._json_data = json_data

    def json(self):
        return self._json_data if self._json_data is not None else json.loads(self.content.decode('utf-8'))


class RecipeUpdaterTestCase(BaseTestCase):
    login_required = 'admin'

    def setUp(self):
        super().setUp()
        Recipe.delete().where(Recipe.type_ == BUILTIN_CACHE_TYPE).execute()
        BookedRecipe.delete().execute()
        AppInfo.set_value(AppInfo.autoUpdateRecipes, '1')
        AppInfo.set_value(AppInfo.lastRecipesUpdateTime, '')
        AppInfo.set_value(AppInfo.lastRecipesCommitSha, '')
        SaveRecipesUpdateReport({})
        AppInfo.set_value(AppInfo.builtinRecipesBuildId, GetBuiltinRecipesBuildId())

    def tearDown(self):
        Recipe.delete().where(Recipe.type_ == BUILTIN_CACHE_TYPE).execute()
        BookedRecipe.delete().execute()
        SaveRecipesUpdateReport({})
        super().tearDown()

    def test_cache_lookup_and_redeploy_clear(self):
        zipSrc = GetBuiltinRecipeZipSource('builtin:nytimes')
        self.assertIsNotNone(zipSrc)
        self.assertEqual(GetBuiltinRecipeSource('builtin:nytimes'), zipSrc)

        buildId = GetBuiltinRecipesBuildId()
        Recipe.create(
            title='NYTimes Updated',
            url='builtin:nytimes',
            type_=BUILTIN_CACHE_TYPE,
            user=BUILTIN_CACHE_USER,
            needs_subscription=True,
            src=VALID_RECIPE_SRC,
            custom={'build_id': buildId, 'etag': '"v1"'},
        )
        self.assertEqual(GetBuiltinRecipeSource('builtin:nytimes'), VALID_RECIPE_SRC)
        self.assertTrue(GetBuiltinRecipeInfo('builtin:nytimes').needs_subscription)

        # Simulate redeploy: saved build id differs from current build id
        BookedRecipe.create(
            recipe_id='builtin:nytimes',
            separated=False,
            user='admin',
            title='NYTimes',
            description='',
            needs_subscription=True,
        )
        SaveRecipesUpdateReport({'failed': ['foo (HTTP 404)'], 'checked': ['builtin:nytimes']})
        AppInfo.set_value(AppInfo.lastRecipesUpdateTime, '2026-11-25 00:00:00')
        AppInfo.set_value(AppInfo.builtinRecipesBuildId, 'old_build_000')
        self.assertTrue(ClearStaleBuiltinCache())
        self.assertEqual(len(list(Recipe.select().where(Recipe.type_ == BUILTIN_CACHE_TYPE))), 0)
        self.assertEqual(GetBuiltinRecipeSource('builtin:nytimes'), zipSrc)
        self.assertEqual(GetRecipesUpdateReport(), {})
        self.assertEqual(AppInfo.get_value(AppInfo.lastRecipesUpdateTime), '')
        booked = BookedRecipe.select().where(BookedRecipe.recipe_id == 'builtin:nytimes').first()
        self.assertFalse(booked.needs_subscription)

    def test_stale_cache_ignored_on_direct_read(self):
        Recipe.create(
            title='NYTimes Stale',
            url='builtin:nytimes',
            type_=BUILTIN_CACHE_TYPE,
            user=BUILTIN_CACHE_USER,
            src=VALID_RECIPE_SRC,
            custom={'build_id': 'stale_build_xyz', 'etag': '"v0"'},
        )
        zipSrc = GetBuiltinRecipeZipSource('builtin:nytimes')
        self.assertEqual(GetBuiltinRecipeSource('builtin:nytimes'), zipSrc)
        self.assertEqual(len(list(Recipe.select().where(Recipe.type_ == BUILTIN_CACHE_TYPE))), 0)

    def test_update_subscribed_recipes_flow(self):
        BookedRecipe.create(
            recipe_id='builtin:nytimes',
            separated=False,
            user='admin',
            title='NYTimes',
            description='',
        )
        BookedRecipe.create(
            recipe_id='custom:999',
            separated=False,
            user='admin',
            title='Custom RSS',
            description='',
        )

        # 1. Disabled schedule skips unless force=True
        AppInfo.set_value(AppInfo.autoUpdateRecipes, '0')
        self.assertIn('disabled', UpdateSubscribedBuiltinRecipes(force=False).lower())

        # 2. First update downloads and caches valid recipe (API rate-limited -> ETag fallback)
        AppInfo.set_value(AppInfo.autoUpdateRecipes, '1')
        def side_effect_first(url, headers=None):
            if 'api.github.com' in url:
                return FakeResp(403)
            return FakeResp(200, VALID_RECIPE_SRC, {'ETag': '"etag-1"'})

        with mock.patch('application.lib.recipe_updater.UrlOpener.open', side_effect=side_effect_first) as m_open:
            msg = UpdateSubscribedBuiltinRecipes()
            self.assertIn('1 updated', msg)
            raw_calls = [c for c in m_open.call_args_list if 'raw.githubusercontent.com' in c[0][0]]
            self.assertEqual(len(raw_calls), 1)
            self.assertTrue(raw_calls[0][0][0].endswith('/nytimes.recipe'))

        report = GetRecipesUpdateReport()
        self.assertEqual(report['updated'], ['nytimes'])
        self.assertEqual(report['failed'], [])

        self.assertEqual(GetBuiltinRecipeSource('builtin:nytimes'), VALID_RECIPE_SRC)
        info = GetBuiltinRecipeInfo('builtin:nytimes')
        self.assertTrue(info.needs_subscription)
        booked = BookedRecipe.select().where(BookedRecipe.recipe_id == 'builtin:nytimes').first()
        self.assertTrue(booked.needs_subscription)

        # 3. Second update sends If-None-Match and handles 304
        def side_effect_304(url, headers=None):
            if 'api.github.com' in url:
                return FakeResp(403)
            return FakeResp(304)

        with mock.patch('application.lib.recipe_updater.UrlOpener.open', side_effect=side_effect_304) as m_open:
            msg = UpdateSubscribedBuiltinRecipes()
            self.assertIn('1 unchanged', msg)
            raw_calls = [c for c in m_open.call_args_list if 'raw.githubusercontent.com' in c[0][0]]
            self.assertEqual(raw_calls[0][1]['headers'], {'If-None-Match': '"etag-1"'})

        # 4. Invalid syntax from upstream is rejected, keeping previous valid cache
        def side_effect_invalid(url, headers=None):
            if 'api.github.com' in url:
                return FakeResp(403)
            return FakeResp(200, INVALID_RECIPE_SRC, {'ETag': '"etag-bad"'})

        with mock.patch('application.lib.recipe_updater.UrlOpener.open', side_effect=side_effect_invalid):
            msg = UpdateSubscribedBuiltinRecipes()
            self.assertIn('1 failed', msg)
        self.assertEqual(GetBuiltinRecipeSource('builtin:nytimes'), VALID_RECIPE_SRC)
        report = GetRecipesUpdateReport()
        self.assertEqual(len(report['failed']), 1)
        self.assertIn('nytimes', report['failed'][0])
        info = GetBuiltinRecipeInfo('builtin:nytimes')
        self.assertTrue(info.needs_subscription)
        booked = BookedRecipe.select().where(BookedRecipe.recipe_id == 'builtin:nytimes').first()
        self.assertTrue(booked.needs_subscription)

    def test_commit_sha_and_compare_api(self):
        BookedRecipe.create(
            recipe_id='builtin:nytimes',
            separated=False,
            user='admin',
            title='NYTimes',
            description='',
        )
        AppInfo.set_value(AppInfo.lastRecipesCommitSha, 'sha_old')
        SaveRecipesUpdateReport({'checked': ['builtin:nytimes']})

        # 1. Unchanged SHA & already checked -> 0 raw downloads
        def side_effect_same_sha(url, headers=None):
            if 'commits?' in url:
                return FakeResp(200, json_data=[{'sha': 'sha_old'}])
            raise AssertionError(f'Unexpected URL called: {url}')

        with mock.patch('application.lib.recipe_updater.UrlOpener.open', side_effect=side_effect_same_sha):
            msg = UpdateSubscribedBuiltinRecipes()
            self.assertIn('1 unchanged', msg)

        # 2. Changed SHA, but compare diff only touches another recipe -> 0 raw downloads
        def side_effect_other_file(url, headers=None):
            if 'commits?' in url:
                return FakeResp(200, json_data=[{'sha': 'sha_new_1'}])
            if 'compare/' in url:
                return FakeResp(200, json_data={'files': [{'filename': 'recipes/bbc.recipe', 'status': 'modified'}]})
            raise AssertionError(f'Unexpected URL called: {url}')

        with mock.patch('application.lib.recipe_updater.UrlOpener.open', side_effect=side_effect_other_file):
            msg = UpdateSubscribedBuiltinRecipes()
            self.assertIn('1 unchanged', msg)
        self.assertEqual(AppInfo.get_value(AppInfo.lastRecipesCommitSha), 'sha_new_1')

        # 3. Changed SHA and compare diff includes nytimes.recipe -> downloads and updates
        def side_effect_matching_file(url, headers=None):
            if 'commits?' in url:
                return FakeResp(200, json_data=[{'sha': 'sha_new_2'}])
            if 'compare/' in url:
                return FakeResp(200, json_data={'files': [{'filename': 'recipes/nytimes.recipe', 'status': 'modified'}]})
            return FakeResp(200, VALID_RECIPE_SRC, {'ETag': '"etag-sha2"'})

        with mock.patch('application.lib.recipe_updater.UrlOpener.open', side_effect=side_effect_matching_file):
            msg = UpdateSubscribedBuiltinRecipes()
            self.assertIn('1 updated', msg)
        self.assertEqual(AppInfo.get_value(AppInfo.lastRecipesCommitSha), 'sha_new_2')
        self.assertEqual(GetBuiltinRecipeSource('builtin:nytimes'), VALID_RECIPE_SRC)
        info = GetBuiltinRecipeInfo('builtin:nytimes')
        self.assertTrue(info.needs_subscription)
        booked = BookedRecipe.select().where(BookedRecipe.recipe_id == 'builtin:nytimes').first()
        self.assertTrue(booked.needs_subscription)

    def test_new_subscription_and_permanent_vs_transient_failure(self):
        BookedRecipe.create(recipe_id='builtin:nytimes', separated=False, user='admin', title='NYTimes', description='')
        BookedRecipe.create(recipe_id='builtin:deleted_feed', separated=False, user='admin', title='Deleted', description='')
        AppInfo.set_value(AppInfo.lastRecipesCommitSha, 'sha_1')
        SaveRecipesUpdateReport({'checked': ['builtin:nytimes']})

        # 1. Unchanged SHA, but builtin:deleted_feed is newly subscribed -> only deleted_feed is fetched;
        # permanent HTTP 404 still allows commit SHA to stay/advance
        def side_effect_new_sub(url, headers=None):
            if 'commits?' in url:
                return FakeResp(200, json_data=[{'sha': 'sha_1'}])
            if url.endswith('/deleted_feed.recipe'):
                return FakeResp(404)
            raise AssertionError(f'Unexpected URL called: {url}')

        with mock.patch('application.lib.recipe_updater.UrlOpener.open', side_effect=side_effect_new_sub):
            msg = UpdateSubscribedBuiltinRecipes(force=False)
            self.assertIn('1 unchanged, 1 failed', msg)
        self.assertEqual(AppInfo.get_value(AppInfo.lastRecipesCommitSha), 'sha_1')
        report = GetRecipesUpdateReport()
        self.assertIn('builtin:deleted_feed', report['checked'])
        self.assertEqual(report['failed'], ['deleted_feed (HTTP 404)'])

        # 2. Next scheduled run with same SHA skips permanent 404 without re-fetching, keeping failed report
        def side_effect_skip_404(url, headers=None):
            if 'commits?' in url:
                return FakeResp(200, json_data=[{'sha': 'sha_1'}])
            raise AssertionError(f'Unexpected URL called: {url}')

        with mock.patch('application.lib.recipe_updater.UrlOpener.open', side_effect=side_effect_skip_404):
            msg = UpdateSubscribedBuiltinRecipes(force=False)
            self.assertIn('1 unchanged, 1 failed', msg)

        # 3. Transient HTTP 500 blocks advancing commit SHA
        def side_effect_500(url, headers=None):
            if 'commits?' in url:
                return FakeResp(200, json_data=[{'sha': 'sha_2'}])
            if 'compare/' in url:
                return FakeResp(200, json_data={'files': [{'filename': 'recipes/nytimes.recipe', 'status': 'modified'}]})
            return FakeResp(500)

        with mock.patch('application.lib.recipe_updater.UrlOpener.open', side_effect=side_effect_500):
            msg = UpdateSubscribedBuiltinRecipes(force=False)
            self.assertIn('2 failed', msg)
        self.assertEqual(AppInfo.get_value(AppInfo.lastRecipesCommitSha), 'sha_1')

    def test_routes_auth_and_admin_settings(self):
        # Unauthenticated request without cron header/key is rejected
        self.client.get('/logout')
        resp = self.client.get('/recipes/update')
        self.assertEqual(resp.status_code, 403)

        # GAE cron header succeeds
        with mock.patch('application.lib.recipe_updater.UpdateSubscribedBuiltinRecipes',
                        return_value='Checked 0 builtin recipes.'):
            resp = self.client.get('/recipes/update', headers={'X-Appengine-Cron': 'true'})
            self.assertEqual(resp.status_code, 200)

        # Admin UI POST saves schedule
        self.client.post('/login', data={'username': 'admin', 'password': 'admin'})
        resp = self.client.post('/admin/recipes', data={'auto_update_recipes': '7', 'action': 'save'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(AppInfo.get_value(AppInfo.autoUpdateRecipes), '7')

        # Admin UI POST clear_cache deletes cached recipes and resets commit SHA
        Recipe.create(
            title='NYTimes Cached',
            url='builtin:nytimes',
            type_=BUILTIN_CACHE_TYPE,
            user=BUILTIN_CACHE_USER,
            needs_subscription=True,
            src=VALID_RECIPE_SRC,
            custom={'build_id': GetBuiltinRecipesBuildId(), 'etag': '"v1"'},
        )
        BookedRecipe.create(
            recipe_id='builtin:nytimes',
            separated=False,
            user='admin',
            title='NYTimes',
            description='',
            needs_subscription=True,
        )
        AppInfo.set_value(AppInfo.lastRecipesCommitSha, 'some_sha')
        resp = self.client.post('/admin/recipes', data={'auto_update_recipes': 'weekly', 'action': 'clear_cache'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(list(Recipe.select().where(Recipe.type_ == BUILTIN_CACHE_TYPE))), 0)
        self.assertEqual(AppInfo.get_value(AppInfo.lastRecipesCommitSha), '')
        booked = BookedRecipe.select().where(BookedRecipe.recipe_id == 'builtin:nytimes').first()
        self.assertFalse(booked.needs_subscription)

    def test_urlopener_submit_form_and_cookies(self):
        from application.lib.urlopener import UrlOpener
        opener = UrlOpener()
        opener.set_simple_cookie('ec_sub', 'true', '.economist.com')
        cookies = opener.cookies()
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0]['name'], 'ec_sub')
        self.assertEqual(cookies[0]['value'], 'true')

        html = '<html><body><form action="/login" method="POST"><input name="email"/><input name="password"/></form></body></html>'
        login_resp = FakeResp(200, html, {'Content-Type': 'text/html'})
        login_resp.url = 'https://example.com/login'
        login_resp.text = html
        login_resp.encoding = 'utf-8'
        done_resp = FakeResp(200, '<html>ok</html>')
        done_resp.url = 'https://example.com/home'
        done_resp.text = '<html>ok</html>'
        done_resp.encoding = 'utf-8'

        with mock.patch.object(opener, 'open_remote_url', side_effect=[login_resp, done_resp]) as m_req:
            res = opener.submit_form('https://example.com/login', {'email': 'a@b.com', 'password': 'pw'})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(m_req.call_count, 2)
            self.assertEqual(m_req.call_args_list[1][0][1], {'email': 'a@b.com', 'password': 'pw'})

    def test_unsubscribe_cleans_unused_cache(self):
        from application.view.subscribe import UnsubscribeRecipe
        Recipe.create(
            title='NYTimes Cached',
            url='builtin:nytimes',
            type_=BUILTIN_CACHE_TYPE,
            user=BUILTIN_CACHE_USER,
            needs_subscription=False,
            src=VALID_RECIPE_SRC,
            custom={'build_id': GetBuiltinRecipesBuildId(), 'etag': '"v1"'},
        )
        BookedRecipe.create(recipe_id='builtin:nytimes', separated=False, user='admin', title='NYTimes', description='')
        BookedRecipe.create(recipe_id='builtin:nytimes', separated=False, user='other_user', title='NYTimes', description='')

        adminUser = KeUser.get(KeUser.name == 'admin')
        info = GetBuiltinRecipeInfo('builtin:nytimes')

        # Unsubscribing admin still keeps cache because other_user is subscribed
        UnsubscribeRecipe(adminUser, 'builtin:nytimes', info)
        self.assertEqual(len(list(Recipe.select().where(Recipe.type_ == BUILTIN_CACHE_TYPE))), 1)

        # Removing the last subscriber cleans up the cache
        BookedRecipe.delete().where(BookedRecipe.user == 'other_user').execute()
        UnsubscribeRecipe(adminUser, 'builtin:nytimes', info)
        self.assertEqual(len(list(Recipe.select().where(Recipe.type_ == BUILTIN_CACHE_TYPE))), 0)
