#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""create/update config.py/requirments.txt of KindleEar
[Version Specification](https://peps.python.org/pep-0440)
~=2.31.0 : >=2.31.0,==2.31.*
>=0.2.3,<1.0.0
"""
import re, os, sys, subprocess, secrets
from itertools import chain

def new_secret_key(length=12):
    allchars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXZYabcdefghijklmnopqrstuvwxyz'
    return ''.join([secrets.choice(allchars) for i in range(length)])

REQ_COMM = [('requests', '~=2.32.0'),
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
    ('gunicorn', '~=22.0.0'),
    ('Flask', '~=3.0.3'),
    ('flask-babel', '~=4.0.0'),
    ('six', '~=1.16.0'),
    ('feedparser', '~=6.0.11'),
    ('qrcode', '~=7.4.2'),
    ('gtts', '~=2.5.1'),
    ('edge-tts', '~=6.1.11'),
    ('justext', '~=3.0.1'),
]

REQ_DB = {
    'sqlite': [('peewee', '~=3.17.1'),],
    'mysql': [('peewee', '~=3.17.1'), ('pymysql', '~=1.1.0'),],
    'postgresql': [('peewee', '~=3.17.1'), ('psycopg2-binary', '~=2.9.9'),],
    'cockroachdb': [('peewee', '~=3.17.1'), ('psycopg2-binary', '~=2.9.9'),],
    'datastore': [('weedata', '>=0.2.7,<1.0.0'), ('google-cloud-datastore', '~=2.19.0'),],
    'mongodb': [('weedata', '>=0.2.7,<1.0.0'), ('pymongo', '~=4.6.3'),],
    'redis': [('weedata', '>=0.2.7,<1.0.0'), ('redis', '~=5.0.3'),],
    'pickle': [('weedata', '>=0.2.7,<1.0.0'),],
}

REQ_TASK = {
    'gae': [('google-cloud-tasks', '~=2.16.3'),],
    'apscheduler': [('flask-apscheduler', '~=1.13.1')],
    'celery': [('celery', '~=5.3.6'), ('eventlet', '~=0.36.1')],
    'rq': [('flask-rq2', '~=18.3'),],
}

REQ_PLAT = {'gae': [('appengine-python-standard', '~=1.1.6'),
        ('google-cloud-texttospeech', '~=2.16.3')],
    'docker': [('chunspell', '~=2.0.4'), ('marisa_trie', '~=1.2.0'), ('indexed-gzip', '~=1.8.7')], #docker/amd64 basic libs
    'dockerArm': [('chunspell', '~=2.0.4'), ('marisa_trie', '~=1.2.0'), ('indexed-gzip', '~=1.8.7')], #docker/arm64 basic libs
    'dockerAll': [('weedata', '>=0.2.7,<1.0.0'),('pymysql', '~=1.1.0'), #docker[all] install all libs
        ('psycopg2-binary', '~=2.9.9'),('pymongo', '~=4.6.3'),('redis', '~=5.0.3'),
        ('celery', '~=5.3.6'),('flask-rq2', '~=18.3'),('sqlalchemy', '~=2.0.29')],
}

#a dict contains all libs, {'name': [(name, version)],}
def all_supported_libs():
    ret = {}
    for item in chain(REQ_COMM, *REQ_DB.values(), *REQ_TASK.values(), *REQ_PLAT.values()):
        ret[item[0].lstrip('#')] = [(item[0].lstrip('#'), item[1]),] #get rid of hashtag
    return ret

ALL_LIBS = all_supported_libs()

def write_req(reqFile, db, task, plat, *extra):
    EXTRAS = [ALL_LIBS for idx in range(len(extra))]
    with open(reqFile, 'w', encoding='utf-8') as f:
        f.write('\n'.join([''.join(item) for item in REQ_COMM]))
        f.write('\n')
        seen = set([item[0].lstrip('#') for item in REQ_COMM])
        for req, opt in zip([REQ_DB, REQ_TASK, REQ_PLAT, *EXTRAS], [db, task, plat, *extra]):
            items = req.get(opt, [])
            for item in items:
                if item[0].lstrip('#') not in seen:
                    f.write(''.join(item) + '\n')
                seen.add(item[0].lstrip('#'))
        f.write('\n')
        
        #Output currently unused libraries and add hashtag
        for name, items in ALL_LIBS.items():
            name = name.lstrip('#')
            if name not in seen:
                seen.add(name)
                f.write('#' + ''.join(items[0]).lstrip('#') + '\n')

#parse config.py to a string with format symbols
def config_to_dict(cfgFile):
    with open(cfgFile, 'r', encoding='utf-8') as f:
        code = compile(f.read(), cfgFile, 'exec')
        config_dict = {}
        exec(code, globals(), config_dict)
    return config_dict

#prepare config.py to build docker
def dockerize_config_py(cfgFile, arg):
    default_cfg = {'APP_ID': 'kindleear', 'DATABASE_URL': 'sqlite:////data/kindleear.db',
        'TASK_QUEUE_SERVICE': 'apscheduler', 'TASK_QUEUE_BROKER_URL': 'memory',
        'KE_TEMP_DIR': '/tmp', 'DOWNLOAD_THREAD_NUM': '3', 'ALLOW_SIGNUP': 'no',
        'HIDE_MAIL_TO_LOCAL': 'yes', 'LOG_LEVEL': 'warning', 'SECRET_KEY': new_secret_key,
        'DELIVERY_KEY': lambda: new_secret_key(6), 'EBOOK_SAVE_DIR': '/data/ebooks', 
        'DICTIONARY_DIR': '/data/dict', 'DEMO_MODE': 'no'}
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
        value = default_cfg.get(name, None) #type:ignore
        if name is not None and value is not None:
            value = value() if callable(value) else value
            ret.append(f'{name} = "{value}"')
        else:
            ret.append(line)
    
    with open(cfgFile, 'w', encoding='utf-8') as f:
        f.write('\n'.join(ret))
    print(f'Finished update of {cfgFile}')

def gae_location():
    try:
        output = subprocess.check_output(['gcloud', 'beta', 'app', 'describe'], universal_newlines=True)
        lines = output.split('\n')
        for line in lines:
            if 'locationId:' in line:
                loc = line[11:].strip()
                return {'us-central': 'us-central1', 'europe-west': 'europe-west1'}.get(loc, loc)
        return ''
    except Exception as e:
        print(f"Subprocess error: {e}")
        return ''

#prepare config.py to deploy in gae
def gaeify_config_py(cfgFile):
    appId = os.getenv('GOOGLE_CLOUD_PROJECT')
    loc = gae_location()
    if not appId or not loc:
        print('Unable to query the app ID and app location. The script will exit directly.')
        sys.exit(1)

    domain = f"https://{appId}.appspot.com"
    print('--------------------------------')
    print(f'   AppId: {appId}')
    print(f'Location: {loc}')
    print(f'  Domain: {domain}')
    print('--------------------------------')
    usrInput = input('Confirm the above information, then press y to continue: ')
    if usrInput.lower() != 'y':
        sys.exit(1)

    default_cfg = {'APP_ID': appId, 'APP_DOMAIN': domain, 'SERVER_LOCATION': loc,
        'DATABASE_URL': 'datastore', 'TASK_QUEUE_SERVICE': 'gae', 'TASK_QUEUE_BROKER_URL': '',
        'KE_TEMP_DIR': '/tmp', 'DOWNLOAD_THREAD_NUM': '2', 'ALLOW_SIGNUP': 'no',
        'HIDE_MAIL_TO_LOCAL': 'yes', 'LOG_LEVEL': 'warning', 'SECRET_KEY': new_secret_key,
        'DELIVERY_KEY': lambda: new_secret_key(6), 'EBOOK_SAVE_DIR': '', 'DICTIONARY_DIR': '',
        'DEMO_MODE': 'no'}
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
        value = default_cfg.get(name, None) #type:ignore
        if name is not None and value is not None:
            value = value() if callable(value) else value
            ret.append(f'{name} = "{value}"')
        else:
            ret.append(line)
    
    with open(cfgFile, 'w', encoding='utf-8') as f:
        f.write('\n'.join(ret))
    print(f'Finished update of {cfgFile}')

#Change some params in worker.yaml
#arg: gae[B2,2,t2,20m]
def update_worker_yaml(workerYamlFile, arg):
    items = arg.split('[')[-1].rstrip(']').split(',') if '[' in arg else []
    items = [e.strip() for e in items if e.strip()]
    if not items:
        return

    instance_class = ''
    idle_timeout = ''
    max_instances = ''
    threads = ''
    for item in items:
        if item.startswith('B') and item[1:].isdigit():
            instance_class = item
        if item.startswith('t') and item[1:].isdigit():
            threads = item[1:]
        elif item.endswith('m') and item[:-1].isdigit():
            idle_timeout = item
        elif item.isdigit():
            max_instances = item

    with open(workerYamlFile, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()

    for idx, line in enumerate(lines):
        if line.startswith('instance_class:') and instance_class:
            lines[idx] = f"instance_class: {instance_class}"
        elif line.startswith('  max_instances:') and max_instances:
            lines[idx] = f"  max_instances: {max_instances}"
        elif line.startswith('  idle_timeout:') and idle_timeout:
            lines[idx] = f"  idle_timeout: {idle_timeout}"
        elif line.startswith('entrypoint:'):
            #entrypoint: gunicorn -b :$PORT --workers 1 --threads 2 --timeout 1200 main:app
            parts = [item.strip() for item in line.split(' ') if item.strip()]
            def elemIdx(key): #Find position of key
                return parts.index(key) if key in parts else 0

            def UpdateOrAddParam(key1, value, key2=None): #Update if exists or add if not
                idx = elemIdx(key1) or elemIdx(key2)
                if idx > 0 and idx < len(parts) - 1 and parts[idx + 1].isdigit():
                    parts[idx + 1] = value
                elif 0 < idx < len(parts):
                    parts.insert(idx + 1, value)
                else:
                    idx = len(parts) - 1
                    parts[idx:idx] = [key1, value]

            if max_instances:
                UpdateOrAddParam('--workers', max_instances, '-w')
            if idle_timeout:
                UpdateOrAddParam('--timeout', str(int(int(idle_timeout[:-1]) * 60)), '-t')
            if threads:
                UpdateOrAddParam('--threads', threads)
            
            lines[idx] = ' '.join(parts)

    ret = [f'Finished update of {workerYamlFile} using params:']
    instance_class and ret.append(f'    instance_class: {instance_class}') #type:ignore
    max_instances and ret.append(f'     max_instances: {max_instances}') #type:ignore
    threads and ret.append(f'           threads: {threads}') #type:ignore
    idle_timeout and ret.append(f'      idle_timeout: {idle_timeout}') #type:ignore
    ret.append('')
    if len(ret) > 2:
        with open(workerYamlFile, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print('\n'.join(ret))

if __name__ == '__main__':
    thisDir = os.path.abspath(os.path.dirname(__file__))
    cfgFile = os.path.normpath(os.path.join(thisDir, '..', 'config.py'))
    reqFile = os.path.normpath(os.path.join(thisDir, '..', 'requirements.txt'))
    workerYamlFile = os.path.normpath(os.path.join(thisDir, '..', 'worker.yaml'))
    if not os.path.exists(cfgFile):
        cfgFile = os.path.normpath(os.path.join(thisDir, 'config.py'))
        reqFile = os.path.normpath(os.path.join(thisDir, 'requirements.txt'))
        workerYamlFile = os.path.normpath(os.path.join(thisDir, 'worker.yaml'))

    dockerArgs = ''
    gaeify = False
    arg1 = sys.argv[1] if len(sys.argv) >= 2 else ''
    arg2 = sys.argv[2] if len(sys.argv) >= 3 else '' #TARGETPLATFORM
    if arg1 == '--help':
        print('This script can help you to update config.py and requirements.txt.')
        print('Command arguments:')
        print('  docker              : prepare for docker image')
        print('  docker[all]         : prepare for docker image, install all libs')
        print('  docker[name1,name2] : prepare for docker image, install name1,name2')
        print('  gae                 : prepare for deploying in gae')
        print('  gae[B2,1,t2,20m]    : prepare for deploying in gae, customize worker params')
        print('  empty               : do not modify config.py, only update requirements.txt')
        sys.exit(1)
    elif arg1.startswith('docker'):
        print('\nUpdating config.py and requirements.txt for Docker deployment.\n')
        dockerize_config_py(cfgFile, arg1)
        dockerArgs = arg1
    elif arg1.startswith('gae'):
        print('\nUpdating config.py and requirements.txt for GAE deployment.\n')
        gaeify_config_py(cfgFile)
        update_worker_yaml(workerYamlFile, arg1)
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
    if dockerArgs == 'docker[all]':
        plat = 'dockerAll'
    elif dockerArgs.startswith('docker'):
        plat = 'dockerArm' if 'arm' in arg2 else 'docker'
    elif (cfg['DATABASE_URL'].startswith('datastore') or cfg['TASK_QUEUE_SERVICE'] == 'gae'):
        plat = 'gae'
    
    extras = set()
    if broker.startswith('redis://'):
        extras.add('redis')
    elif broker.startswith('mongodb://'):
        extras.add('pymongo')
    elif broker.startswith(('sqlite://', 'mysql://', 'postgresql://')):
        extras.add('sqlalchemy')
    if '[' in dockerArgs and dockerArgs != 'docker[all]': #add libs in square brackets
        extras.update(dockerArgs.split('[')[-1].rstrip(']').split(','))

    write_req(reqFile, db, task, plat, *extras)
    print(f'Finished create {reqFile}')
    sys.exit(0)
