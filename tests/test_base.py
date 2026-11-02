#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from contextlib import contextmanager
from functools import wraps
import datetime, logging, os, re, unittest, json, io
from unittest import mock

VERBOSITY = int(os.environ.get('KE_TEST_VERBOSITY') or 1)
SLOW_TESTS = bool(os.environ.get('KE_SLOW_TESTS'))

#合并config.py配置信息到os.environ，如果对应环境变量存在，则不会覆盖，和main.py保持一致
def set_env():
    import config
    cfgMap = {}
    keys = ['APP_ID', 'APP_DOMAIN', 'SERVER_LOCATION', 'DATABASE_URL', 'TASK_QUEUE_SERVICE',
        'TASK_QUEUE_BROKER_URL', 'KE_TEMP_DIR', 'DOWNLOAD_THREAD_NUM', 'ALLOW_SIGNUP',
        'SECRET_KEY', 'DELIVERY_KEY', 'ADMIN_NAME', 'POCKET_CONSUMER_KEY', 'HIDE_MAIL_TO_LOCAL',
        'LOG_LEVEL', 'EBOOK_SAVE_DIR', 'DICTIONARY_DIR', 'DEMO_MODE', 'MCP_TOOL_TIMEOUT']
    for key in keys:
        cfgMap[key] = os.getenv(key) if key in os.environ else getattr(config, key)
        if (key == 'APP_DOMAIN') and not cfgMap[key].startswith('http'):
            cfgMap[key] = 'https://' + cfgMap[key]
        os.environ[key] = cfgMap[key]
    return cfgMap

cfgMap = set_env()

from application import init_app
app = init_app(__name__, cfgMap, set_env, debug=True)
celery_app = app.extensions.get("celery", None)

from application.back_end.db_models import *

class BaseTestCase(unittest.TestCase):
    login_required = None

    def setUp(self):
        self.app = app
        app.config['TESTING'] = True
        #connect_database()
        create_database_tables()
        self.client = app.test_client()
        self.runner = app.test_cli_runner()
        if self.login_required:
            self.client.post('/login', data={'username': self.login_required, 'password': self.login_required})
        self.temp_files = []
        
    def tearDown(self):
        #if self.login_required:
        #    self.client.post('/logout')
        if self.temp_files:
            for f in self.temp_files:
                try:
                    os.remove(f)
                except:
                    pass

    def assertIsNone(self, value):
        self.assertTrue(value is None, '%r is not None' % value)

    def assertIsNotNone(self, value):
        self.assertTrue(value is not None, '%r is None' % value)

    @contextmanager
    def assertRaisesCtx(self, exceptions):
        try:
            yield
        except Exception as exc:
            if not isinstance(exc, exceptions):
                raise AssertionError('Got %s, expected %s' % (exc, exceptions))
        else:
            raise AssertionError('No exception was raised.')

def skip_if(expr, reason='n/a'):
    def decorator(method):
        return unittest.skipIf(expr, reason)(method)
    return decorator

def skip_unless(expr, reason='n/a'):
    def decorator(method):
        return unittest.skipUnless(expr, reason)(method)
    return decorator

def slow_test():
    def decorator(method):
        return unittest.skipUnless(SLOW_TESTS, 'skipping slow test')(method)
    return decorator

