#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import os, shutil, sys, unittest, importlib, coverage, builtins, logging

testDir = os.path.dirname(__file__)
appDir = os.path.abspath(os.path.join(testDir, '..'))
sys.path.insert(0, appDir)
sys.path.insert(0, os.path.join(appDir, 'application', 'lib'))

log = logging.getLogger()
log.setLevel(logging.INFO)
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
    os.environ['DATABASE_URL'] = 'sqlite://:memory:'
    os.environ['TASK_QUEUE_SERVICE'] = TASK_QUEUE_SERVICE
    os.environ['TASK_QUEUE_BROKER_URL'] = TASK_QUEUE_BROKER_URL
    os.environ['APP_DOMAIN'] = APP_DOMAIN
    os.environ['ADMIN_NAME'] = ADMIN_NAME
    os.environ['HIDE_MAIL_TO_LOCAL'] = '1' if HIDE_MAIL_TO_LOCAL else ''
    
set_env()

def runtests(suite, verbosity=1, failfast=False):
    runner = unittest.TextTestRunner(verbosity=verbosity, failfast=failfast)
    results = runner.run(suite)
    return results.failures, results.errors

def collect_tests(module=None):
    suite = unittest.TestSuite()
    modules = [module] if module else TEST_MODULES
    for target in modules:
        m = reload_module(target)
        user_suite = unittest.TestLoader().loadTestsFromModule(m)
        suite.addTest(user_suite)
    return suite

def reload_module(module_name):
    module = importlib.import_module(module_name)
    #importlib.reload(module)
    return module

def start_test(verbosity=1, failfast=0, testonly='', report=''):
    if report:
        cov = coverage.coverage()
        cov.start()

    runtests(collect_tests(), verbosity, failfast)

    if report:
        cov.stop()
        cov.save()
        if report == 'html':
            cov.html_report(directory=os.path.join(testDir, 'covhtml'))
        else:
            cov.report()
            
    return 0

TEST_MODULES = ['test_login', 'test_setting', 'test_admin', 'test_subscribe', 'test_adv', 
     'test_logs'] #'test_share',
if INBOUND_EMAIL_SERVICE == 'gae':
    TEST_MODULES.append('test_inbound_email')

if __name__ == '__main__':
    verbosity = 1 #Verbosity of output, 0 | 1 | 4
    failfast = 0 #Exit on first failure/error
    report = '' # '' | 'html' | 'console'
    testonly = '' #module name, empty for testing all

    os.environ['KE_TEST_VERBOSITY'] = str(verbosity)
    os.environ['KE_SLOW_TESTS'] = '1' #Run tests that may be slow
    sys.exit(start_test(verbosity, failfast, testonly, report))

