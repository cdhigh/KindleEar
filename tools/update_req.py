#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""create/update requirments.txt of KindleEar
"""
import re, os, sys, shutil

REQ_COMM = [('requests', '>=2.31.0,<3.0.0'),
    ('chardet', '>=5.2.0,<6.0.0'),
    ('pillow', '>=10.2.0,<11.0.0'),
    ('lxml', '>=5.0.0,<6.0.0'),
    ('sendgrid', '>=6.11.0,<7.0.0'),
    ('mailjet_rest', '>=1.3.4,<2.0.0'),
    ('python-dateutil', '>=2.8.2,<3.0.0'),
    ('css_parser', '>=1.0.10,<=2.0.0'),
    ('beautifulsoup4', '>=4.12.2,<5.0.0'),
    ('html2text', '>=2020.1.16'),
    ('html5lib', '>=1.1,<2.0'),
    ('#html5-parser', '~=0.4.0'),
    ('gunicorn', '>=21.2.0,<22.0.0'),
    ('Flask', '>=3.0.0,<4.0.0'),
    ('flask-babel', '>=4.0.0,<5.0.0'),
    ('six', '>=1.16.0,<2.0.0'),
    ('feedparser', '>=6.0.11,<7.0.0'),
]

REQ_DB = {
    'sqlite': [('peewee', '>=3.1.7,<4.0.0'),],
    'mysql': [('peewee', '>=3.1.7,<4.0.0'), ('pymysql', '>=1.1.0,<2.0.0'),],
    'postgresql': [('peewee', '>=3.1.7,<4.0.0'), ('psycopg2', '>=2.9.9,<3.0.0'),],
    'cockroachdb': [('peewee', '>=3.1.7,<=4.0.0'), ('psycopg2', '>=2.9.9,<3.0.0'),],
    'datastore': [('weedata', '>=0.2.1,<1.0.0'), ('google-cloud-datastore', '>=2.19.0,<3.0.0'),],
    'mongodb': [('weedata', '>=0.2.1,<1.0.0'), ('pymongo', '>=3.7.2,<4.0.0'),],
    'redis': [('weedata', '>=0.2.1,<1.0.0'), ('redis', '>=4.5.0,<6.0.0'),],
    'pickle': [('weedata', '>=0.2.1,<1.0.0'),],
}

REQ_TASK = {
    'gae': [('google-cloud-tasks', '>=2.15.0,<3.0.0'),],
    'apscheduler': [('flask-apscheduler', '>=1.13.1,<2.0.0')],
    'celery': [('celery', '>=5.3.6,<6.0.0'), ('eventlet', '>=0.35.1,<1.0.0')],
    'rq': [('flask-rq2', '>=18.3,<19.0'),],
}

REQ_PLAT = {'gae': [('appengine-python-standard', '>=1.1.6,<2.0.0'),],}

EXTRA = {
    'sqlalchemy': [('sqlalchemy', '>=2.0.28,<3.0.0')],
    'redis': [('redis', '>=4.5.0,<6.0.0')],
}

def write_req(reqFile, db, task, plat, *extra):
    with open(reqFile, 'w', encoding='utf-8') as f:
        f.write('\n'.join([''.join(item) for item in REQ_COMM]))
        f.write('\n')
        EXTRAS = [EXTRA for idx in range(len(extra))]
        seen = set()
        for req, opt in zip([REQ_DB, REQ_TASK, REQ_PLAT, *EXTRAS], [db, task, plat, *extra]):
            #f.write('\n')
            items = req.get(opt, None)
            for item in (items or []):
                if item[0] not in seen:
                    f.write(''.join(item) + '\n')
                seen.add(item[0])
        f.write('\n')
        for req, opt in zip([REQ_DB, REQ_TASK, REQ_PLAT, *EXTRAS], [db, task, plat, *extra]):
            items = req.get(opt, None)
            for key, items in req.items():
                for item in filter(lambda x: x[0] not in seen, (items or [])):
                    seen.add(item[0])
                    f.write('#' + ''.join(item) + '\n')

#parse config.py to a string with format symbols
def config_to_dict(cfgFile):
    with open(cfgFile, 'r', encoding='utf-8') as f:
        code = compile(f.read(), cfgFile, 'exec')
        config_dict = {}
        exec(code, globals(), config_dict)
    return config_dict

if __name__ == '__main__':
    print('\nThis script can help you to generate requirements.txt.\n')
    usrInput = input('Press y to continue :')
    if usrInput.lower() != 'y':
        sys.exit(0)

    thisDir = os.path.abspath(os.path.dirname(__file__))
    cfgFile = os.path.normpath(os.path.join(thisDir, '..', 'config.py'))
    reqFile = os.path.normpath(os.path.join(thisDir, '..', 'requirements.txt'))

    cfg = config_to_dict(cfgFile)
    db = cfg['DATABASE_URL'].split('://')[0]
    task = cfg['TASK_QUEUE_SERVICE']
    broker = cfg['TASK_QUEUE_BROKER_URL']
    if (cfg['DATABASE_URL'].startswith('datastore') or cfg['TASK_QUEUE_SERVICE'] == 'gae'):
        plat = 'gae'
    else:
        plat = ''
    extras = set()
    if broker.startswith('redis://'):
        extras.add('redis')
    elif broker.startswith('mongodb://'):
        extras.add('pymongo')
    elif broker.startswith(('sqlite://', 'mysql://', 'postgresql://')):
        extras.add('sqlalchemy')
    write_req(reqFile, db, task, plat, *extras)
    print(f'Finished create {reqFile}')
