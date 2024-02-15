#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import os, shutil, sys, unittest, importlib, coverage, builtins, logging

testDir = os.path.dirname(__file__)
appDir = os.path.abspath(os.path.join(testDir, '..'))
sys.path.insert(0, appDir)
sys.path.insert(0, os.path.join(appDir, 'application', 'lib'))

log = logging.getLogger()
log.setLevel(logging.DEBUG)
builtins.__dict__['default_log'] = log
builtins.__dict__['appDir'] = appDir

from config import *

#将config.py里面的部分配置信息写到 os.environ，因为有些部分可能不依赖flask运行
def set_env():
    if not TEMP_DIR:
        os.environ['TEMP_DIR'] = ''
    elif os.path.isabs(TEMP_DIR):
        os.environ['TEMP_DIR'] = TEMP_DIR
    else:
        os.environ['TEMP_DIR'] = os.path.join(appDir, TEMP_DIR)
    os.environ['DOWNLOAD_THREAD_NUM'] = str(int(DOWNLOAD_THREAD_NUM))
    os.environ['DATABASE_ENGINE'] = 'sqlite'
    os.environ['DATABASE_NAME'] = ':memory:'
    os.environ['DATABASE_HOST'] = 'localhost'
    os.environ['DATABASE_PORT'] = str(8081)
    os.environ['DATABASE_USERNAME'] = ''
    os.environ['DATABASE_PASSWORD'] = ''

    os.environ['TASK_QUEUE_SERVICE'] = TASK_QUEUE_SERVICE
    os.environ['CELERY_BROKER_URL'] = CELERY_BROKER_URL
    os.environ['CELERY_RESULT_BACKEND'] = CELERY_RESULT_BACKEND
    os.environ['KE_DOMAIN'] = KE_DOMAIN
    os.environ['SRC_EMAIL'] = SRC_EMAIL
    
set_env()

TEST_MODULES = ['test_login', 'test_setting', 'test_admin', 'test_subscribe', 'test_adv']
if INBOUND_EMAIL_SERVICE == 'gae':
    TEST_MODULES.append('test_inbound_email')

#TEST_MODULES = ['test_inbound_email']


def runtests(suite, verbosity=1, failfast=False):
    runner = unittest.TextTestRunner(verbosity=verbosity, failfast=failfast)
    results = runner.run(suite)
    return results.failures, results.errors

def collect_tests(args=None):
    suite = unittest.TestSuite()

    if not args:
        for m in [reload_module(m) for m in TEST_MODULES]:
            module_suite = unittest.TestLoader().loadTestsFromModule(m)
            suite.addTest(module_suite)
    else:
        for arg in args:
            m = reload_module(arg)
            user_suite = unittest.TestLoader().loadTestsFromNames(m)
            suite.addTest(user_suite)

    return suite

def reload_module(module_name):
    module = importlib.import_module(module_name)
    #importlib.reload(module)
    return module

def main():
    verbosity = 4 #Verbosity of output, 0 | 1 | 4
    failfast = 0 #Exit on first failure/error
    report = '' # '' | 'html' | 'console'

    os.environ['KE_TEST_VERBOSITY'] = str(verbosity)
    os.environ['KE_SLOW_TESTS'] = '1' #Run tests that may be slow

    if report:
        cov = coverage.coverage()
        cov.start()

    suite = collect_tests()
    runtests(suite, verbosity, failfast)

    if report:
        cov.stop()
        cov.save()
        if report == 'html':
            cov.html_report(directory=os.path.join(testDir, 'cov_html'))
        else:
            cov.report()
            
    return 0

if __name__ == '__main__':
    sys.exit(main())
