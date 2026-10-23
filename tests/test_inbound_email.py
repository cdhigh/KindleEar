#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import io
from test_base import *
from urllib.parse import quote
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formatdate
from email.encoders import encode_base64
from bs4 import BeautifulSoup

#根据参数构建一个简单的邮件字符串
def build_mail_message(sender, to, subject, text, files=None):
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

class InboundEmailTestCase(BaseTestCase):
    login_required = 'admin'

    def setUp(self):
        super().setUp()
        user = KeUser.get_or_none(KeUser.name == self.login_required)
        user.set_cfg('kindle_email', 'akindleear@gmail.com')
        user.send_mail_service = {'service': 'local'}
        user.save()

    #GAE的收信和退信接口只有部署在GAE上才能测试
    def test_ah_bounce(self):
        from application.view.inbound_email import gae_mail
        if not gae_mail:
            self.skipTest('google.appengine is not available.')
        resp = self.client.post('/_ah/bounce', data={'from': ['a', 'b', 'c'], 'to': ['1@', '2@']})
        self.assertEqual(resp.status_code, 200)

    def test_ah_mail(self):
        from application.view.inbound_email import gae_mail
        mTypes = ('gae', 'general') if gae_mail else ('general',)
        for mType in mTypes:
            WhiteList.delete().execute()
            data = {'sender': 'Bill <ms@us.com>', 'subject': 'teardown', 'text': 'is text body', 'files': None}
            resp = self.send('dl', data, mType)
            self.assertEqual(resp.status_code, 200)
            self.assertIn('Spam mail', resp.text)

            WhiteList.create(mail='*', user='admin')
            resp = self.send('dl', data, mType)
            self.assertEqual(resp.status_code, 200)
            
            data['text'] = "www.google.com"
            resp = self.send('dl', data, mType)
            self.assertEqual(resp.status_code, 200)

            resp = self.send('trigger', data, mType)
            self.assertEqual(resp.status_code, 200)
            self.assertIn('is triggered', resp.text)

            resp = self.send('book', data, mType)
            self.assertEqual(resp.status_code, 200)

            resp = self.send('download', data, mType)
            self.assertEqual(resp.status_code, 200)

            data['subject'] = 'Teardown!links'
            resp = self.send('download', data, mType)
            self.assertEqual(resp.status_code, 200)

            data['subject'] = 'Teardown!article'
            resp = self.send('download', data, mType)
            self.assertEqual(resp.status_code, 200)

            imgDir = os.path.join(appDir, 'application', 'images')
            data['files'] = [os.path.join(imgDir, 'cover0.jpg'), os.path.join(imgDir, 'cover1.jpg')]
            resp = self.send('d', data, mType)
            self.assertEqual(resp.status_code, 200)

    def send(self, to, data, mType):
        to = f'{to}@kindleear.appspotmail.com'
        data['to'] = to
        url = f'/_ah/mail/{quote(to)}' if mType == 'gae' else '/mail'
        return self.client.post(url, data=build_mail_message(**data).encode('utf-8'), content_type='multipart/alternative')

    def build_mail(self, sender, to, subject, text, files=None):
        return build_mail_message(sender, to, subject, text, files)


HOOK_SRC_BOTH = '''
from calibre.web.feeds.news import MailNewsRecipe

class MyMailHook(MailNewsRecipe):
    def preprocess_email(self, subject, txtBodies, htmlBodies, attachments):
        subject = '[hooked] ' + subject
        return subject, txtBodies, htmlBodies, attachments

    def preprocess_soup(self, soup, attachments):
        tag = soup.new_tag('p')
        tag.string = 'content-hook-marker'
        soup.body.append(tag)
        return soup, attachments
'''

class MailHookTestCase(BaseTestCase):
    login_required = 'admin'

    def setUp(self):
        super().setUp()
        user = KeUser.get_or_none(KeUser.name == self.login_required)
        user.set_cfg('kindle_email', 'akindleear@gmail.com')
        user.send_mail_service = {'service': 'local'}
        user.save()
        InBox.delete().execute()
        UserBlob.delete().execute()
        WhiteList.delete().execute()

    #钩子源码的编译检查
    def test_compile_mail_hook(self):
        from application.mail_hook import compile_mail_hook
        from calibre.web.feeds.news import MailNewsRecipe

        hook_cls = compile_mail_hook(HOOK_SRC_BOTH)
        self.assertTrue(issubclass(hook_cls, MailNewsRecipe))

        #只重写 extract_urls 也可以
        src = '''from calibre.web.feeds.news import MailNewsRecipe
class SimpleHook(MailNewsRecipe):
    def extract_urls(self, soup):
        return ['http://example.com/art1']
'''
        hook_cls = compile_mail_hook(src)
        self.assertTrue(issubclass(hook_cls, MailNewsRecipe))

        #没有定义 MailNewsRecipe 子类
        with self.assertRaises(Exception):
            compile_mail_hook('a = 1\n')

        #语法错误
        with self.assertRaises(Exception):
            compile_mail_hook('class BadHook(:\n')

        #方法签名不匹配
        with self.assertRaises(Exception):
            compile_mail_hook('''from calibre.web.feeds.news import MailNewsRecipe
class BadSigHook(MailNewsRecipe):
    def preprocess_email(self, a, b):
        return None
''')

        #高危模块导入被拦截
        with self.assertRaises(ValueError):
            compile_mail_hook('''import os
from calibre.web.feeds.news import MailNewsRecipe
class SafeHook(MailNewsRecipe):
    pass
''')

        with self.assertRaises(ValueError):
            compile_mail_hook('''from subprocess import Popen
from calibre.web.feeds.news import MailNewsRecipe
class SafeHook(MailNewsRecipe):
    pass
''')

        #高危函数调用被拦截
        with self.assertRaises(ValueError):
            compile_mail_hook('''open("test.txt")
from calibre.web.feeds.news import MailNewsRecipe
class SafeHook(MailNewsRecipe):
    pass
''')

        #沙箱逃逸属性访问被拦截
        with self.assertRaises(ValueError):
            compile_mail_hook('''().__class__.__bases__[0].__subclasses__()
from calibre.web.feeds.news import MailNewsRecipe
class SafeHook(MailNewsRecipe):
    pass
''')

    #上传钩子文件的AJAX接口
    def test_upload_hook_api(self):
        from application.mail_hook import hook_blob_name

        #没有此白名单条目，拒绝
        resp = self.client.post('/advanced/inboundmail/hook',
            data={'mail': '*', 'hook_file': (io.BytesIO(HOOK_SRC_BOTH.encode('utf-8')), 'hook.py')},
            content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('whitelist', resp.json['status'])

        WhiteList.create(mail='*', user='admin')
        resp = self.client.post('/advanced/inboundmail/hook',
            data={'mail': '*', 'hook_file': (io.BytesIO(HOOK_SRC_BOTH.encode('utf-8')), 'my_hook.py')},
            content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        self.assertEqual(resp.json['file'], 'my_hook.py')

        dbItem = UserBlob.get_or_none((UserBlob.user == 'admin') & (UserBlob.name == hook_blob_name('*')))
        self.assertIsNotNone(dbItem)

        #上传有语法错误的文件
        resp = self.client.post('/advanced/inboundmail/hook',
            data={'mail': '*', 'hook_file': (io.BytesIO(b'class BadHook(:\n'), 'hook.py')},
            content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(resp.json['status'], 'ok')

        #上传没有钩子类继承的文件
        resp = self.client.post('/advanced/inboundmail/hook',
            data={'mail': '*', 'hook_file': (io.BytesIO(b'a = 1\n'), 'hook.py')},
            content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(resp.json['status'], 'ok')

        #页面显示Hooked状态
        resp = self.client.get('/advanced/inboundmail')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('hookEnabled', resp.text)
        self.assertIn('Hooked', resp.text)
        self.assertIn('/advanced/inboundmail/hook/view/', resp.text)

        #查看钩子源码页面
        resp = self.client.get('/advanced/inboundmail/hook/view/*')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('preprocess_email', resp.text)
        self.assertIn('prism.js', resp.text)

        #删除钩子的AJAX接口
        resp = self.client.post('/advanced/inboundmail/hook/delete', data={'mail': '*'})
        self.assertEqual(resp.json['status'], 'ok')
        dbItem = UserBlob.get_or_none((UserBlob.user == 'admin') & (UserBlob.name == hook_blob_name('*')))
        self.assertIsNone(dbItem)

        #删除钩子后，按钮恢复为Hook
        resp = self.client.get('/advanced/inboundmail')
        self.assertIn('>Hook</a>', resp.text)
        self.assertNotIn('Hooked', resp.text)
        resp = self.client.get('/advanced/inboundmail/hook/view/*')
        self.assertIn('The hook does not exist.', resp.text)

        resp = self.client.post('/advanced/inboundmail/hook/delete', data={'mail': '*'})
        self.assertNotEqual(resp.json['status'], 'ok')

    #钩子的匹配优先级和调用
    def test_run_mail_hook(self):
        from application.mail_hook import save_mail_hook, run_mail_preprocess_email, run_mail_preprocess_soup

        user = KeUser.get_or_none(KeUser.name == 'admin')
        save_mail_hook(user, '*', HOOK_SRC_BOTH, 'hook.py')

        #通配符匹配 preprocess_email
        subject, txtBodies, htmlBodies, attachments = run_mail_preprocess_email(user, 'someone@anywhere.com', 'dl__k@x.com',
            'hello', ['world'], [], [('a.txt', b'data')])
        self.assertEqual(subject, '[hooked] hello')

        #soup钩子修改
        soup = BeautifulSoup('<html><body><p>test</p></body></html>', 'lxml')
        soup, attachments, urls = run_mail_preprocess_soup(user, 'someone@anywhere.com', 'k@x.com', soup, [])
        self.assertIn('content-hook-marker', str(soup))
        self.assertEqual(urls, [])

        #extract_urls 提取外链
        hook3Src = '''from calibre.web.feeds.news import MailNewsRecipe
class ExtUrlsHook(MailNewsRecipe):
    def extract_urls(self, soup):
        return ['http://example.com/art1', 'http://example.com/art2']
'''
        save_mail_hook(user, 'urls@test.com', hook3Src, 'hook3.py')
        soup, attachments, urls = run_mail_preprocess_soup(user, 'urls@test.com', 'k@x.com', soup, [])
        self.assertEqual(urls, ['http://example.com/art1', 'http://example.com/art2'])

        #精确地址优先于通配符
        exactSrc = HOOK_SRC_BOTH.replace("'[hooked] '", "'[exact] '")
        save_mail_hook(user, 'me@home.com', exactSrc, 'exact.py')
        subject, _, _, _ = run_mail_preprocess_email(user, 'me@home.com', 'dl__k@x.com', 'hello', ['world'], [], [])
        self.assertEqual(subject, '[exact] hello')

        #域名匹配优先于通配符
        domainSrc = HOOK_SRC_BOTH.replace("'[hooked] '", "'[domain] '")
        save_mail_hook(user, '@home.com', domainSrc, 'domain.py')
        subject, _, _, _ = run_mail_preprocess_email(user, 'other@home.com', 'dl__k@x.com', 'hello', ['world'], [], [])
        self.assertEqual(subject, '[domain] hello')

        #不匹配精确地址和域名的发件人只命中通配符钩子
        subject, _, _, _ = run_mail_preprocess_email(user, 'other@other.com', 'dl__k@x.com', 'hello', ['world'], [], [])
        self.assertEqual(subject, '[hooked] hello')

    #整条链路：收到邮件 -> 钩子处理 -> 暂存内容为处理后的内容
    def test_hook_in_mail_process(self):
        WhiteList.create(mail='*', user='admin')
        user = KeUser.get_or_none(KeUser.name == 'admin')
        from application.mail_hook import save_mail_hook
        save_mail_hook(user, '*', HOOK_SRC_BOTH, 'hook.py')

        to = 'dl@kindleear.appspotmail.com'
        data = {'sender': 'someone@anywhere.com', 'to': to, 'subject': 'plain mail', 'text': 'the mail body'}
        resp = self.client.post('/mail', data=build_mail_message(**data).encode('utf-8'),
            content_type='multipart/alternative')
        self.assertEqual(resp.status_code, 200)

        #暂存的邮件主题已被钩子修改
        dbItem = InBox.get_or_none(InBox.user == 'admin')
        self.assertIsNotNone(dbItem)
        self.assertEqual(dbItem.subject, '[hooked] plain mail')

    #删除白名单条目时同时删除钩子
    def test_delete_whitelist_delete_hook(self):
        from application.mail_hook import save_mail_hook, hook_blob_name
        wl = WhiteList.create(mail='me@home.com', user='admin')
        user = KeUser.get_or_none(KeUser.name == 'admin')
        save_mail_hook(user, 'me@home.com', HOOK_SRC_BOTH, 'hook.py')

        resp = self.client.get(f'/advanceddel?wlist_id={wl.id}')
        self.assertEqual(resp.status_code, 302)
        dbItem = UserBlob.get_or_none((UserBlob.user == 'admin') & (UserBlob.name == hook_blob_name('me@home.com')))
        self.assertIsNone(dbItem)

    #测试有外链且无图片时的 merge 模式
    @mock.patch('application.view.inbound_email.create_url2book_task')
    def test_hook_merge_mode(self, mock_task):
        WhiteList.create(mail='*', user='admin')
        user = KeUser.get_or_none(KeUser.name == 'admin')
        from application.mail_hook import save_mail_hook
        hook_merge = '''from calibre.web.feeds.news import MailNewsRecipe
class MergeHook(MailNewsRecipe):
    def extract_urls(self, soup):
        return ['http://example.com/art1', 'http://example.com/art2']
'''
        save_mail_hook(user, '*', hook_merge, 'hook_merge.py')
        data = {'sender': 'news@example.com', 'to': 'dl@kindleear.appspotmail.com', 'subject': 'Newsletter', 'text': 'Hello newsletter'}
        resp = self.client.post('/mail', data=build_mail_message(**data).encode('utf-8'),
            content_type='multipart/alternative')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_task.called)
        payload = mock_task.call_args[0][0]
        self.assertEqual(payload['action'], 'merge')
        self.assertIn('Hello newsletter', payload['text'])
        self.assertEqual(payload['urls'], 'http://example.com/art1|http://example.com/art2')
        self.assertEqual(payload['sender'], 'news@example.com')

    #测试有图片附件时降级为分开推送（action不为merge）
    @mock.patch('application.view.inbound_email.send_to_kindle')
    @mock.patch('application.view.inbound_email.create_url2book_task')
    def test_hook_with_images_fallback(self, mock_task, mock_send):
        WhiteList.create(mail='*', user='admin')
        user = KeUser.get_or_none(KeUser.name == 'admin')
        from application.mail_hook import save_mail_hook
        hook_img = '''from calibre.web.feeds.news import MailNewsRecipe
class ImgHook(MailNewsRecipe):
    def preprocess_soup(self, soup, attachments):
        return soup, [('test.png', b'fakeimage')]
    def extract_urls(self, soup):
        return ['http://example.com/art1']
'''
        save_mail_hook(user, '*', hook_img, 'hook_img.py')
        data = {'sender': 'news@example.com', 'to': 'dl@kindleear.appspotmail.com', 'subject': 'Newsletter Img', 'text': 'Hello newsletter with image'}
        resp = self.client.post('/mail', data=build_mail_message(**data).encode('utf-8'),
            content_type='multipart/alternative')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_task.called)
        payload = mock_task.call_args[0][0]
        self.assertEqual(payload['action'], '')  #不使用 merge
        self.assertEqual(payload['text'], '')
        self.assertTrue(mock_send.called)  #独立推送了正文图片邮件

    #测试soup为None时只推urls，不使用merge
    @mock.patch('application.view.inbound_email.create_url2book_task')
    def test_hook_none_soup_no_merge(self, mock_task):
        WhiteList.create(mail='*', user='admin')
        user = KeUser.get_or_none(KeUser.name == 'admin')
        from application.mail_hook import save_mail_hook
        hook_none = '''from calibre.web.feeds.news import MailNewsRecipe
class NoneSoupHook(MailNewsRecipe):
    def preprocess_soup(self, soup, attachments):
        return None, []
    def extract_urls(self, soup):
        return ['http://example.com/art1']
'''
        save_mail_hook(user, '*', hook_none, 'hook_none.py')
        data = {'sender': 'news@example.com', 'to': 'dl@kindleear.appspotmail.com', 'subject': 'Links Only', 'text': 'Ignored text'}
        resp = self.client.post('/mail', data=build_mail_message(**data).encode('utf-8'),
            content_type='multipart/alternative')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_task.called)
        payload = mock_task.call_args[0][0]
        self.assertEqual(payload['action'], '')
        self.assertEqual(payload['text'], '')

    #测试自定义 MailNewsRecipe 的完整生成与执行
    def test_mail_news_recipe_execution(self):
        from application.mail_hook import save_mail_hook
        from build_ebook import urls_to_book
        WhiteList.create(mail='custom@recipe.com', user='admin')
        user = KeUser.get_or_none(KeUser.name == 'admin')

        hook_src = '''from calibre.web.feeds.news import MailNewsRecipe
class MyCustomNews(MailNewsRecipe):
    merge_mail = True
    def extract_urls(self, soup):
        return []
    def preprocess_html(self, soup):
        p = soup.new_tag('p')
        p.string = 'preprocessed-content'
        if soup.body:
            soup.body.append(p)
        return soup
'''
        save_mail_hook(user, 'custom@recipe.com', hook_src, 'hook_custom.py')
        book = urls_to_book([], 'Test Book', user, sender='custom@recipe.com',
                            mail_html='<html><body><p>Mail chapter</p></body></html>', merge_mail=True)
        self.assertTrue(book)
        self.assertTrue(len(book) > 100)
