#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from test_base import *
from config import *

class LibraryOfficalTestCase(BaseTestCase):
    def test_shared(self):
        resp = self.client.get('/kindleearappspotlibrary')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json == [])

        query = {'key': 'kindleear.lucky!', 'data_type': 'latesttime'}
        resp = self.client.get('/kindleearappspotlibrary', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'ok', 'data': 0})

        now = str(datetime.datetime.utcnow().timestamp())
        AppInfo.create(name='lastSharedRssTime', value=now)
        resp = self.client.get('/kindleearappspotlibrary', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'ok', 'data': int(now.timestamp())})

        query = {'key': 'kindleear.lucky!', 'data_type': ''}
        resp = self.client.get('/kindleearappspotlibrary', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, [])

        SharedRss.create(title='title1', url='url', src='src', description='description', category='category', 
            language='lang', isfulltext=True, creator='creator', subscribed=1, created_time=now, 
            invalid_report_days=0, last_invalid_report_time=now, last_subscribed_time=now)

        resp = self.client.get('/kindleearappspotlibrary', query_string=query)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json[0]['t'], 'title1')
        
    def test_shared_post(self):
        data = {'key': 'kindleear', 'data_type': ''}
        resp = self.client.post('/kindleearappspotlibrary', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {})

        SharedRss.delete().execute()

        data = {'key': 'kindleear.lucky!', 'category': '', 'title': 'title1', 'url': '', 'lang': '',
            'isfulltext': '', 'creator': '', 'src': '', 'description': '', }
        resp = self.client.post('/kindleearappspotlibrary', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'The title or url or src is empty!')

        data['url'] = 'https://www.test.com/test.xml'
        resp = self.client.post('/kindleearappspotlibrary', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        dbItem = SharedRss.get_or_none()
        self.assertEqual(dbItem.url, 'https://www.test.com/test.xml')

        data['category'] = 'newcate'
        resp = self.client.post('/kindleearappspotlibrary', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        dbItem = SharedRss.get_or_none()
        self.assertEqual(dbItem.category, 'newcate')




        