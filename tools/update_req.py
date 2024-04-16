#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""create/update requirments.txt of KindleEar
[Version Specification](https://peps.python.org/pep-0440)
~=2.31.0 : >=2.31.0,==2.31.*
>=0.2.3,<1.0.0
"""
import re, os, sys, shutil, subprocess

REQ_COMM = [('requests', '~=2.31.0'),
    ('chardet', '~=5.2.0'),
    ('pillow', '~=10.3.0'),
    ('lxml', '~=5.2.0'),
    ('lxml_html_clean', '~=0.1.1'),
    ('sendgrid', '~=6.11.0'),
    ('mailjet_rest', '~=1.3.4'),
    ('python-dateutil', '~=2.9.0'),
    ('css_parser', '~=1.0.10'),
    ('beautifulsoup4', '~=4.12.2'),
    ('html2text', '~=2024.2.26'),
    ('html5lib', '~=1.1'),
    ('#html5-parser', '~=0.4.0'),
    ('gunicorn', '~=21.2.0'),
    ('Flask', '~=3.0.3'),
    ('flask-babel', '~=4.0.0'),
    ('six', '~=1.16.0'),
    ('feedparser', '~=6.0.11'),
]

REQ_DB = {
    'sqlite': [('peewee', '~=3.17.1'),],
    'mysql': [('peewee', '~=3.17.1'), ('pymysql', '~=1.1.0'),],
    'postgresql': [('peewee', '~=3.17.1'), ('psycopg2-binary', '~=2.9.9'),],
    'cockroachdb': [('peewee', '~=3.17.1'), ('psycopg2-binary', '~=2.9.9'),],
    'datastore': [('weedata', '>=0.2.3,<1.0.0'), ('google-cloud-datastore', '~=2.19.0'),],
    'mongodb': [('weedata', '>=0.2.3,<1.0.0'), ('pymongo', '~=4.6.3'),],
    'redis': [('weedata', '>=0.2.3,<1.0.0'), ('redis', '~=5.0.3'),],
    'pickle': [('weedata', '>=0.2.3,<1.0.0'),],
}

REQ_TASK = {
    'gae': [('google-cloud-tasks', '~=2.16.3'),],
    'apscheduler': [('flask-apscheduler', '~=1.13.1')],
    'celery': [('celery', '~=5.3.6'), ('eventlet', '~=0.36.1')],
    'rq': [('flask-rq2', '~=18.3'),],
}

REQ_PLAT = {'gae': [('appengine-python-standard', '~=1.1.6'),],
    'docker': [('weedata', '>=0.2.3,<1.0.0'),('pymysql', '~=1.1.0'), #docker install all libs
    ('psycopg2-binary', '~=2.9.9'),('pymongo', '~=4.6.3'),('redis', '~=5.0.3'),
    ('celery', '~=5.3.6'),('flask-rq2', '~=18.3'),('sqlalchemy', '~=2.0.29')],
}

EXTRA = {
    'sqlalchemy': [('sqlalchemy', '~=2.0.29')],
    'redis': [('redis', '~=5.0.3')],
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

#prepare config.py to build docker
def dockerize_config_py(cfgFile):
    default_cfg = {'APP_ID': 'kindleear', 'DATABASE_URL': 'sqlite:////data/kindleear.db',
        'TASK_QUEUE_SERVICE': 'apscheduler', 'TASK_QUEUE_BROKER_URL': 'memory',
        'KE_TEMP_DIR': '/tmp', 'DOWNLOAD_THREAD_NUM': '3', 'ALLOW_SIGNUP': 'no',
        'HIDE_MAIL_TO_LOCAL': 'yes', 'LOG_LEVEL': 'warning'}
    ret = []
    inDocComment = False
    pattern = r"^([_A-Z]+)\s*=\s*(.+)$"
    with open(cfgFile, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()
    for line in lines:
        line = line.strip()
        if '"""' in line or "'''" in line:
            inDocComment = not inDocComment
            ret.append(line)
            continue
        elif not line or line.startswith('#') or inDocComment:
            ret.append(line)
            continue

        match = re.match(pattern, line)
        name = match.group(1) if match else None
        value = default_cfg.get(name, None)
        if name is not None and value is not None:
            ret.append(f'{name} = "{value}"')
        else:
            ret.append(line)
    
    with open(cfgFile, 'w', encoding='utf-8') as f:
        f.write('\n'.join(ret))
    print(f'Finished update {cfgFile}')

def gae_location():
    try:
        output = subprocess.check_output(['gcloud', 'beta', 'app', 'describe'], universal_newlines=True)
        lines = output.split('\n')
        for line in lines:
            if 'locationId:' in line:
                loc = line[11:].strip()
                return {'us-central': 'us-central1', 'europe-west': 'europe-west1'}.get(loc, loc)
        return ''
    except subprocess.CalledProcessError as e:
        print(f"Subprocess error: {e}")
        return ''

#prepare config.py to deploy in gae
def gaeify_config_py(cfgFile):
    appId = os.getenv('GOOGLE_CLOUD_PROJECT')
    loc = gae_location()
    domain = f"https://{appId}.appspot.com"
    print('------------------------')
    print(f'   AppId: {appId}')
    print(f'Location: {loc}')
    print(f'  Domain: {domain}')
    print('------------------------')
    usrInput = input('Confirm the above information, then press y to continue: ')
    if usrInput.lower() != 'y':
        sys.exit(1)

    default_cfg = {'APP_ID': appId, 'APP_DOMAIN': domain, 'SERVER_LOCATION': gae_location(),
        'DATABASE_URL': 'datastore', 'TASK_QUEUE_SERVICE': 'gae', 'TASK_QUEUE_BROKER_URL': '',
        'KE_TEMP_DIR': '', 'DOWNLOAD_THREAD_NUM': '3', 'ALLOW_SIGNUP': 'no',
        'HIDE_MAIL_TO_LOCAL': 'yes', 'LOG_LEVEL': 'warning'}
    ret = []
    inDocComment = False
    pattern = r"^([_A-Z]+)\s*=\s*(.+)$"
    with open(cfgFile, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()
    for line in lines:
        line = line.strip()
        if '"""' in line or "'''" in line:
            inDocComment = not inDocComment
            ret.append(line)
            continue
        elif not line or line.startswith('#') or inDocComment:
            ret.append(line)
            continue

        match = re.match(pattern, line)
        name = match.group(1) if match else None
        value = default_cfg.get(name, None)
        if name is not None and value is not None:
            ret.append(f'{name} = "{value}"')
        else:
            ret.append(line)
    
    with open(cfgFile, 'w', encoding='utf-8') as f:
        f.write('\n'.join(ret))
    print(f'Finished update {cfgFile}')

#command arugments:
#  update_req docker     : prepare for build docker image
#  update_req docker-all : prepare for build docker image, install all libs
#  update_req gae        : prepare for deploying in gae
#  update_req            : do not modify config.py, only update requirements.txt
if __name__ == '__main__':
    thisDir = os.path.abspath(os.path.dirname(__file__))
    cfgFile = os.path.normpath(os.path.join(thisDir, '..', 'config.py'))
    reqFile = os.path.normpath(os.path.join(thisDir, '..', 'requirements.txt'))
    if not os.path.exists(cfgFile):
        cfgFile = os.path.normpath(os.path.join(thisDir, 'config.py'))
        reqFile = os.path.normpath(os.path.join(thisDir, 'requirements.txt'))

    dockerize = False
    gaeify = False
    if len(sys.argv) == 2 and sys.argv[1] in ('docker', 'docker-all'):
        print('\nGenerating config.py and requirements.txt for Docker deployment.\n')
        dockerize_config_py(cfgFile)
        dockerize = (sys.argv[1] == 'docker-all')
    elif len(sys.argv) == 2 and sys.argv[1] == 'gae':
        print('\nGenerating config.py and requirements.txt for GAE deployment.\n')
        gaeify_config_py(cfgFile)
        gaeify = True
    else:
        print('\nThis script can help you to update requirements.txt.\n')
        usrInput = input('Press y to continue :')
        if usrInput.lower() != 'y':
            sys.exit(1)
        
    cfg = config_to_dict(cfgFile)
    db = cfg['DATABASE_URL'].split('://')[0]
    task = cfg['TASK_QUEUE_SERVICE']
    broker = cfg['TASK_QUEUE_BROKER_URL']
    plat = ''
    if dockerize:
        plat = 'docker'
    elif (cfg['DATABASE_URL'].startswith('datastore') or cfg['TASK_QUEUE_SERVICE'] == 'gae'):
        plat = 'gae'
    
    extras = set()
    if broker.startswith('redis://'):
        extras.add('redis')
    elif broker.startswith('mongodb://'):
        extras.add('pymongo')
    elif broker.startswith(('sqlite://', 'mysql://', 'postgresql://')):
        extras.add('sqlalchemy')
    write_req(reqFile, db, task, plat, *extras)
    print(f'Finished create {reqFile}')
    sys.exit(0)
    
