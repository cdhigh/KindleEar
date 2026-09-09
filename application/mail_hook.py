#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#入站邮件的预处理钩子：用户针对白名单条目上传python钩子文件（类似recipe），
#收到邮件时根据发件人地址匹配钩子并调用，用于预处理邮件内容或附件
#Author: cdhigh <https://github.com/cdhigh>
#钩子文件为普通python文件，至少定义下面两个钩子函数之一，函数可以原地修改参数：
#def hook_email(sender, to, subject, txtBodies, htmlBodies, attachments):
#    参数与ReceiveMailImpl()一致，在解析邮件之前调用，
#    返回None或(subject, txtBodies, htmlBodies, attachments)
#def hook_email_soup(sender, to, soup, attachments):
#    soup为BeautifulSoup实例，在邮件正文转换为soup之后调用，
#    返回None或(soup, attachments)
#sender/to为字符串，subject为字符串，txtBodies/htmlBodies为字符串列表，
#attachments为[(fileName, bytes),...]，soup为BeautifulSoup实例
import json, inspect, ast
from flask_babel import gettext as _
from .ke_utils import utcnow
from .back_end.db_models import UserBlob

#钩子文件支持的钩子函数名
HOOK_FULL_FUNC_NAME = 'hook_email'
HOOK_SOUP_FUNC_NAME = 'hook_email_soup'

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

#编译并简单执行钩子源码以检查错误，返回一个 {钩子函数名: 函数} 字典
#源码有语法错误、模块级代码有运行错误、没有定义任何钩子函数或函数签名不匹配则抛出异常
def compile_mail_hook(src, filename='hook.py'):
    check_hook_ast_safety(src)
    code = compile(src, filename, 'exec')
    namespace = {'__name__': 'mail_hook', '__file__': filename}
    #namespace未包含__builtins__时，exec会自动注入内置模块，钩子代码可以正常import任何库
    exec(code, namespace) #type:ignore #nosec B102 #NOSONAR

    hooks = {}
    func = namespace.get(HOOK_FULL_FUNC_NAME)
    if callable(func):
        if not _signature_match(func, 6):
            args = 'sender, to, subject, txtBodies, htmlBodies, attachments'
            raise Exception(_('The signature of {}() is invalid, it should be: def {}({})').format(
                HOOK_FULL_FUNC_NAME, HOOK_FULL_FUNC_NAME, args))
        hooks[HOOK_FULL_FUNC_NAME] = func

    func = namespace.get(HOOK_SOUP_FUNC_NAME)
    if callable(func):
        if not _signature_match(func, 4):
            args = 'sender, to, soup, attachments'
            raise Exception(_('The signature of {}() is invalid, it should be: def {}({})').format(
                HOOK_SOUP_FUNC_NAME, HOOK_SOUP_FUNC_NAME, args))
        hooks[HOOK_SOUP_FUNC_NAME] = func
        
    if not hooks:
        raise Exception(_('Cannot find the function {} or {} in the hook file.').format(
            HOOK_FULL_FUNC_NAME, HOOK_SOUP_FUNC_NAME))
    return hooks

#检查函数签名是否可以接收argCount个位置参数
def _signature_match(func, argCount):
    try:
        inspect.signature(func).bind(*([object()] * argCount))
        return True
    except (TypeError, ValueError): #ValueError: 无法解析的签名，比如某些内置函数，放行
        return False

#加载并执行钩子源码，返回指定名称的钩子函数，没有匹配的钩子或执行失败则返回None
def _load_hook_func(user, sender, name):
    dbItem = match_mail_hook(user, sender)
    if not dbItem:
        return None

    _, src = load_hook_payload(dbItem)
    if not src:
        return None

    try:
        check_hook_ast_safety(src)
        namespace = {'__name__': 'mail_hook'}
        #namespace未包含__builtins__时，exec会自动注入内置模块，钩子代码可以正常import任何库
        exec(compile(src, hook_blob_name(sender), 'exec'), namespace) #type:ignore #nosec B102 #NOSONAR
        return namespace.get(name) if callable(namespace.get(name)) else None
    except Exception as e:
        default_log.warning(f'Failed to run the mail hook [{sender}]: {e}')
        return None

#调用完整签名钩子函数预处理邮件，返回 (subject, txtBodies, htmlBodies, attachments)
#钩子函数可以原地修改参数，也可以返回一个修改后的元组，出现错误则记录日志并不影响邮件处理流程
def run_mail_hook(user, sender, to, subject, txtBodies, htmlBodies, attachments):
    try:
        func = _load_hook_func(user, sender, HOOK_FULL_FUNC_NAME)
        if func:
            ret = func(sender, to, subject, txtBodies, htmlBodies, attachments)
            if isinstance(ret, (tuple, list)) and (len(ret) == 4):
                subject, txtBodies, htmlBodies, attachments = ret
    except Exception as e:
        default_log.warning(f'The mail hook {HOOK_FULL_FUNC_NAME} failed: {e}')
    return subject, txtBodies, htmlBodies, attachments

#调用内容签名钩子函数处理邮件正文soup和附件，返回 (soup, attachments)
def run_mail_content_hook(user, sender, to, soup, attachments):
    try:
        func = _load_hook_func(user, sender, HOOK_SOUP_FUNC_NAME)
        if func:
            ret = func(sender, to, soup, attachments)
            if isinstance(ret, (tuple, list)) and (len(ret) == 2):
                soup, attachments = ret
    except Exception as e:
        default_log.warning(f'The mail hook {HOOK_SOUP_FUNC_NAME} failed: {e}')
    return soup, attachments
