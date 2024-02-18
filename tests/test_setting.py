#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from test_base import *
from flask import session
from application.view.setting import get_locale

class SettingTestCase(BaseTestCase):
    login_required = 'admin'

    def test_setting_page(self):
        resp = self.client.get('/setting')
        self.assertEqual(resp.status_code, 200)
        data = resp.text
        self.assertTrue(('Base' in data) and ('Oldest article' in data))

    def test_set_post(self):
        data = {'kindle_email': '', 'rss_title': '', 'sm_service': 'sendgrid', 'sm_apikey': '', 'sm_host': '',
            'sm_port': '', 'sm_username': '', 'sm_password': '', 'sm_save_path': '', 
            'enable_send': 'all', 'timezone': 8, 'send_time': 7, 'book_type': 'epub', 'device_type': 'kindle',
            'title_fmt': '', 'Monday': 1, 'book_mode': '', 'remove_hyperlinks': 'all', 'author_format': '',
            'book_language': 'zh', 'oldest': 7, 'time_fmt': ''
            }
        resp = self.client.post('/setting', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Kindle E-mail is requied!', resp.text)

        data['kindle_email'] = 'test@gmail.com'
        resp = self.client.post('/setting', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Title is requied!', resp.text)

        data['rss_title'] = 'Test'
        resp = self.client.post('/setting', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Some parameters are missing or wrong.', resp.text)

        data['sm_apikey'] = 'dfhkfdslajjflds'
        resp = self.client.post('/setting', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Settings Saved!', resp.text)

        data['enable_send'] = 'recipes'
        resp = self.client.post('/setting', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Settings Saved!', resp.text)

        data['enable_send'] = ''
        resp = self.client.post('/setting', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Settings Saved!', resp.text)

    def test_set_locale(self):
        with self.client:
            resp = self.client.get('/setlocale/zh')
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(session['langCode'], 'zh')
            self.assertEqual(get_locale(), 'zh')

            resp = self.client.get('/setlocale/unknown')
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(session['langCode'], 'en')
            self.assertEqual(get_locale(), 'en')