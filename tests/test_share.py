#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from test_base import *
from config import *

class ShareTestCase(BaseTestCase):
    login_required = 'admin'

    def setUp(self):
        super().setUp()
        self.shareLinks = {'key': 'testkey', 'Evernote': {'enable': '1', 'email': ''},
            'Wiz': {'enable': '1', 'email': ''}, 'Pocket': {'enable': 1, 'access_token': ''},
            'Instapaper': {'enable': '1', 'username': '', 'password': ''}}
        KeUser.update(kindle_email='akindleear@gmail.com', send_mail_service={'service': 'local'},
            share_links=self.shareLinks
            ).where(KeUser.name == self.login_required).execute()

    def test_share(self):
        resp = self.client.get('/share')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Some parameters are missing or wrong.', resp.text)

        query = {'act': 'Wiz', 'u': 'admin', 'url': 'test.com', 't': 'test', 'k': 'invalid'}
        resp = self.client.get('/share', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('The username does not exist or the email is empty.', resp.text)

        query['k'] = 'testkey'
        query['act'] = 'invalid'
        resp = self.client.get('/share', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Unknown command:', resp.text)

    def test_evernote_wiz(self):
        query = {'act': 'Evernote', 'u': 'admin', 'url': 'http://test1.com', 't': 'test', 'k': 'testkey'}
        resp = self.client.get('/share', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('There is no Evernote email yet.', resp.text)

        self.shareLinks['Evernote']['email'] = 'test@test.com'
        KeUser.update(share_links=self.shareLinks).where(KeUser.name == self.login_required).execute()
        resp = self.client.get('/share', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Failed save to', resp.text)

        query['url'] = 'www.google.com'
        resp = self.client.get('/share', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Saved to your', resp.text)

        query['act'] = 'Wiz'
        resp = self.client.get('/share', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Saved to your', resp.text)

    def test_pocket(self):
        query = {'act': 'Pocket', 'u': 'admin', 'url': 'https://www.google.com', 't': 'test', 'k': 'testkey'}
        resp = self.client.get('/share', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Unauthorized', resp.text)

        self.shareLinks['Pocket']['access_token'] = 'test'
        KeUser.update(share_links=self.shareLinks).where(KeUser.name == self.login_required).execute()
        resp = self.client.get('/share', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Failed save to', resp.text)

    def test_instapaper(self):
        query = {'act': 'Instapaper', 'u': 'admin', 'url': 'https://www.google.com', 't': 'test', 'k': 'testkey'}
        resp = self.client.get('/share', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('The username or password is empty.', resp.text)

        self.shareLinks['Instapaper']['username'] = 'test'
        self.shareLinks['Instapaper']['password'] = 'test'
        KeUser.update(share_links=self.shareLinks).where(KeUser.name == self.login_required).execute()
        resp = self.client.get('/share', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('The username does not exist or password is wrong.', resp.text)

