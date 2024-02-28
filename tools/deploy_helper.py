#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""帮助设置requirments.txt和config.py
"""
import re, os, sys, shutil

REQ_COMM = [('requests', '>=2.0.0,<=2.99.0'),
    ('chardet', '>=5.0.0,<=5.99.0'),
    ('pillow', '>=10.0.0,<=10.99.0'),
    ('lxml', '>=5.0.0,<=5.99.0'),
    ('sendgrid', '>=6.0.0,<=6.99.0'),
    ('python-dateutil', '>=2.0.0,<=2.99.0'),
    ('css_parser', '>=1.0.0,<=1.99.0'),
    ('beautifulsoup4', '>=4.0.0,<=4.99.0'),
    ('html2text', '>=2020.1.16'),
    ('html5lib', '>=1.1'),
    ('#html5-parser', '~=0.4.0'),
    ('gunicorn', ''),
    ('Flask', '>=3.0.0,<=3.99.0'),
    ('flask-babel', '>=4.0.0,<=4.99.0'),
    ('six', '>=1.0.0,<=1.99.0'),
    ('feedparser', '>=6.0.0,<=6.99.0'),
]

REQ_DB = {
    'datastore': [('weedata', '>=0.1.0,<=0.99.0'), ('google-cloud-datastore', '>=2.19.0,<=2.99.0'),],
    'sqlite': [('peewee', '>=3.0.0,<=3.99.0'),],
    'mysql': [('peewee', '>=3.0.0,<=3.99.0'), ('pymysql', '>=1.0.0,<=1.99.0'),],
    'postgresql': [('peewee', '>=3.0.0,<=3.99.0'), ('psycopg2', '>=2.0.0,<=2.99.0'),],
    'cockroachdb': [('peewee', '>=3.0.0,<=3.99.0'), ('psycopg2', '>=2.0.0,<=2.99.0'),],
    'mongodb': [('weedata', '>=0.1.0,<=0.99.0'), ('pymongo', '>=3.0.0,<=3.99.0'),],
    'redis': [('weedata', '>=0.1.0,<=0.99.0'), ('redis', '>=4.5.0,<=5.99.0'),],
    'pickle': [('weedata', '>=0.1.0,<=0.99.0'),],
}

REQ_TASK = {
    'gae': [('google-cloud-tasks', '>=2.0.0,<=2.99.0'),],
    'apscheduler': [('flask-apscheduler', '>=1.0.0,<=1.99.0')],
    'celery': [('celery', '>=5.0.0,<=5.99.0'), ('eventlet', '>=0.30.0,<=0.99.0')],
    'rq': [('flask-rq2', '>=18.0,<=18.99'),],
}

REQ_PLAT = {'gae': [('appengine-python-standard', '>=1.1.0,<=1.99.0'),],}

EXTRA = {
    'sqlalchemy': [('sqlalchemy', '')],
}

def write_req(reqFile, db, task, plat, *extra):
    with open(reqFile, 'w', encoding='utf-8') as f:
        f.write('\n'.join([''.join(item) for item in REQ_COMM]))
        f.write('\n')
        EXTRAS = [EXTRA for idx in range(len(extra))]
        for req, opt in zip([REQ_DB, REQ_TASK, REQ_PLAT, *EXTRAS], [db, task, plat, *extra]):
            f.write('\n')
            items = req.get(opt, None)
            seen = set()
            for item in (items or []):
                if item[0] not in seen:
                    f.write(''.join(item) + '\n')
                seen.add(item[0])
            for key, items in req.items():
                if key != opt:
                    for item in filter(lambda x: x[0] not in seen, (items or [])):
                        seen.add(item[0])
                        f.write('#' + ''.join(item) + '\n')

#parse config.py to a string with format symbols
def config_to_fmtstr(cfgFile, fmt='dict'):
    with open(cfgFile, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()

    ret = [] if fmt == 'list' else {}
    docComment = False
    pattern = r"""^([_A-Z]+)\s*=\s*([f]{0,1}"[^"]*"|[f]{0,1}'[^']*'|\S+)\s*(#.*)?$"""
    for line in lines:
        line = line.strip()
        if line.startswith(('"""', "'''")):
            docComment = not docComment
            if fmt == 'list':
                ret.append(line)
            continue
        elif not line or line.startswith('#') or docComment:
            if fmt == 'list':
                ret.append(line)
            continue

        match = re.match(pattern, line)
        if match:
            if fmt == 'list':
                ret.append((match.group(1), match.group(2), match.group(3)))
            else:
                ret[match.group(1)] = match.group(2).strip('f"\'')
        else:
            ret.append(line)
    return ret

#Write to config.py, cfgItems={'APPID':,...}
def write_cfg(cfgFile, cfgItems):
    dir_ = os.path.dirname(cfgFile)
    b, ext = os.path.splitext(os.path.basename(cfgFile))
    bakFile = os.path.join(dir_, f'{b}_bak{ext}')
    try:
        shutil.copy(cfgFile, bakFile)
    except Exception as e:
        print(str(e))
        return

    cfg = config_to_fmtstr(cfgFile)
    with open(cfgFile, 'w', encoding='utf-8') as f:
        for line in cfg:
            if not isinstance(line, tuple):
                f.write(line)
                f.write('\n')
                continue

            item, orgValue, comment = line
            comment = ('  ' + comment) if comment else ''
            value = cfgItems.get(item, None)
            if value is not None:
                value = f'"{value}"' if isinstance(value, str) else value
                f.write(f'{item} = {value}{comment}\n')
            else:
                f.write(f'{item} = {orgValue}{comment}\n')

if __name__ == '__main__':
    print('\nThis script can help you to generate requirements.txt.\n')
    thisDir = os.path.dirname(__file__)
    cfgFile = os.path.join(thisDir, '..', 'config.py')
    reqFile = os.path.join(thisDir, '..', 'requirements.txt')

    cfg = config_to_fmtstr(cfgFile)
    db = cfg['DATABASE_URL'].split('://')[0]
    task = cfg['TASK_QUEUE_SERVICE']
    broker = cfg['TASK_QUEUE_BROKER_URL']
    if (cfg['DATABASE_URL'].startswith('datastore') or cfg['INBOUND_EMAIL_SERVICE'] == 'gae' or 
        cfg['TASK_QUEUE_SERVICE'] == 'gae'):
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

