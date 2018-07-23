#!/usr/bin/env python
# -*- coding:utf-8 -*-
""" uploader helper for KindleEar <https://github.com/cdhigh/KindleEar>
It will modify AppId and some other items for you automatically.
Configure file 'custom.txt' format (encoding of the file must be ascii):
application: YourAppId
email: YourEmail
timezone: 8
If it not exist, this script will create it in same directory of __file__.
"""
import os, sys, re, codecs, locale, shutil
__Author__ = 'cdhigh <https://github.com/cdhigh>'
__Version__ = '1.4'
__Date__ = '2017-09-03'

CUSTOM_FILE = 'custom.txt'
KE_DIR = 'KindleEar'
KE_MASTER_DIR = 'KindleEar-master'
PAT_APP = r"^application:\s*([\w]+)"
PAT_EMAIL = r"^SRC_EMAIL\s*=\s*[\"\']([\w@\.-]+)[\"\'](.*)"
PAT_DOMAIN = r"^DOMAIN\s*=\s*[\"\']([\w:/\.-]+)[\"\'](.*)"
PAT_TZ = r"^TIMEZONE\s*=\s*?(-{0,1}\d+)(.*)"

try:
    input = raw_input
except NameError:
    pass

#(re)move chinese books to a subdirectory (donot display in webpage) 
def RemoveChineseBooks(ke_dir):
    lang = 'zh_CN'
    cn_books = [] #Relative path saved
    loc = locale.getdefaultlocale()
    if loc and len(loc) > 1:
        lang = loc[0]
    if lang.startswith('zh'):
        return

    #create list of books which language is Chinese
    books_dir = os.path.join(ke_dir, 'books')
    if not os.path.exists(books_dir):
        return
    list_book_dirs = os.walk(books_dir)
    for root, dirs, files in list_book_dirs:
        for f in files:
            if not f.endswith('.py') or f.startswith('__') or f.endswith('base.py'):
                continue
            
            bkfile = os.path.join(root, f)
            rel_path_bkfile = bkfile.replace(books_dir, '').lstrip('/').lstrip('\\') #Relative path
            all_lines = []
            try:
                with codecs.open(bkfile, 'r', 'utf-8') as f:
                    all_lines = f.read().split('\n')
            except:
                continue
                
            if not all_lines:
                continue
                
            iscnbook = False
            for line in all_lines:
                ln = line.replace(' ', '').replace('\t', '')
                if ln.startswith(('title=', 'description=')): #title line
                    for ch in ln:
                        if u'\u4e00' <= ch <= u'\u9fff': #Chinese Chars
                            iscnbook = True
                            break
                    #if not iscnbook:
                    #    break #next book
                        
            if iscnbook: #Is Chinese Book
                cn_books.append(rel_path_bkfile)
                #*.pyc exists?
                if rel_path_bkfile.endswith('.py'):
                    pycfile = rel_path_bkfile + 'c'
                    if os.path.exists(pycfile):
                        cn_books.append(pycfile)
            
    if not cn_books:
        return

    #if exist some Chinese books, then ask for move or not
    ret = input('Do you want to remove Chinese books? (y/n)')
    if ret not in ('Y', 'YES', 'y', 'yes'):
        return
        
    #check and create subdirectory
    bakdir = os.path.join(books_dir, 'ChineseBooksBak')
    if not os.path.exists(bakdir):
        os.makedirs(bakdir)
        
    for book in cn_books:
        dst = os.path.join(bakdir, book)
        dst_dir = os.path.dirname(dst) #create dst directory
        if not os.path.exists(dst_dir):
            try:
                os.makedirs(dst_dir)
            except:
                pass
        if os.path.exists(dst): #dst exist, try to remove it firstly.
            try:
                os.remove(dst)
            except:
                pass
        
        #remove book to bak directory
        try:
            shutil.move(os.path.join(books_dir, book), dst)
        except:
            try:
                os.remove(os.path.join(books_dir, book))
            except:
                pass
    
    #Delete __init__.py of directory backup
    list_bak_dir = os.walk(bakdir)
    for root, dirs, files in list_bak_dir:
        for f in files:
            if f == '__init__.py' or f == '__init__.pyc':
                #try:
                    os.remove(os.path.join(root, f))
                #except:
                #    pass
    
def Main():
    #Searching for KindleEar folder
    ke_dir = os.path.join(os.path.dirname(__file__), KE_DIR)
    kem_dir = os.path.join(os.path.dirname(__file__), KE_MASTER_DIR)
    kemm_dir = os.path.join(kem_dir, KE_MASTER_DIR)
    keup_dir = os.path.join(os.path.dirname(__file__), '..', KE_DIR)
    dirs = list(filter(os.path.exists, (ke_dir, kemm_dir, kem_dir, keup_dir)))
    if not dirs:
        print("Cant found folder 'KindleEar'! Please download it from github firstly.")
        return 1
    
    ke_dir = dirs[0]
    custom_file = os.path.join(os.path.dirname(__file__), CUSTOM_FILE) #file for saving your custom info
    app_yaml = os.path.join(ke_dir, 'app.yaml')
    work_yaml = os.path.join(ke_dir, 'module-worker.yaml')
    cfg_file = os.path.join(ke_dir, 'config.py')
    
    slapp = [] #string buffer for app.yaml
    if os.path.exists(app_yaml):
        with open(app_yaml, 'r') as fapp:
            slapp = fapp.read().split('\n')
    if not slapp:
        print("Not exist 'app.yaml' or it's invalid, please download KindleEar again.")
        return 1
        
    slcfg = [] #string buffer for config.py
    if os.path.exists(cfg_file):
        with codecs.open(cfg_file, 'r', 'utf-8') as fcfg:
            slcfg = fcfg.read().split('\n')
    if not slcfg:
        print("Not exist 'config.py' or it's invalid, please download KindleEar again.")
        return 1
        
    slwork = [] #string buffer for module-worker.yaml
    if os.path.exists(work_yaml):
        with open(work_yaml, 'r') as fwork:
            slwork = fwork.read().split('\n')
    
    #init some parameter
    app = email = timezone = ''
    mt1 = re.match(PAT_APP, slapp[0])
    mt2 = re.match(PAT_APP, slwork[0]) if slwork else mt1
    if mt1 and mt2 and mt1.group(1) == mt2.group(1):
        app = mt1.group(1)
    for index, line in enumerate(slcfg):
        mt = re.match(PAT_EMAIL, line)
        if mt:
            email = mt.group(1)
            continue
        mt = re.match(PAT_DOMAIN, line)
        if mt:
            domain = mt.group(1)
            continue
        mt = re.match(PAT_TZ, line)
        if mt:
            timezone = mt.group(1)
            continue
            
    slcustom = []
    needinput = True
    if os.path.exists(custom_file):
        with open(custom_file, 'r') as fcustom:
            slcustom = fcustom.read().split('\n')
        for line in slcustom:
            if line.lower().startswith('application:'):
                app = line[len('application:'):].strip()
            elif line.lower().startswith('email:'):
                email = line[len('email:'):].strip()
            elif line.lower().startswith('timezone:'):
                timezone = line[len('timezone:'):].strip()
    
    ret = input('Your custom info :\n\t  app id : %s\n\t   email : %s\n\ttimezone : %s\nCorrect? (y/n) : '%(app,email,timezone))
    if ret in ('y', 'yes', 'Y', 'YES'):
        needinput = False #configure items correct!
    
    while 1:
        if needinput or not all((app, email, timezone)):
            new_app = input('Input app id (%s): ' % app)
            new_email = input('Input your gmail (%s): ' % email)
            new_timezone = input('Input your timezone (%s): ' % timezone)
            app = new_app if new_app else app
            email = new_email if new_email else email
            timezone = new_timezone if new_timezone else timezone
            with open(custom_file, 'w') as fcustom:
                fcustom.write('application: %s\n' % app)
                fcustom.write('email: %s\n' % email)
                fcustom.write('timezone: %s' % timezone)
                
        if all((app, email, timezone)):
            break
        elif not app:
            print('app id is empty, please input it again.')
        elif not email:
            print('email is empty, please input it again.')
        elif not timezone:
            print('timezone is empty, please input it again.')
        
    #Check and modify app.yaml
    mt = re.match(PAT_APP, slapp[0])
    if mt:
        if mt.group(1) != app:
            slapp[0] = 'application: ' + app
            with open(app_yaml, 'w') as fapp:
                fapp.write('\n'.join(slapp))
    else:
        print('app.yaml seems invalid, please download KindleEar again.')
        return 1
    
    #Check and modify module-work.yaml
    if slwork:
        mt = re.match(PAT_APP, slwork[0])
        if mt:
            if mt.group(1) != app:
                slwork[0] = 'application: ' + app
                with open(work_yaml, 'w') as fwork:
                    fwork.write('\n'.join(slwork))
        else:
            print('module-work.yaml seems invalid, please download KindleEar again.')
            return 1
    
    #Check and modify config.py
    cfg_changed = False
    for index, line in enumerate(slcfg):
        mt = re.match(PAT_EMAIL, line)
        if mt:
            if mt.group(1) != email:
                slcfg[index] = 'SRC_EMAIL = "%s"' % email + mt.group(2)
                cfg_changed = True
            continue
        mt = re.match(PAT_DOMAIN, line)
        if mt:
            domain = mt.group(1)
            if domain.endswith('appspot.com') and domain not in (
                'http://%s.appspot.com' % app, 'https://%s.appspot.com' % app):
                slcfg[index] = 'DOMAIN = "https://%s.appspot.com"' % app + mt.group(2)
                cfg_changed = True
            continue
        mt = re.match(PAT_TZ, line)
        if mt:
            if mt.group(1) != timezone:
                slcfg[index] = 'TIMEZONE = %s'%timezone + mt.group(2)
                cfg_changed = True
            continue
    if cfg_changed:
        with codecs.open(cfg_file, 'w', 'utf-8') as fcfg:
            fcfg.write('\n'.join(slcfg))
    
    RemoveChineseBooks(ke_dir)
    
    return 0
    
if __name__ == '__main__':
    print('\nKindleEar uploader v%s (%s) by %s\n' % (__Version__, __Date__, __Author__))
    ret = Main()
    if ret:
        import sys
        sys.exit(ret)
        