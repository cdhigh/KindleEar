#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#MCP服务器端点的单元测试（全部离线，不访问外网；本地HTTP fixture仅绑定127.0.0.1）
from test_base import *
import os, json, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from application.back_end.db_models import KeUser, Recipe, BookedRecipe, DeliverLog

TEST_TOKEN = 'unittest' + 'x' * 25

RECIPE_SRC = """#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from calibre.web.feeds.news import BasicNewsRecipe
class UnitTestRecipe(BasicNewsRecipe):
    title = 'UnitTest Recipe'
    description = 'for mcp unittest'
    language = 'en'
    oldest_article = 7
    max_articles_per_feed = 5
    feeds = [(u'UnitTest', 'https://example.com/rss')]
"""

HOOK_SRC = """# -*- coding:utf-8 -*-
from calibre.web.feeds.news import MailNewsRecipe
class UnitTestHook(MailNewsRecipe):
    def preprocess_email(self, subject, txtBodies, htmlBodies, attachments):
        return '[Newsletter] ' + subject, txtBodies, htmlBodies, attachments
"""

def mcp_post(client, payload, token=TEST_TOKEN):
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    return client.post('/mcp', data=json.dumps(payload), headers=headers,
        content_type='application/json')

#==================== 本地HTTP fixture（供 test_recipe/fetch_page 真实调用路径离线测试） ====================
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

_FIXTURE_PAGES = {}

class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = _FIXTURE_PAGES.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode('utf-8'))
    def log_message(self, *args):
        pass

_fixture_server = None
def fixture_base():
    global _fixture_server
    if _fixture_server is None:
        longText = ('Lorem ipsum dolor sit amet, consectetur adipiscing elit. ' * 40)
        _FIXTURE_PAGES['/'] = ('<html><head><title>Fixture News</title></head><body>'
            '<nav>HOME | NEWS | ADS</nav><div class="list">'
            '<a href="/article1.html">Article One</a>'
            '<a href="/article2.html">Article Two</a></div></body></html>')
        for name in ('article1', 'article2'):
            _FIXTURE_PAGES[f'/{name}.html'] = ('<html><head><title>' + name + '</title></head><body>'
                '<nav>HOME | NEWS</nav>'
                '<div class="mc-article-body"><h1>Title of ' + name + '</h1>'
                '<p>' + longText + '</p>'
                '<p>Second paragraph with <a href="http://example.com">a link</a>.</p>'
                '<img src="/img.png"/><img data-src="/lazy.png"/>'
                '</div><footer>advertisement footer</footer></body></html>')
        _FIXTURE_PAGES['/img.png'] = (b'\x89PNG\r\n\x1a\n' + b'0' * 64)
        _fixture_server = ThreadingHTTPServer(('127.0.0.1', 0), _FixtureHandler)
        threading.Thread(target=_fixture_server.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{_fixture_server.server_port}'

def call_tool(client, name, arguments=None, id_=1):
    return mcp_post(client, {'jsonrpc': '2.0', 'id': id_, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments or {}}})

def tool_result(resp):
    return json.loads(resp.json['result']['content'][0]['text'])

class McpTestCase(BaseTestCase):
    login_required = 'admin'

    def setUp(self):
        super().setUp()
        user = KeUser.get_or_none(KeUser.name == self.login_required)
        user.set_custom('mcp_token', TEST_TOKEN)
        user.set_custom('mcp_readonly', False)
        user.set_custom('mcp_enabled', True)
        user.save()

    def tearDown(self):
        #清理本测试创建的数据
        user = KeUser.get_or_none(KeUser.name == self.login_required)
        if user:
            user.set_custom('mcp_token', '')
            user.set_custom('mcp_readonly', False)
            user.set_custom('mcp_enabled', '')
            user.save()
            for item in Recipe.get_all(Recipe.user == user.name):
                BookedRecipe.delete().where((BookedRecipe.user == user.name) &
                    (BookedRecipe.recipe_id == item.recipe_id)).execute()
                item.delete_instance()
        super().tearDown()

    def test_auth_required(self):
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
            'params': {'protocolVersion': '2025-06-18'}}, token=None)
        self.assertEqual(resp.status_code, 401)
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'},
            token='wrongtoken123')
        self.assertEqual(resp.status_code, 401)
        resp = self.client.get('/mcp')
        self.assertEqual(resp.status_code, 405)

    def test_initialize_handshake(self):
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
            'params': {'protocolVersion': '2025-06-18', 'capabilities': {},
                'clientInfo': {'name': 'unittest'}}})
        self.assertEqual(resp.status_code, 200)
        result = resp.json['result']
        self.assertEqual(result['protocolVersion'], '2025-06-18')
        self.assertEqual(result['serverInfo']['name'], 'kindleear')
        self.assertIn('tools', result['capabilities'])

        #notification无id，返回202空体
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.assertEqual(resp.status_code, 202)

    def test_parse_error(self):
        resp = self.client.post('/mcp', data='{invalid json',
            headers={'Authorization': 'Bearer ' + TEST_TOKEN}, content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json['error']['code'], -32700)

    def test_unknown_method(self):
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'no/such/method'})
        self.assertEqual(resp.json['error']['code'], -32601)

    def test_ping(self):
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})
        self.assertEqual(resp.json['result'], {})

    def test_tools_list(self):
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
        tools = resp.json['result']['tools']
        self.assertEqual(len(tools), 34)
        names = {t['name'] for t in tools}
        self.assertIn('test_recipe', names)
        self.assertIn('test_mail_hook', names)
        for tool in tools: #schema必须可被客户端识别
            self.assertEqual(tool['inputSchema']['type'], 'object')

    def test_tool_get_service_status(self):
        resp = call_tool(self.client, 'get_service_status')
        self.assertEqual(resp.status_code, 200)
        data = tool_result(resp)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['service'], 'KindleEar')

    def test_tool_list_subscriptions(self):
        resp = call_tool(self.client, 'list_subscriptions')
        data = tool_result(resp)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('subscriptions', data)

    def test_tool_validate_recipe(self):
        resp = call_tool(self.client, 'validate_recipe', {'src': RECIPE_SRC})
        data = tool_result(resp)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['title'], 'UnitTest Recipe')
        resp = call_tool(self.client, 'validate_recipe', {'src': 'this is not python {{'})
        data = tool_result(resp)
        self.assertEqual(data['status'], 'error')

    def test_tool_save_and_get_recipe(self):
        resp = call_tool(self.client, 'save_recipe',
            {'src': RECIPE_SRC, 'subscribe': True, 'separated': False})
        data = tool_result(resp)
        self.assertEqual(data['status'], 'ok', data)
        self.assertEqual(data['title'], 'UnitTest Recipe')
        recipeId = data['id']
        user = KeUser.get_or_none(KeUser.name == self.login_required)
        self.assertIsNotNone(user.get_booked_recipe(recipeId))

        #重复保存报错，overwrite后成功
        resp = call_tool(self.client, 'save_recipe', {'src': RECIPE_SRC})
        self.assertEqual(tool_result(resp)['status'], 'error')
        resp = call_tool(self.client, 'save_recipe', {'src': RECIPE_SRC, 'overwrite': True})
        self.assertEqual(tool_result(resp)['status'], 'ok')

        resp = call_tool(self.client, 'get_recipe_source', {'recipe_id': recipeId})
        data = tool_result(resp)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('class UnitTestRecipe', data['source'])

        #清理
        recipe = Recipe.get_or_none((Recipe.user == user.name) & (Recipe.title == 'UnitTest Recipe'))
        recipe.delete_instance()
        BookedRecipe.delete().where((BookedRecipe.user == user.name) &
            (BookedRecipe.recipe_id == recipeId)).execute()

    def test_tool_test_recipe_failed_articles(self):
        #全部文章下载失败：不得崩溃，返回部分结果（文章列表+失败清单+traceback）
        src = """from calibre.web.feeds.news import BasicNewsRecipe
class FailRecipe(BasicNewsRecipe):
    title = 'FailTest'
    description = 'offline failure test'
    language = 'en'
    timeout = 5
    def parse_index(self):
        return [('Fail', [
            {'title': 'a', 'url': 'http://127.0.0.1:9/a.html'},
            {'title': 'b', 'url': 'http://127.0.0.1:9/b.html'},
        ])]
"""
        resp = call_tool(self.client, 'test_recipe', {'src': src, 'max_articles': 2})
        data = tool_result(resp)
        self.assertEqual(data['status'], 'error')
        self.assertIn('No articles downloaded', data.get('traceback', ''))
        self.assertNotIn('orig_url', data.get('traceback', ''))
        self.assertEqual(len(data['feeds'][0]['articles']), 2)
        self.assertFalse(data['feeds'][0]['articles'][0]['downloaded'])
        self.assertEqual(len(data['failed_downloads']), 2)

    def test_tool_extract_article_preview_offline(self):
        #P0-1: 真实调用路径（file:// fixture → UrlOpener → readability三引擎）
        fixture_base()
        fd, path = tempfile.mkstemp(suffix='.html')
        os.close(fd)
        self.temp_files.append(path)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(_FIXTURE_PAGES['/article1.html'])
        resp = call_tool(self.client, 'extract_article_preview',
            {'url': 'file:///' + path.replace(os.sep, '/')})
        data = tool_result(resp)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('readability', data['engines'])
        self.assertNotIn('error', data['engines']['readability'])
        self.assertGreater(data['engines']['readability']['text_length'], 200)
        self.assertIn('justext', data['engines'])
        self.assertIn(data['selected'], ('readability', 'justext'))

    def test_tool_test_recipe_index_only(self):
        #P0-2: max_articles=0 只解析索引，不下载正文
        src = """from calibre.web.feeds.news import BasicNewsRecipe
class IndexRecipe(BasicNewsRecipe):
    title = 'IndexOnly'
    description = 'x'
    language = 'en'
    def parse_index(self):
        return [('Feed', [
            {'title': 'n1', 'url': 'http://127.0.0.1:9/n1.html'},
            {'title': 'n2', 'url': 'http://127.0.0.1:9/n2.html'},
            {'title': 'n3', 'url': 'http://127.0.0.1:9/n3.html'}])]
"""
        resp = call_tool(self.client, 'test_recipe', {'src': src, 'max_articles': 0})
        data = tool_result(resp)
        self.assertEqual(data['status'], 'ok', data.get('traceback'))
        self.assertTrue(data['index_only'])
        self.assertGreaterEqual(data['effective_timeout_seconds'], 5)
        self.assertEqual(data['feeds'][0]['article_count'], 3)
        articles = data['feeds'][0]['articles']
        self.assertEqual([a['title'] for a in articles], ['n1', 'n2', 'n3'])
        self.assertFalse(any(a['downloaded'] for a in articles))
        self.assertNotIn('content', articles[0])
        self.assertNotIn('preview', articles[0])

    def test_tool_test_recipe_content_control(self):
        #P0-3/P1-7: 默认预览+content_chars；include_content=true 全文；image_count
        base = fixture_base()
        src = f"""from calibre.web.feeds.news import BasicNewsRecipe
class HttpRecipe(BasicNewsRecipe):
    title = 'HttpTest'
    description = 'x'
    language = 'en'
    timeout = 15
    def parse_index(self):
        return [('Feed', [
            {{'title': 'A1', 'url': '{base}/article1.html'}},
            {{'title': 'A2', 'url': '{base}/article2.html'}}])]
"""
        resp = call_tool(self.client, 'test_recipe', {'src': src, 'max_articles': 2,
            'content_chars': 300})
        data = tool_result(resp)
        self.assertEqual(data['status'], 'ok', data.get('traceback'))
        arts = data['feeds'][0]['articles']
        self.assertTrue(arts[0]['downloaded'])
        self.assertIn('preview', arts[0])
        self.assertNotIn('content', arts[0])
        self.assertLessEqual(len(arts[0]['preview']), 300)
        self.assertEqual(arts[0]['image_count'], 0) #keep_images=False剥除img标签
        self.assertTrue(any('keep_images' in n for n in data.get('notes', [])))

        resp = call_tool(self.client, 'test_recipe', {'src': src, 'max_articles': 2,
            'include_content': True, 'download_images': True})
        data = tool_result(resp)
        self.assertEqual(data['status'], 'ok', data.get('traceback'))
        arts = data['feeds'][0]['articles']
        self.assertIn('content', arts[0])
        self.assertGreater(len(arts[0]['content']), 300)
        self.assertGreaterEqual(arts[0]['image_count'], 1)

    def test_clamp_timeout(self):
        #P0-4: 默认90，上限300
        from application.work.recipe_tester import clamp_timeout
        self.assertEqual(clamp_timeout(None), 90)
        self.assertEqual(clamp_timeout(300), 300)
        self.assertEqual(clamp_timeout(999), 300)
        self.assertEqual(clamp_timeout('abc'), 90)
        self.assertEqual(clamp_timeout(5), 5)

    def test_tool_fetch_page_selector_pagination(self):
        #P1-5: selector子树 + offset/max_chars分页（file://真实UrlOpener路径）
        fixture_base()
        fd, path = tempfile.mkstemp(suffix='.html')
        os.close(fd)
        self.temp_files.append(path)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(_FIXTURE_PAGES['/article1.html'])
        uri = 'file:///' + path.replace(os.sep, '/')
        resp = call_tool(self.client, 'fetch_page',
            {'url': uri, 'selector': 'div.mc-article-body', 'selector_format': 'text'})
        data = tool_result(resp)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['matched'], 1)
        self.assertIn('Title of article1', data['content'])
        self.assertNotIn('advertisement', data['content']) #选择器外的页脚不进入结果

        resp = call_tool(self.client, 'fetch_page',
            {'url': uri, 'format': 'text', 'offset': 0, 'max_chars': 200})
        data = tool_result(resp)
        self.assertGreater(data['total_chars'], 400)
        self.assertEqual(data['next_offset'], 200)
        resp = call_tool(self.client, 'fetch_page',
            {'url': uri, 'format': 'text', 'offset': 200, 'max_chars': 200})
        data2 = tool_result(resp)
        self.assertEqual(data2['offset'], 200)
        self.assertNotEqual(data2['content'], data['content'])

    def test_tool_get_task_status_shelf(self):
        #P1-6: 交付结果与书架互相印证
        #注意：handler经sys.path的flat模块(mcp_tools)执行，需同时patch两个导入路径
        import application.lib.mcp_tools as _pkgTools
        import mcp_tools as _flatTools
        fakeShelf = {'ShelfMatched Book': {'book_dir': '2026-10-30/001_globo', 'article_count': 20}}
        DeliverLog.create(user=self.login_required, to='a@b.c', size=1024,
            time_str='2026-10-30 10:00', book='ShelfMatched Book', status='ok')
        try:
            with mock.patch.object(_flatTools, '_shelf_lookup', return_value=fakeShelf), \
                    mock.patch.object(_pkgTools, '_shelf_lookup', return_value=fakeShelf):
                resp = call_tool(self.client, 'get_task_status', {'book': 'ShelfMatched'})
                data = tool_result(resp)
                entry = data['logs'][0]
                self.assertEqual(entry['shelf']['book_dir'], '2026-10-30/001_globo')
                self.assertEqual(entry['shelf']['article_count'], 20)
                self.assertEqual(entry['status_note'], 'Delivery succeeded.')
                self.assertIn('shelf_note', data)
        finally:
            DeliverLog.delete().where((DeliverLog.user == self.login_required) &
                (DeliverLog.book == 'ShelfMatched Book')).execute()

    def test_tool_test_delivery_shelf_note(self):
        #P1-6: test_delivery返回书架可见性说明
        with mock.patch('application.back_end.task_queue_adpt.create_delivery_task') as mocked:
            resp = call_tool(self.client, 'test_delivery', {'recipe_ids': ['upload:999']})
            data = tool_result(resp)
            self.assertEqual(data['status'], 'queued')
            self.assertIn('shelf_note', data)
            self.assertIn('list_shelf', data['shelf_note'])
            mocked.assert_called_once()

    def test_tool_get_service_status_deps(self):
        #P2-9: python/依赖版本/工具数量
        resp = call_tool(self.client, 'get_service_status')
        data = tool_result(resp)
        self.assertTrue(data['readability_ok'])
        self.assertGreaterEqual(data['mcp_tool_count'], 34)
        self.assertIn('python', data)
        self.assertIn('lxml', data['dependencies'])

    def test_error_response_shape(self):
        #P2-8: 工具异常统一 {status:error, error, traceback}
        resp = call_tool(self.client, 'read_mail', {'mail_id': '999999'})
        self.assertTrue(resp.json['result'].get('isError'))
        data = tool_result(resp)
        self.assertEqual(data['status'], 'error')
        self.assertIn('error', data)
        self.assertIn('traceback', data)

    def test_readonly_mode_blocks_write_tools(self):
        user = KeUser.get_or_none(KeUser.name == self.login_required)
        user.set_custom('mcp_readonly', True)
        user.save()
        resp = call_tool(self.client, 'push_url_to_kindle',
            {'urls': ['https://example.com/a'], 'title': 't'})
        result = resp.json['result']
        self.assertTrue(result.get('isError'))
        self.assertIn('read-only', result['content'][0]['text'].lower())
        #只读工具不受影响
        resp = call_tool(self.client, 'get_service_status')
        self.assertEqual(tool_result(resp)['status'], 'ok')

    def test_resources_and_prompts(self):
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'resources/list'})
        self.assertEqual(len(resp.json['result']['resources']), 4)
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 2, 'method': 'resources/read',
            'params': {'uri': 'kindlear://account'}})
        contents = resp.json['result']['contents']
        self.assertEqual(contents[0]['uri'], 'kindlear://account')
        self.assertIn('"username"', contents[0]['text'])

        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 3, 'method': 'prompts/list'})
        self.assertEqual(len(resp.json['result']['prompts']), 5)
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 4, 'method': 'prompts/get',
            'params': {'name': 'recipe_workflow', 'arguments': {'url': 'https://example.com'}}})
        text = resp.json['result']['messages'][0]['content']['text']
        self.assertIn('INDEX-ONLY', text)
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 4, 'method': 'prompts/get',
            'params': {'name': 'create_news_recipe', 'arguments': {'url': 'https://example.com'}}})
        text = resp.json['result']['messages'][0]['content']['text']
        self.assertIn('https://example.com', text)
        #未知prompt返回错误
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 5, 'method': 'prompts/get',
            'params': {'name': 'no_such_prompt'}})
        self.assertIn('error', resp.json)

    def test_tool_manage_whitelist(self):
        resp = call_tool(self.client, 'manage_whitelist', {'action': 'add', 'mail': 'News@Example.COM'})
        data = tool_result(resp)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['added'], 'news@example.com')
        resp = call_tool(self.client, 'manage_whitelist', {'action': 'list'})
        mails = [m['mail'] for m in tool_result(resp)['whitelist']]
        self.assertIn('news@example.com', mails)
        resp = call_tool(self.client, 'manage_whitelist', {'action': 'remove', 'mail': 'news@example.com'})
        self.assertEqual(tool_result(resp)['status'], 'ok')

    def test_tool_validate_mail_hook(self):
        resp = call_tool(self.client, 'validate_mail_hook', {'src': HOOK_SRC})
        data = tool_result(resp)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['class'], 'UnitTestHook')
        #非法代码：包含被禁止的import
        resp = call_tool(self.client, 'validate_mail_hook',
            {'src': 'import os\nfrom calibre.web.feeds.news import MailNewsRecipe\n'
                    'class BadHook(MailNewsRecipe):\n    pass\n'})
        self.assertEqual(tool_result(resp)['status'], 'error')

    def test_adv_mcp_page(self):
        #设置页不再包含MCP卡片，独立页面/advanced/mcp 承担配置
        resp = self.client.get('/settings')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('mcp_token', resp.text)

        resp = self.client.get('/advanced/mcp')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('MCP Server', resp.text)
        self.assertIn('/mcp', resp.text)

        resp = self.client.post('/advanced/mcp', data={'mcp_enabled': 'on', 'mcp_readonly': 'on'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Settings Saved!', resp.text)
        user = KeUser.get_or_none(KeUser.name == self.login_required)
        self.assertTrue(user.custom.get('mcp_readonly'))
        resp = call_tool(self.client, 'push_url_to_kindle',
            {'urls': ['https://example.com/a'], 'title': 't'})
        self.assertTrue(resp.json['result'].get('isError'))
        #恢复
        user.set_custom('mcp_readonly', False)
        user.save()

    def test_enable_switch(self):
        #全新用户未设置开关时默认停用：即使令牌有效也拒绝连接
        fresh = KeUser.create(name='mcpswitchtest', passwd_hash='x')
        fresh.set_custom('mcp_token', 'freshtoken000000000000000000000')
        fresh.save()
        try:
            resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'},
                token='freshtoken000000000000000000000')
            self.assertEqual(resp.status_code, 401)
            fresh.set_custom('mcp_enabled', True)
            fresh.save()
            resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'},
                token='freshtoken000000000000000000000')
            self.assertEqual(resp.status_code, 200)
        finally:
            fresh.delete_instance()

        #admin用户：页面上取消勾选后停用，令牌保留；重新打勾即恢复
        resp = self.client.post('/advanced/mcp', data={})
        self.assertEqual(resp.status_code, 200)
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})
        self.assertEqual(resp.status_code, 401)
        user = KeUser.get_or_none(KeUser.name == self.login_required)
        self.assertFalse(user.custom.get('mcp_enabled'))
        self.assertTrue(user.custom.get('mcp_token'))
        resp = self.client.post('/advanced/mcp', data={'mcp_enabled': 'on'})
        self.assertEqual(resp.status_code, 200)
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['result'], {})

    def test_token_ajax(self):
        #需要登录会话，BaseTestCase已完成登录
        resp = self.client.post('/mcp/token', data={})
        self.assertEqual(resp.status_code, 200)
        newToken = resp.json['token']
        self.assertEqual(resp.json['status'], 'ok')
        #旧token立即失效，新token生效（停用走"启用 MCP 服务器"开关，见test_enable_switch）
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, token=TEST_TOKEN)
        self.assertEqual(resp.status_code, 401)
        resp = mcp_post(self.client, {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, token=newToken)
        self.assertEqual(resp.status_code, 200)
        #恢复token供tearDown使用
        user = KeUser.get_or_none(KeUser.name == self.login_required)
        user.set_custom('mcp_token', TEST_TOKEN)
        user.save()
