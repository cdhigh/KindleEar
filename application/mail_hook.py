#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#入站邮件的预处理钩子：用户针对白名单条目上传 MailNewsRecipe 派生类钩子文件，
#收到邮件时根据发件人地址匹配钩子并调用，用于预处理邮件内容、外链提取及反反爬抓取
#Author: cdhigh <https://github.com/cdhigh>
#钩子文件为普通python文件，定义继承自 MailNewsRecipe 的类：
#class MyMailRecipe(MailNewsRecipe):
#    def preprocess_email(self, subject, txtBodies, htmlBodies, attachments):
#        return subject, txtBodies, htmlBodies, attachments
#    def preprocess_soup(self, soup, attachments):
#        return soup, attachments
#    def extract_urls(self, soup):
#        return ['https://...']
import json, inspect, ast
from flask_babel import gettext as _
from .ke_utils import utcnow
from .back_end.db_models import UserBlob
from calibre.web.feeds.news import BasicNewsRecipe, MailNewsRecipe
from flask_babel import gettext as _
from .ke_utils import utcnow
from .back_end.db_models import UserBlob

#钩子源码保存在UserBlob表，name字段为此前缀 + 白名单地址（小写）
HOOK_NAME_PREFIX = 'hook:'

#单个钩子文件的最大字节数，防止意外上传超大文件
MAX_HOOK_FILE_SIZE = 512 * 1024

#将白名单地址转换为保存钩子的UserBlob的name字段
def hook_blob_name(mail):
    return HOOK_NAME_PREFIX + (mail or '').strip().lower()

#获取某个白名单条目对应的钩子UserBlob实例，没有则返回None
def get_mail_hook(user, mail):
    return UserBlob.get_or_none((UserBlob.user == user.name) & (UserBlob.name == hook_blob_name(mail)))

#返回某个白名单条目已经上传的钩子文件名，没有则返回空字符串
def get_mail_hook_filename(user, mail):
    file, _ = load_hook_payload(get_mail_hook(user, mail))
    return file

#保存钩子源码到数据库
def save_mail_hook(user, mail, src, filename):
    data = json.dumps({'file': filename, 'src': src}, ensure_ascii=False).encode('utf-8')
    dbItem = get_mail_hook(user, mail)
    if dbItem:
        dbItem.data = data
        dbItem.time = utcnow()
    else:
        dbItem = UserBlob(name=hook_blob_name(mail), user=user.name, data=data)
    dbItem.save()
    return dbItem

#删除某个白名单条目的钩子，返回是否删除了内容
def delete_mail_hook(user, mail):
    dbItem = get_mail_hook(user, mail)
    if dbItem:
        dbItem.delete_instance()
        return True
    else:
        return False

#根据发件人地址匹配钩子，优先级：完整地址 > @域名 > *，没有则返回None
def match_mail_hook(user, sender):
    sender = (sender or '').strip().lower()
    if not sender or '@' not in sender:
        return None

    host = sender.split('@')[-1]
    for mail in (sender, f'@{host}', '*'):
        dbItem = get_mail_hook(user, mail)
        if dbItem and dbItem.data:
            return dbItem
    return None

#解码UserBlob保存的钩子内容，返回 (文件名, 源码)
def load_hook_payload(dbItem):
    if not dbItem or not dbItem.data:
        return '', ''
    try:
        payload = json.loads(dbItem.data.decode('utf-8'))
        return payload.get('file', ''), payload.get('src', '')
    except Exception: #兼容直接保存的纯源码
        return '', dbItem.data.decode('utf-8', errors='replace')

#钩子代码安全检查：禁止导入的高危模块、危险属性与内置函数
BLOCKED_HOOK_MODULES = {
    'os', 'sys', 'subprocess', 'shutil', 'socket', 'pty', 'commands',
    'importlib', 'ctypes', 'posix', 'nt', 'multiprocessing', 'threading',
    'signal', 'webbrowser', 'pickle', 'shelve', 'builtins', '__builtin__'
}
BLOCKED_HOOK_ATTRS = {
    '__subclasses__', '__bases__', '__globals__', '__code__', '__builtins__'
}
BLOCKED_HOOK_CALLS = {
    'exec', 'eval', 'compile', 'open', 'breakpoint', '__import__'
}

#检查钩子源码语法树，拦截潜在高危行为
def check_hook_ast_safety(src: str):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return  #语法错误交由后面的 compile 统一抛出

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split('.')[0] in BLOCKED_HOOK_MODULES:
                    raise ValueError(_("Forbidden module import in mail hook: {}").format(alias.name))
        elif isinstance(node, ast.ImportFrom):
            if (node.module or '').split('.')[0] in BLOCKED_HOOK_MODULES:
                raise ValueError(_("Forbidden module import in mail hook: {}").format(node.module))
        elif isinstance(node, ast.Attribute):
            if node.attr in BLOCKED_HOOK_ATTRS:
                raise ValueError(_("Forbidden attribute access in mail hook: {}").format(node.attr))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and (node.func.id in BLOCKED_HOOK_CALLS):
                raise ValueError(_("Forbidden function call in mail hook: {}()").format(node.func.id))

#编译并检查钩子源码，返回 MailNewsRecipe 的子类
#源码有语法错误、高危操作或未定义 MailNewsRecipe 子类则抛出异常
def compile_mail_hook(src, filename='hook.py'):
    check_hook_ast_safety(src)
    code = compile(src, filename, 'exec')
    namespace = {
        '__name__': 'mail_hook',
        '__file__': filename,
        'BasicNewsRecipe': BasicNewsRecipe,
        'MailNewsRecipe': MailNewsRecipe,
    }
    exec(code, namespace) #type:ignore #nosec B102 #NOSONAR

    hook_cls = None
    for obj in namespace.values():
        if (inspect.isclass(obj) and issubclass(obj, MailNewsRecipe)
            and obj is not MailNewsRecipe):
            hook_cls = obj
            break

    if not hook_cls:
        raise Exception(_('Cannot find any subclass of MailNewsRecipe in the hook file.'))

    # 检查方法签名
    sigError = _('The signature of {0} is invalid, it should be: def {0}({1})')
    if not _signature_match(hook_cls.preprocess_email, 5): # self + 4 args
        args = 'self, subject, txtBodies, htmlBodies, attachments'
        raise Exception(sigError.format('preprocess_email', args))

    if not _signature_match(hook_cls.preprocess_soup, 3): # self + 2 args
        args = 'self, soup, attachments'
        raise Exception(sigError.format('preprocess_soup', args))

    if not _signature_match(hook_cls.extract_urls, 2): # self + 1 arg
        args = 'self, soup'
        raise Exception(sigError.format('extract_urls', args))

    return hook_cls

#检查函数签名是否可以接收argCount个位置参数
def _signature_match(func, argCount):
    try:
        inspect.signature(func).bind(*([object()] * argCount))
        return True
    except (TypeError, ValueError):
        return False

#加载发件人匹配的钩子类，没有匹配的钩子或编译失败则返回None
def load_mail_hook(user, sender):
    dbItem = match_mail_hook(user, sender)
    if not dbItem:
        return None

    _, src = load_hook_payload(dbItem)
    if not src:
        return None

    try:
        return compile_mail_hook(src, hook_blob_name(sender))
    except Exception as e:
        default_log.warning(f'Failed to load mail hook [{sender}]: {e}')
        return None

#调用钩子预处理原始邮件，返回 (subject, txtBodies, htmlBodies, attachments)
def run_mail_preprocess_email(user, sender, to, subject, txtBodies, htmlBodies, attachments):
    hook_cls = load_mail_hook(user, sender)
    if not hook_cls:
        return subject, txtBodies, htmlBodies, attachments

    try:
        hook = hook_cls()
        hook.sender = sender
        hook.to = to
        ret = hook.preprocess_email(subject, txtBodies, htmlBodies, attachments)
        if isinstance(ret, (tuple, list)) and len(ret) == 4:
            subject, txtBodies, htmlBodies, attachments = ret
    except Exception as e:
        default_log.warning(f'Mail hook preprocess_email failed [{sender}]: {e}')

    return subject, txtBodies, htmlBodies, attachments

#调用钩子预处理邮件正文soup和提取外链，返回 (soup, attachments, urls)
def run_mail_preprocess_soup(user, sender, to, soup, attachments):
    urls = []
    hook_cls = load_mail_hook(user, sender)
    if not hook_cls:
        return soup, attachments, urls

    try:
        hook = hook_cls()
        hook.sender = sender
        hook.to = to

        # 1. preprocess_soup
        ret = hook.preprocess_soup(soup, attachments)
        if ret is not None:
            if isinstance(ret, (tuple, list)):
                if len(ret) == 2:
                    soup, attachments = ret
                elif len(ret) == 3:
                    soup, attachments, urls = ret
                elif len(ret) == 1:
                    soup = ret[0]
            else:
                soup = ret

        # 2. extract_urls（如果 preprocess_soup 没通过 3 元组直接返回 urls）
        if not urls and callable(getattr(hook, 'extract_urls', None)):
            ret_urls = hook.extract_urls(soup)
            if isinstance(ret_urls, (list, tuple)):
                urls = list(ret_urls)

        # 3. 检查 hook.urls 属性（如果用户在方法内直接设置了 self.urls）
        if not urls and getattr(hook, 'urls', None):
            urls = list(hook.urls)
    except Exception as e:
        default_log.warning(f'Mail hook preprocess_soup failed [{sender}]: {e}')

    return soup, attachments, urls

