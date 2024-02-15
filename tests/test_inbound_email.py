#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from test_base import *
from urllib.parse import quote
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formatdate
from email.encoders import encode_base64

class InboundEmailTestCase(BaseTestCase):
    login_required = 'admin'

    def setUp(self):
        super().setUp()
        KeUser.update(kindle_email='akindleear@gmail.com', send_mail_service={'service': 'local'}
            ).where(KeUser.name == self.login_required).execute()

    def test_ah_bounce(self):
        resp = self.client.post('/_ah/bounce', data={'from': ['a', 'b', 'c'], 'to': ['1@', '2@']})
        self.assertEqual(resp.status_code, 200)

    def test_ah_mail(self):
        data = {'sender': 'Bill <ms@us.com>', 'subject': 'teardown', 'text': 'is text body', 'files': None}
        resp = self.send('dl', data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Spam mail!', resp.text)

        WhiteList.create(mail='*', user='admin')
        resp = self.send('dl', data)
        self.assertEqual(resp.status_code, 200)
        
        data['text'] = "www.google.com"
        resp = self.send('dl', data)
        self.assertEqual(resp.status_code, 200)

        resp = self.send('trigger', data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('is triggered', resp.text)

        resp = self.send('book', data)
        self.assertEqual(resp.status_code, 200)

        resp = self.send('download', data)
        self.assertEqual(resp.status_code, 200)

        data['subject'] = 'Teardown!links'
        resp = self.send('download', data)
        self.assertEqual(resp.status_code, 200)

        data['subject'] = 'Teardown!article'
        resp = self.send('download', data)
        self.assertEqual(resp.status_code, 200)

        imgDir = os.path.join(appDir, 'application', 'images')
        data['files'] = [os.path.join(imgDir, 'cover0.jpg'), os.path.join(imgDir, 'cover1.jpg')]
        resp = self.send('d', data)
        self.assertEqual(resp.status_code, 200)

    def send(self, to, data):
        to = f'{to}@kindleear.appspotmail.com'
        data['to'] = to
        return self.client.post(f'/_ah/mail/{quote(to)}', data=self.build_mail(**data), content_type='multipart/alternative')

    def build_mail(self, sender, to, subject, text, files=None):
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = to
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject

        msg.attach(MIMEText(text))

        for f in (files or []):
            part = MIMEBase('application', "octet-stream")
            part.set_payload(open(f, 'rb').read())
            encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(f)}"')
            msg.attach(part)

        return msg.as_string()
        
