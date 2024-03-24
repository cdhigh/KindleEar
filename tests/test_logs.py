#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from test_base import *
from config import *

class LogsTestCase(BaseTestCase):
    login_required = 'admin'

    def test_logs(self):
        resp = self.client.get('/logs')
        self.assertEqual(resp.status_code, 200)
        text = resp.text
        self.assertTrue(('There is no log' in text) or ('Only display last 10 logs' in text))

        data = {'user': 'admin', 'to': 'test@test.com', 'size': 1024, 'time_str': '2024-01-01',
            'datetime': datetime.datetime.utcnow(), 'book': 'test', 'status': 'ok'}
        DeliverLog.create(**data)
        DeliverLog.create(**data)
        DeliverLog.create(**data)

        resp = self.client.get('/logs')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Only display last 10 logs', resp.text)

        data['user'] = 'other'
        DeliverLog.create(**data)
        KeUser.create(name='other', passwd='pwd', email='1@2', sender='1@2')
        resp = self.client.get('/logs')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Logs of other users', resp.text)
        KeUser.delete().where(KeUser.name != 'admin').execute()

    def test_remove_logs(self):
        resp = self.client.get('/removelogs')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('lines delivery log removed.', resp.text)

        KeUser.create(name='other', passwd='pwd', email='1@1', sender='1@1', enable_send=True, expiration_days=7, 
                expires=datetime.datetime.utcnow() - datetime.timedelta(days=30))
        resp = self.client.get('/removelogs')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('lines delivery log removed.', resp.text)
        user = KeUser.get(KeUser.name == 'other')
        self.assertFalse(user.enable_send)
        KeUser.delete().where(KeUser.name != 'admin').execute()
