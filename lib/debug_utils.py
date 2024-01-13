#!usr/bin/Python
# -*- coding:utf-8 -*-
from lib.urlopener import UrlOpener

#几个调试工具函数
#将抓取的网页发到自己邮箱进行调试
def debug_mail(content, name='page.html'):
    from google.appengine.api import mail
    mail.send_mail(SRC_EMAIL, SRC_EMAIL, "KindleEar Debug", "KindlerEar",
        attachments=[(name, content),])

#抓取网页，发送到自己邮箱，用于调试目的
def debug_fetch(url, name='page.html'):
    if not name:
        name = 'page.html'
    opener = UrlOpener()
    result = opener.open(url)
    if result.status_code == 200 and result.content:
        debug_mail(result.content, name)
    else:
        default_log.warning('debug_fetch failed: code:%d, url:%s' % (result.status_code, url))

#本地调试使用，在本地创建一个FTP服务器后，将调试文件通过FTP保存到本地
#因为只是调试使用，所以就没有那么复杂的处理了，要提前保证目标目录存在
def debug_save_ftp(content, name='page.html', root='', server='127.0.0.1', port=21, username='', password=''):
    import ftplib
    ftp = ftplib.FTP()
    ftp.set_debuglevel(0)  #打开调试级别2，显示详细信息; 0为关闭调试信息
    ftp.connect(server, port, 60)  #FTP主机 端口 超时时间
    ftp.login(username, password)  #登录，如果匿名登录则用空串代替即可
    
    if root:
        rootList = root.replace('\\', '/').split('/')
        for dirName in rootList:
            if dirName:
                ftp.cwd(dirName)
    
    #为简单起见，就不删除FTP服务器的同名文件，取而代之的就是将当前时间附加到文件名后
    name = name.replace('.', datetime.datetime.now().strftime('_%H_%M_%S.'))
    ftp.storbinary('STOR %s' % name, StringIO(content))
    ftp.set_debuglevel(0)
    ftp.quit()
