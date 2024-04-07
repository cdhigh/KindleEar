#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Wallabag api，实现添加一个条目到wallabag
#Wallabag 官方主机：https://app.wallabag.it
from urllib.parse import urljoin
from urlopener import UrlOpener

class WallaBag:
    ALLOW_EXTENSIONS = ('json', 'xml', 'txt', 'csv', 'pdf', 'epub', 'mobi', 'html')

    #config是一个字典，包含键 host, client_id, client_secret, username, password, 
    #access_token, refresh_token
    def __init__(self, config, log, extension='json'):
        for item in ['host', 'client_id', 'client_secret', 'username', 'password']:
            config.setdefault(item, '') #保证每个元素都存在
        self.config = config
        assert(extension in self.ALLOW_EXTENSIONS)
        self.extension = extension
        self.log = log
        self.opener = UrlOpener()

    #添加一个条目到 WallaBag
    #url ： 要保存的URL，最好先urlencode
    #title  : 可选，如果保存的是一个图片或PDF，则需要，否则不需要
    #tags : 可选，逗号分隔的字符串列表
    #archive: 0/1 - 条目已存档
    #starred: 0/1 - 条目已加星标
    #content: 如果不需要wallbag联网获取url的内容，可以使用此参数传递，同时title/url也不能为空
    #language: 语言种类
    #published_at: 发布日期，$YYYY-MM-DDTHH:II:SS+TZ 或整数时间戳
    #authors: 逗号分割的作者名字字符串
    #public: 0/1 - 是否创建用于公开分享的链接
    #origin_url: 原始地址，可以和url相同
    #返回字典：{'msg': , 'changed': , 'resp': }
    #如果成功，resp保存服务器返回的json，msg为空，changed只是token是否有变化
    #失败时msg保存失败描述
    def add(self, url, **kwargs):
        ret = {'msg': '', 'changed': False, 'resp': None}
        kwargs['url'] = url
        resp, need_get_token = self._add_entry(kwargs)
        
        if need_get_token: #重新获取access token
            self.log.debug('Updating wallabag token')
            msg = self.update_token()
            if not msg:
                self.log.info('Refreshed wallabag token')
                ret['changed'] = True
                resp, _ = self._add_entry(kwargs) #重新执行
            else:
                ret['msg'] = msg
        elif not resp:
            ret['msg'] = 'No server response or non-JSON format returned.'

        ret['resp'] = resp
        return ret
        
    #更新token，包括access_token/refresh_token
    #如果失败，返回错误描述字符串，否则返回空串
    def update_token(self):
        c = self.config
        url = urljoin(c["host"], '/oauth/v2/token')
        data1 = {'username': c['username'], 'password': c['password'], 'client_id': c['client_id'],
            'client_secret': c['client_secret'], 'grant_type': 'password'}
        data2 = {'client_id': c['client_id'], 'client_secret': c['client_secret'], 
            'refresh_token': c.get('refresh_token', ''), 'grant_type': 'refresh_token'}
        
        errors = []
        dataList = [data2, data1] if c.get('refresh_token') else [data1]
        for data in dataList:
            try:
                resp = self.opener.open(url, data=data)
            except Exception as e:
                msg = 'Error while getting token using {}: {}'.format(data['grant_type'], str(e))
                self.log.warning(msg)
                errors.append(msg)
                continue

            if resp.status_code < 400:
                respDict = resp.json()
                if isinstance(respDict, dict):
                    self.config['access_token'] = respDict.get('access_token', '')
                    self.config['refresh_token'] = respDict.get('refresh_token', '')
                    return '' #任何一个成功就返回
            else:
                msg = 'Error while getting token using {}: {}'.format(data['grant_type'], resp.status_code)
                self.log.warning(msg)
                errors.append(msg)

        return '\n'.join(errors)

    #将一个url添加到wallabag
    #data: 为一个字典
    #返回 resp, need_get_token
    def _add_entry(self, data):
        access_token = self.config.get('access_token', '')
        if not access_token:
            return None, True

        headers = {'Authorization': f'Bearer {access_token}'}
        
        wallaUrl = urljoin(self.config['host'], f'/api/entries.{self.extension}')
        try:
            resp = self.opener.open(wallaUrl, headers=headers, data=data)
        except Exception as e:
            self.log.error('Error adding url: {}'.format(str(e)))
            return None, False

        self.log.debug('add url to wallabag get Resp: {}, {}'.format(resp.status_code, resp.text))
        if resp.status_code >= 400:
            return None, (resp.status_code == 401)
        else:
            return resp.json(), False

