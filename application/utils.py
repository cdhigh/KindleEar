#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#一些常用工具函数
#Author: cdhigh <https://github.com/cdhigh>
import os, sys, hashlib, base64, secrets, datetime, re, traceback
from urllib.parse import urlparse

#比较安全的eval
#txt: 需要编译的字符串
#gbl: 全局字典
#local: 本地字典
def safe_eval(txt, gbl=None, local=None):
    gbl = gbl or {}
    local = local or {}
    code = compile(txt, '<user input>', 'eval')
    reason = None
    banned = ('eval', 'compile', 'exec', 'getattr', 'hasattr', 'setattr', 'delattr',
        'classmethod', 'globals', 'help', 'input', 'isinstance', 'issubclass', 'locals',
        'open', 'print', 'property', 'staticmethod', 'vars', 'os')
    for name in code.co_names:
        if re.search(r'^__\S*__$', name):
            reason = 'dunder attributes not allowed' # pragma: no cover
        elif name in banned:
            reason = 'arbitrary code execution not allowed' # pragma: no cover
        if reason:
            raise NameError(f'{name} not allowed : {reason}') # pragma: no cover
    return eval(code, gbl, local)

#获取发生异常时的文件名和行号，添加到自定义错误信息后面
#此函数必须要在异常后调用才有意义，否则只是简单的返回传入的参数
def loc_exc_pos(msg: str):
    klass, e, excTb = sys.exc_info()
    if excTb:
        stacks = traceback.extract_tb(excTb) #StackSummary instance, a list
        if len(stacks) == 0:
            return msg

        top = stacks[0]
        bottom2 = stacks[-2] if len(stacks) > 1 else stacks[-1]
        bottom1 = stacks[-1]
        tF = os.path.basename(top.filename)
        tLn = top.lineno
        b1F = os.path.basename(bottom1.filename)
        b1Ln = bottom1.lineno
        b2F = os.path.basename(bottom2.filename)
        b2Ln = bottom2.lineno
        typeName = klass.__name__ if klass else ''
        return f'{msg}: {typeName} {e} [{tF}:{tLn}->...->{b2F}:{b2Ln}->{b1F}:{b1Ln}]'
    else:
        return msg

#字符串转整数，出错则返回default
def str_to_int(txt, default=0):
    try:
        return int(txt.split('.')[0].replace(',', '').strip())
    except:
        return default

#字符串转浮点，出错则返回default
def str_to_float(txt, default=0.0):
    try:
        return float(txt.replace(',', '').replace('_', '').strip())
    except:
        return default

#字符串转bool(txt)
def str_to_bool(txt):
    return str(txt or '').lower().strip() in ('yes', 'true', 'on', 'enable', 'enabled', '1', 'checked')

#返回字符串格式化时间
def time_str(fmt="%Y-%m-%d %H:%M", tz=0):
    return tz_now(tz).strftime(fmt)

#返回datetime实例，包含timezone信息
def tz_now(tz=0):
    return datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=tz)))

#隐藏真实email地址，使用星号代替部分字符
#输入单个email字符串或列表，返回部分隐藏的字符串
def hide_email(email):
    emailList = [email] if isinstance(email, str) else email
    newEmails = []
    for item in emailList:
        if '@' not in item:
            newEmails.append(item)
            continue

        item = item.split('@')
        if len(item[0]) < 4:
            return item[0][0] + '**@' + item[-1]
        to = item[0][0] + '*****' + item[0][-1]
        newEmails.append(to + '@' + item[-1])
    if not newEmails:
        return email
    elif len(newEmails) == 1:
        return newEmails[0]
    else:
        return newEmails

#隐藏真实的网址
def hide_website(site):
    if not site:
        return ''
        
    parts = urlparse(site)
    path = parts.path if parts.path else parts.netloc
    if '.' in path:
        pathArray = path.split('.')
        if len(pathArray[0]) > 4:
            pathArray[0] = pathArray[0][:2] + '**' + pathArray[0][-1]
        else:
            pathArray[0] = pathArray[0][0] + '**'
            pathArray[1] = pathArray[1][0] + '**'
        site = '.'.join(pathArray)
    elif len(path) > 4:
        site = path[:2] + '**' + path[-1]
    else:
        site = path[0] + '**'
    return site

#判断url是否合法
def url_validator(url):
    try:
        parts = urlparse(url)
        return all([parts.scheme, parts.netloc])
    except AttributeError:
        return False

#将字节长度转换为人类友好的字符串，比如 2000 -> 2kB
#value: 字节长度
#binary: 进位是2进制还是10进制
#suffix: 字符串后缀
def filesizeformat(value, binary=False, suffix='B'):
    value = abs(float(value))
    if binary:
        base = 1024
        prefixes = ('', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi', 'Yi')
    else:
        base = 1000
        prefixes = ('', 'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')

    for unit in prefixes:
        if value < base:
            return f"{value:3.1f} {unit}{suffix}" if unit else f"{int(value)} {suffix}"
        value /= base
    return f"{value:.1f} {unit}{suffix}" #type:ignore

#将文件名中的非法字符替换为replace指定的字符
def sanitize_filename(filename, replace=' '):
    for c in ('<', '>', '\\', '/', '?', '*', ':', '|', "'", '"'):
        filename = filename.replace(c, replace)
    return filename

#获取一个目录的中大小
def get_directory_size(directory):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            total_size += os.path.getsize(filepath)
    return total_size

#将字符串安全转义到xml格式，有标准库函数xml.sax.saxutils.escape()，但是简单的功能就简单的函数就好
def xml_escape(txt):
    txt = (txt or '').replace("&", "&amp;")
    txt = txt.replace("<", "&lt;")
    txt = txt.replace(">", "&gt;")
    txt = txt.replace('"', "&quot;")
    txt = txt.replace("'", "&apos;")
    return txt

def xml_unescape(txt):
    txt = (txt or '').replace("&amp;", "&")
    txt = txt.replace("&lt;", "<")
    txt = txt.replace("&gt;", ">")
    txt = txt.replace("&quot;", '"')
    txt = txt.replace("&apos;", "'")
    return txt

#-----------以下为安全相关的工具函数--------------------

#使用此密码管理器逐步将以前的md5哈希的密码迁移到sha256密码
#尽管sha256不是密码哈希算法，但是已经足够好(配合加盐16字节)
#PBKDF2在3.10之后默认不提供，其他更好的bcrypt/scrypt等不是标准库
class PasswordManager:
    def __init__(self, secretKey: str):
        """secretKey: 密码的salt"""
        self.secretKey = secretKey
        #迭代计算次数，大多数免费VPS性能不强，次数太多了影响正常使用体验
        #何况sha256不是专门的密码哈希算法，单纯增加迭代次数带来的安全性提升有限
        self.iterations = 1000
    
    def migrate_password(self, stored_hash: str, password: str) -> str:
        """密码校验和哈希迁移函数，校验成功返回sha256哈希，否则返回空串
        stored_hash: 数据库保存的密码哈希值
        password: 需要校验的密码"""
        password = password or ''
        if len(stored_hash) == 32:  #MD5哈希长度为32，sha256哈希长度为64(base64后44字节)
            pwd_hash = ''
            try:
                pwd_hash = hashlib.md5((password + self.secretKey).encode('utf-8')).hexdigest()
            except Exception as e:
                print(f'PasswordManager migrate_password hash failed: {e}')
            return self.create_hash(password) if pwd_hash == stored_hash else ''
        else:
            return stored_hash if self.verify_password(stored_hash, password) else ''

    def create_hash(self, password: str) -> str:
        """创建密码的sha256哈希结果，返回base64字符串"""
        hash_value = self._sha256_hash(password)
        return base64.b64encode(hash_value).decode('utf-8')

    def verify_password(self, stored_hash: str, password: str) -> bool:
        """使用sha256算法校验密码是否正确
        stored_hash: 数据库保存的密码哈希值
        password: 需要校验的密码"""
        try:
            decoded = base64.b64decode(stored_hash or '')
            return self._sha256_hash(password) == decoded
        except Exception as e:
            print(f'PasswordManager b64decode password failed: {e}')
            return False
        
    def _sha256_hash(self, password: str) -> bytes:
        """计算密码的hash值，返回bytes"""
        result = ((password or '') + self.secretKey).encode('utf-8')
        for _ in range(self.iterations):
            result = hashlib.sha256(result).digest()
        return result

def new_secret_key(length=16):
    """生成一个安全密钥，为了更通用，只包含数字和ASCII大小写字母，不包含特殊字符"""
    allchars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXZYabcdefghijklmnopqrstuvwxyz'
    return ''.join([secrets.choice(allchars) for i in range(length)])

def ke_encrypt(txt: str, key: str):
    """简单可逆加密"""
    return _ke_auth_code(txt, key, 'encode')
    
def ke_decrypt(txt: str, key: str):
    """简单可逆解密"""
    return _ke_auth_code(txt, key, 'decode')

def _ke_auth_code(txt: str, key: str, act: str='decode'):
    if not txt:
        return ''
        
    key = key or ''
    key = hashlib.md5(key.encode('utf-8')).hexdigest()
    keyA = hashlib.md5(key[:16].encode('utf-8')).hexdigest()
    keyB = hashlib.md5(key[16:].encode('utf-8')).hexdigest()
    cryptKey = keyA + hashlib.md5(keyA.encode('utf-8')).hexdigest()
    keyLength = len(cryptKey)
    
    if act == 'decode':
        try:
            txt = base64.urlsafe_b64decode(txt).decode('utf-8')
        except:
            txt = ''
    else:
        txt = hashlib.md5((txt + keyB).encode('utf-8')).hexdigest()[:16] + txt
    stringLength = len(txt)
    
    result = ''
    box = list(range(256))
    rndkey = {}
    for i in range(256):
        rndkey[i] = ord(cryptKey[i % keyLength])
    
    j = 0
    for i in range(256):
        j = (j + box[i] + rndkey[i]) % 256
        tmp = box[i]
        box[i] = box[j]
        box[j] = tmp
    a = j = 0
    for i in range(stringLength):
        a = (a + 1) % 256
        j = (j + box[a]) % 256
        tmp = box[a]
        box[a] = box[j]
        box[j] = tmp
        result += chr(ord(txt[i]) ^ (box[(box[a] + box[j]) % 256]))

    if act == 'decode':
        if result[:16] == hashlib.md5((result[16:] + keyB).encode('utf-8')).hexdigest()[:16]:
            return result[16:]
        else:
            return ''
    else:
        return base64.urlsafe_b64encode(result.encode('utf-8')).decode('utf-8')
