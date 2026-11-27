#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from test_base import *
from config import *

class AdvTestCase(BaseTestCase):
    login_required = 'admin'

    def test_advdeliver(self):
        resp = self.client.get('/advanced')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Deliver now', resp.text)

        resp = self.client.get('/advanced/delivernow')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Deliver now', resp.text)

    def test_whitelist(self):
        resp = self.client.get('/advanced/inboundmail')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('White List' in resp.text)
        
        resp = self.client.post('/advanced/inboundmail', data={'wlist': ''})
        self.assertEqual(resp.status_code, 302)

        resp = self.client.post('/advanced/inboundmail', data={'wlist': '*@gmail.com'})
        self.assertEqual(resp.status_code, 302)
        wl = WhiteList.get_or_none((WhiteList.mail == '@gmail.com') & (WhiteList.user == self.login_required))
        self.assertEqual(wl.mail, '@gmail.com')

        resp = self.client.post('/advanced/inboundmail', data={'wlist': 'ke@hotmail.com'})
        self.assertEqual(resp.status_code, 302)
        wl = WhiteList.get_or_none((WhiteList.mail == 'ke@hotmail.com') & (WhiteList.user == self.login_required))
        self.assertEqual(wl.mail, 'ke@hotmail.com')
        wl_id = wl.id

        resp = self.client.get('/advanceddel', query_string={'wlist_id': wl_id})
        self.assertEqual(resp.status_code, 302)
        wl = WhiteList.get_or_none((WhiteList.mail == 'ke@hotmail.com') & (WhiteList.user == self.login_required))
        self.assertEqual(wl, None)

    def test_advarchive(self):
        resp = self.client.get('/advanced/archive')
        self.assertEqual(resp.status_code, 200)
        text = resp.text
        self.assertTrue(('Append hyperlink' in text) and ('to article' in text))

        data = {'evernote_mail': '', 'evernote': '', 'wiz_mail': '', 'wiz': '', 'pocket': '', 
            'access_token': '', 'instapaper': '', 'instapaper_username': '', 'instapaper_password': '', 
            'weibo': '', 'tencentweibo': '', 'browser': ''}
        resp = self.client.post('/advanced/archive', data=data)
        self.assertEqual(resp.status_code, 302)

    def test_advimport(self):
        resp = self.client.get('/advanced/import')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Import custom rss from an OPML file.', resp.text)

        xml = """<?xml version="1.0" encoding="utf-8" ?><opml version="2.0"><head><title>KindleEar.opml</title>
              <dateCreated>Wed, 14 Feb 2024 02:18:32 GMT+0000</dateCreated><dateModified>Wed, 14 Feb 2024 02:18:32 GMT+0000</dateModified>
              <ownerName>KindleEar</ownerName></head><body>
            <outline type="rss" text="bbc" xmlUrl="https://www.bbc.com/bbc.xml" isFulltext="True" />
            <outline type="rss" text="news" xmlUrl="www.news.com/news.xml" isFulltext="False" />
            </body></opml>"""

        data = {'import_file': (io.BytesIO(xml.encode('utf-8')), 'test.opml')}
        resp = self.client.post('/advanced/import', data=data, follow_redirects=True, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        dbItem = Recipe.get_or_none((Recipe.user == 'admin') & (Recipe.url == 'https://www.bbc.com/bbc.xml'))
        self.assertEqual(dbItem.title, 'bbc')
        self.assertEqual(dbItem.isfulltext, True)
        dbItem = Recipe.get_or_none((Recipe.user == 'admin') & (Recipe.url == 'https://www.news.com/news.xml'))
        self.assertEqual(dbItem.title, 'news')
        self.assertEqual(dbItem.isfulltext, False)

        resp = self.client.get('/advanced/export')
        self.assertEqual(resp.status_code, 200)
        content = resp.data
        self.assertIn(b'<ownerName>KindleEar</ownerName>', content)
        self.assertIn(b'https://www.news.com/news.xml', content)

    def test_advuploadcover(self):
        resp = self.client.get('/advanced/cover')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Upload cover image', resp.text)

        with open(os.path.join(appDir, 'application', 'images', 'cover2.jpg'), 'rb') as f:
            cover_data = f.read()
        data = {'order': '', 'cover0': (io.BytesIO(cover_data), 'cover2.jpg')}
        resp = self.client.post('/advanced/cover', data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        blob = UserBlob.get_or_none((UserBlob.user == 'admin') & (UserBlob.name == 'cover0'))
        self.assertIsNotNone(blob)
        dbId = resp.json['cover0']
        self.assertTrue(dbId.startswith('/dbimage/'))
        resp = self.client.get(dbId)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data[:3] == b'\xFF\xD8\xFF')

    def test_advuploadcss(self):
        resp = self.client.get('/advanced/css')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Upload stylesheet', resp.text)

        with open(os.path.join(appDir, 'application', 'static', 'base.css'), 'rb') as f:
            css_data = f.read()
        data = {'css_file': (io.BytesIO(css_data), 'base.css')}
        resp = self.client.post('/advanced/css', data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        blob = UserBlob.get_or_none((UserBlob.user == 'admin') & (UserBlob.name == 'css'))
        self.assertIsNotNone(blob)

        resp = self.client.post('/advanced/css/delete', data={'action': 'delete'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        blob = UserBlob.get_or_none((UserBlob.user == 'admin') & (UserBlob.name == 'css'))
        self.assertIsNone(blob)

    def test_calibre_options_rce_and_validation(self):
        from application.ke_utils import safe_eval, parse_calibre_options

        # safe_eval 与 parse_calibre_options 均不得执行任意代码（含 Issue #754 的 lambda 绕过 PoC）
        rce_payloads = [
            "(lambda: __import__('os').system('id'))()",
            "__import__('os').popen('id').read()",
            "[x for x in ().__class__.__base__.__subclasses__()]",
            "open('config.py').read()",
        ]
        with mock.patch('os.system') as mock_system:
            for payload in rce_payloads:
                with self.assertRaises((ValueError, SyntaxError)):
                    safe_eval(payload)
                with self.assertRaises((ValueError, SyntaxError)):
                    parse_calibre_options(payload)

                resp = self.client.post('/advanced/calibre', data={'options': payload})
                self.assertEqual(resp.status_code, 200)
                self.assertNotIn('Settings Saved!', resp.text)
            mock_system.assert_not_called()

        # 合法 JSON（包含字符串内 true/false/null 不应被正则误改）
        valid_json = '{"title": "A true story", "no_inline_toc": true, "base_font_size": 12}'
        resp = self.client.post('/advanced/calibre', data={'options': valid_json})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Settings Saved!', resp.text)
        admin = KeUser.get_or_none(KeUser.name == 'admin')
        self.assertEqual(admin.custom.get('calibre_options'), {
            'title': 'A true story',
            'no_inline_toc': True,
            'base_font_size': 12,
        })

        # 兼容 Python 字典字面量
        resp = self.client.post('/advanced/calibre', data={'options': "{'extra_css': 'p { color: black; }', 'no_inline_toc': False}"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Settings Saved!', resp.text)
        admin = KeUser.get_or_none(KeUser.name == 'admin')
        self.assertEqual(admin.custom.get('calibre_options'), {
            'extra_css': 'p { color: black; }',
            'no_inline_toc': False,
        })

        # 非字典 / 非字符串键 / 不可 JSON 序列化字面量应被拒绝
        for bad in ('[1, 2, 3]', '{1: "a"}', '{"a": {1, 2}}'):
            resp = self.client.post('/advanced/calibre', data={'options': bad})
            self.assertEqual(resp.status_code, 200)
            self.assertNotIn('Settings Saved!', resp.text)

        # 错误提示不应以未转义 HTML 渲染（防反射型 XSS）
        resp = self.client.post('/advanced/calibre', data={'options': '<script>alert(1)</script>'})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('<script>alert(1)</script>', resp.text)

        # 管理员权限放松：允许设置 debug_pipeline / log_level / verbose
        admin_opts = '{"debug_pipeline": "/tmp/ke_debug", "log_level": "DEBUG", "verbose": 1}'
        resp = self.client.post('/advanced/calibre', data={'options': admin_opts})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Settings Saved!', resp.text)
        admin = KeUser.get_or_none(KeUser.name == 'admin')
        self.assertEqual(admin.custom.get('calibre_options', {}).get('debug_pipeline'), '/tmp/ke_debug')

        # 恢复空设置
        resp = self.client.post('/advanced/calibre', data={'options': ''})
        self.assertEqual(resp.status_code, 200)
        admin = KeUser.get_or_none(KeUser.name == 'admin')
        self.assertEqual(admin.custom.get('calibre_options'), {})

    def test_calibre_options_non_admin_restrictions(self):
        from application.view.login import CreateAccountIfNotExist
        from application.lib.build_ebook import ke_opts, urls_to_book
        import zipfile, tempfile

        KeUser.delete().where(KeUser.name == 'calibre_user').execute()
        with self.app.app_context():
            CreateAccountIfNotExist('calibre_user', 'calibre_pass123', 'calibre@example.com', allow_recipe_upload=False)

        try:
            self.client.post('/login', data={'username': 'calibre_user', 'password': 'calibre_pass123'})

            # 普通用户允许设置常规排版选项（含纯文本 extra_css）
            resp = self.client.post('/advanced/calibre', data={'options': '{"extra_css": "p { text-indent: 2em; }", "no_inline_toc": true}'})
            self.assertEqual(resp.status_code, 200)
            self.assertIn('Settings Saved!', resp.text)

            # 普通用户禁止设置危险选项
            for key, val in [
                ('debug_pipeline', '/tmp/ke_debug'),
                ('extract_to', '/tmp/ke_extract'),
                ('allow_local_files_outside_root', True),
                ('read_metadata_from_opf', 'config.py'),
                ('cover', 'config.py'),
                ('log_level', 'DEBUG'),
                ('verbose', 2),
                ('user', 'admin'),
            ]:
                resp = self.client.post('/advanced/calibre', data={'options': json.dumps({key: val})})
                self.assertEqual(resp.status_code, 200)
                self.assertIn('Option not allowed', resp.text)
                self.assertNotIn('Settings Saved!', resp.text)

            # 运行时纵深防御：即使数据库残留危险键，ke_opts 也应过滤掉
            normal_user = KeUser.get_or_none(KeUser.name == 'calibre_user')
            normal_user.set_custom('calibre_options', {
                'debug_pipeline': '/tmp/should_strip',
                'extract_to': '/tmp/should_strip',
                'allow_local_files_outside_root': True,
                'log_level': 'DEBUG',
                'verbose': 2,
                'base_font_size': 11,
            })
            normal_user.save()
            resolved = ke_opts(normal_user)
            self.assertNotIn('debug_pipeline', resolved)
            self.assertNotIn('extract_to', resolved)
            self.assertNotIn('allow_local_files_outside_root', resolved)
            self.assertNotIn('verbose', resolved)
            self.assertEqual(resolved.get('base_font_size'), 11)
            self.assertEqual(resolved.get('user'), normal_user)

            # 普通用户将 extra_css 设为服务器本地文件路径时，不应读取该文件内容；管理员则允许
            with tempfile.NamedTemporaryFile('w', suffix='.css', delete=False, encoding='utf-8') as tf:
                tf.write('body { background-color: #123456; /* ke_local_css_marker */ }')
                css_file_path = tf.name
            self.temp_files.append(css_file_path)

            sample_html = '<html><body><p>Hello Calibre</p></body></html>'
            normal_user.set_custom('calibre_options', {'extra_css': css_file_path})
            normal_user.save()
            epub_bytes = urls_to_book([], 'Test', normal_user, mail_html=sample_html, output_fmt='epub')
            self.assertTrue(len(epub_bytes) > 0)
            with zipfile.ZipFile(io.BytesIO(epub_bytes)) as zf:
                combined = b''.join(zf.read(name) for name in zf.namelist())
            self.assertNotIn(b'#123456', combined)

            admin_user = KeUser.get_or_none(KeUser.name == 'admin')
            admin_user.set_custom('calibre_options', {'extra_css': css_file_path})
            admin_user.save()
            admin_epub = urls_to_book([], 'Test', admin_user, mail_html=sample_html, output_fmt='epub')
            self.assertTrue(len(admin_epub) > 0)
            with zipfile.ZipFile(io.BytesIO(admin_epub)) as zf:
                admin_combined = b''.join(zf.read(name) for name in zf.namelist())
            self.assertIn(b'#123456', admin_combined)
            admin_user.set_custom('calibre_options', {})
            admin_user.save()
        finally:
            KeUser.delete().where(KeUser.name == 'calibre_user').execute()
            self.client.post('/login', data={'username': 'admin', 'password': 'admin'})


