#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from test_base import *

class AdminTestCase(BaseTestCase):
    login_required = 'admin'

    def test_admin_page(self):
        resp = self.client.get('/admin')
        self.assertEqual(resp.status_code, 200)
        text = resp.text
        self.assertTrue(('Accounts' in text) and ('Add' in text))

    def test_add_account_and_delete(self):
        resp = self.client.get('/account/add')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Add account', resp.text)

        data = {'username': '', 'password1': '1', 'password2': '2', 'email': '1@1.com', 
            'sm_service': 'admin', 'expiration': 0}
        resp = self.client.post('/account/add', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Some parameters are missing or wrong.', resp.text)
        
        data['username'] = '/1>'
        resp = self.client.post('/account/add', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('The username includes unsafe chars.', resp.text)

        resp = self.client.post('/account/add', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('The two new passwords are dismatch.', resp.text)

        data['username'] = 'admin'
        data['password2'] = '1'
        resp = self.client.post('/account/add', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Already exist the username.', resp.text)

        data['username'] = '1'
        resp = self.client.post('/account/add', data=data)
        self.assertEqual(resp.status_code, 302)
        user = KeUser.get_or_none(KeUser.name == '1')
        self.assertEqual(user.email, '1@1.com')

        resp = self.client.post('/account/delete', data={'name': 'admin'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'You do not have sufficient privileges.'})

        resp = self.client.post('/account/delete', data={'name': '2'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': "The username '2' does not exist."})

        resp = self.client.post('/account/delete', data={'name': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'status': 'ok'})
        
    def test_change_admin_password(self):
        resp = self.client.get('/account/change/admin')
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Change Password", resp.text)

        data = {'username': '', 'orgpwd': '', 'password1': '1', 'password2': '2', 'email': '1@1'}
        resp = self.client.post('/account/change/admin', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("The username or password is empty.", resp.text)

        data['username'] = 'admin'
        data['orgpwd'] = 'admin1'
        resp = self.client.post('/account/change/admin', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("The old password is wrong.", resp.text)

        data['orgpwd'] = 'admin'
        resp = self.client.post('/account/change/admin', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("The two new passwords are dismatch.", resp.text)

        data['password2'] = '1'
        resp = self.client.post('/account/change/admin', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Change password success.", resp.text)
        
        data['orgpwd'] = '1'
        data['password1'] = 'admin'
        data['password2'] = 'admin'
        resp = self.client.post('/account/change/admin', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Change password success.", resp.text)

    def test_change_user_password(self):
        data = {'username': '2', 'password1': '2', 'password2': '2', 'email': '1@1.com', 
            'sm_service': 'admin', 'expiration': 12}
        resp = self.client.post('/account/add', data=data)
        self.assertEqual(resp.status_code, 302)

        resp = self.client.get('/account/change/2')
        self.assertEqual(resp.status_code, 200)
        self.assertIn("The password will not be changed if the fields are empties.", resp.text)

        resp = self.client.get('/account/change/4')
        self.assertEqual(resp.status_code, 200)
        self.assertIn("The username '4' does not exist.", resp.text)
        
        data['password1'] = '1'
        data['password2'] = '1'
        resp = self.client.post('/account/change/2', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Change success.", resp.text)

        data['username'] = '3'
        resp = self.client.post('/account/change/3', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("The username '3' does not exist.", resp.text)
        
        data['username'] = '2'
        data['password1'] = '1'
        resp = self.client.post('/account/change/2', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("The two new passwords are dismatch.", resp.text)

        data['password1'] = '2'
        data['password2'] = '2'
        data['expiration'] = 100
        resp = self.client.post('/account/change/2', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Change success.", resp.text)

        data['sm_service'] = 'independent'
        resp = self.client.post('/account/change/2', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Change success.", resp.text)
