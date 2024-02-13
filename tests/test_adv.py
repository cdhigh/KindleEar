#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from test_base import *
from config import *

class AdvTestCase(BaseTestCase):
    login_required = 'admin'

    def test_advdeliver(self):
        resp = self.client.get('/adv')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Deliver now', resp.text)

        resp = self.client.get('/adv/delivernow')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Deliver now', resp.text)

    def test_whitelist(self):
        resp = self.client.get('/adv/whitelist')
        if INBOUND_EMAIL_SERVICE == 'gae':
            self.assertEqual(resp.status_code, 200)
            self.assertTrue('White List' in resp.text)
        else:
            self.assertEqual(resp.status_code, 404)
            return

        resp = self.client.post('/adv/whitelist', data={'wlist': ''})
        self.assertEqual(resp.status_code, 302)

        resp = self.client.post('/adv/whitelist', data={'wlist': '*@gmail.com'})
        self.assertEqual(resp.status_code, 302)
        wl = WhiteList.get_or_none((WhiteList.mail == '@gmail.com') & (WhiteList.user == self.login_required))
        self.assertEqual(wl.mail, '@gmail.com')

        resp = self.client.post('/adv/whitelist', data={'wlist': 'ke@hotmail.com'})
        self.assertEqual(resp.status_code, 302)
        wl = WhiteList.get_or_none((WhiteList.mail == 'ke@hotmail.com') & (WhiteList.user == self.login_required))
        self.assertEqual(wl.mail, 'ke@hotmail.com')
        wl_id = wl.id

        resp = self.client.get('/advdel', query_string={'wlist_id': wl_id})
        self.assertEqual(resp.status_code, 302)
        wl = WhiteList.get_or_none((WhiteList.mail == 'ke@hotmail.com') & (WhiteList.user == self.login_required))
        self.assertEqual(wl, None)

    def test_advarchive(self):
        resp = self.client.get('/adv/archive')
        self.assertEqual(resp.status_code, 200)
        text = resp.text
        self.assertTrue(('Append hyperlink' in text) and ('to article' in text))

        data = {'evernote_mail': '', 'evernote': '', 'wiz_mail': '', 'wiz': '', 'pocket': '', 
            'access_token': '', 'instapaper': '', 'instapaper_username': '', 'instapaper_password': '', 
            'weibo': '', 'tencentweibo': '', 'browser': ''}
        resp = self.client.post('/adv/archive', data=data)
        self.assertEqual(resp.status_code, 302)

    def test_advimport(self):
        resp = self.client.get('/adv/import')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Import custom rss from an OPML file.', resp.text)

        xml = """<?xml version="1.0" encoding="utf-8" ?><opml version="2.0"><head><title>KindleEar.opml</title>
              <dateCreated>Wed, 14 Feb 2024 02:18:32 GMT+0000</dateCreated><dateModified>Wed, 14 Feb 2024 02:18:32 GMT+0000</dateModified>
              <ownerName>KindleEar</ownerName></head><body>
            <outline type="rss" text="bbc" xmlUrl="https%3A%2F%2Fwww.bbc.com/bbc.xml" isFulltext="True" />
            <outline type="rss" text="news" xmlUrl="www.news.com/news.xml" isFulltext="False" />
            </body></opml>"""

        data = {'import_file': (io.BytesIO(xml.encode('utf-8')), 'test.opml')}
        resp = self.client.post('/adv/import', data=data, follow_redirects=True, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        dbItem = Recipe.get_or_none((Recipe.user == 'admin') & (Recipe.url == 'https://www.bbc.com/bbc.xml'))
        self.assertEqual(dbItem.title, 'bbc')
        self.assertEqual(dbItem.isfulltext, True)
        dbItem = Recipe.get_or_none((Recipe.user == 'admin') & (Recipe.url == 'https://www.news.com/news.xml'))
        self.assertEqual(dbItem.title, 'news')
        self.assertEqual(dbItem.isfulltext, False)

        resp = self.client.get('/adv/export')
        self.assertEqual(resp.status_code, 200)
        content = resp.data
        self.assertIn(b'<ownerName>KindleEar</ownerName>', content)
        self.assertIn(b'https%3A%2F%2Fwww.news.com%2Fnews.xml', content)

    def test_advuploadcover(self):
        resp = self.client.get('/adv/cover')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Upload cover image', resp.text)

        with open(os.path.join(appDir, 'application', 'images', 'cover2.jpg'), 'rb') as f:
            cover_data = f.read()
        data = {'order': '', 'cover0': (io.BytesIO(cover_data), 'cover2.jpg')}
        resp = self.client.post('/adv/cover', data=data, content_type='multipart/form-data')
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
        resp = self.client.get('/adv/css')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Upload stylesheet', resp.text)

        with open(os.path.join(appDir, 'application', 'static', 'base.css'), 'rb') as f:
            css_data = f.read()
        data = {'css_file': (io.BytesIO(css_data), 'base.css')}
        resp = self.client.post('/adv/css', data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        blob = UserBlob.get_or_none((UserBlob.user == 'admin') & (UserBlob.name == 'css'))
        self.assertIsNotNone(blob)

        resp = self.client.post('/adv/css/delete', data={'action': 'delete'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        blob = UserBlob.get_or_none((UserBlob.user == 'admin') & (UserBlob.name == 'css'))
        self.assertIsNone(blob)


