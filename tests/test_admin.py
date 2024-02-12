#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from test_base import *

class AdminTestCase(BaseTestCase):
    login_required = 'admin'

    def test_admin_page(self):
        resp = self.client.get('/admin')
        self.assertEqual(resp.status_code, 200)
        data = resp.text
        self.assertTrue(('Change Password' in data) and ('Add Account' in data))

    def test_change_admin_password_fail(self):
        resp = self.client.post('/admin', data={'actType': 'change', 'op': None, 'p1': '1', 'p2': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'The password includes non-ascii chars.'})

        resp = self.client.post('/admin', data={'actType': 'change', 'op': 'admin', 'p1': 'admin', 'p2': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'The username or password is empty.'})

        resp = self.client.post('/admin', data={'actType': 'change', 'op': 'ADMIN', 'p1': 'admin', 'p2': 'admin'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'The old password is wrong.'})

        resp = self.client.post('/admin', data={'actType': 'change', 'op': 'admin', 'p1': '1', 'p2': '2'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'The two new passwords are dismatch.'})

    def test_change_admin_password_success(self):
        resp = self.client.post('/admin', data={'actType': 'change', 'op': 'admin', 'p1': '1', 'p2': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'ok'})
        
        resp = self.client.post('/admin', data={'actType': 'change', 'op': '1', 'p1': 'admin', 'p2': 'admin'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'ok'})

    def test_add_account_and_delete(self):
        resp = self.client.post('/admin', data={'actType': 'add', 'new_username': '', 'new_u_pwd1': '1', 
            'new_u_pwd2': '1', 'new_u_expiration': 0})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'The username or password is empty.'})
        
        resp = self.client.post('/admin', data={'actType': 'add', 'new_username': '/1>', 'new_u_pwd1': 'admin', 
            'new_u_pwd2': 'admin', 'new_u_expiration': 0})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'The username includes unsafe chars.'})

        resp = self.client.post('/admin', data={'actType': 'add', 'new_username': '1', 'new_u_pwd1': '2', 
            'new_u_pwd2': '3', 'new_u_expiration': 0})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'The two new passwords are dismatch.'})

        resp = self.client.post('/admin', data={'actType': 'add', 'new_username': '1', 'new_u_pwd1': '2', 
            'new_u_pwd2': '2', 'new_u_expiration': 10})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'ok'})

        resp = self.client.post('/admin', data={'actType': 'add', 'new_username': '1', 'new_u_pwd1': '3', 
            'new_u_pwd2': '3', 'new_u_expiration': 0})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'Already exist the username.'})

        resp = self.client.post('/admin', data={'actType': 'delete', 'name': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': "ok"})

    def test_del_account_fail(self):
        resp = self.client.post('/admin', data={'actType': 'delete', 'name': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'The username is empty or you dont have right to delete it.'})

        resp = self.client.post('/admin', data={'actType': 'delete', 'name': 'notexist'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': "The username 'notexist' does not exist."})

    
    def test_change_user_password(self):
        resp = self.client.post('/admin', data={'actType': 'add', 'new_username': '1', 'new_u_pwd1': '2', 
            'new_u_pwd2': '2', 'new_u_expiration': 0})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'ok'})

        resp = self.client.get('/mgrpwd/notexist')
        self.assertEqual(resp.status_code, 200)
        self.assertIn("The username 'notexist' does not exist.", resp.text)

        resp = self.client.get('/mgrpwd/1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Please input new password to confirm.", resp.text)

        resp = self.client.post('/mgrpwd/10', data={'p1': '1', 'p2': '1', 'ep': '200'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("The username '10' does not exist.", resp.text)
        
        resp = self.client.post('/mgrpwd/1', data={'p1': '1', 'p2': '12', 'ep': '200'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("The two new passwords are dismatch.", resp.text)
        
        resp = self.client.post('/mgrpwd/1', data={'p1': '12', 'p2': '12', 'ep': '200'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Change password success.", resp.text)

        resp = self.client.post('/mgrpwd/1', data={'p1': '12', 'p2': '12', 'ep': '0'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Change password success.", resp.text)
        
