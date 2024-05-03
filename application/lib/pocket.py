#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pocketd V3 API封装，使用OAuth 2.0
Author: cdhigh
用法：
Step 1: Obtain a platform consumer key
Step 2: Obtain a request token
Step 3: Redirect user to Pocket to continue authorization
Step 4: Receive the callback from Pocket
Step 5: Convert a request token into a Pocket access token
Step 6: Make authenticated requests to Pocket
===================================================
@app.route('/auth')
def auth():
    pocket = Pocket(POCKET_CONSUMER_KEY, CALLBACK_URL)
    try:
        code = pocket.get_request_token()
        url = pocket.get_authorize_url(code)
    except APIError as e:
        return str(e)
    session.pop('code', None)
    session['code'] = code # store request token (code) for getting access token
    return redirect(url)

@app.route('/auth_callback')
def auth_callback():
    pocket = Pocket(POCKET_CONSUMER_KEY)
    code = session['code']
    try:
        resp = pocket.get_access_token(code)
        session.pop('access_token', None)
        session['access_token'] = resp['access_token'] #store access token in session for api call
    except APIError as e:
        return str(e)
===================================================
pocket = Pocket(POCKET_CONSUMER_KEY)
pocket.set_access_token(session['access_token'])
items = pocket.get(count=5, favorite=1, state='archive')
return json.dumps(items)
item = pocket.add(url='http://getpocket.com/developer/docs/authentication')
return json.dumps(item)
"""

import json
from urlopener import UrlOpener

class APIError(Exception):
    def __init__(self, status_code, x_error_code, x_error, request):
        self.status_code = status_code
        self.x_error_code = x_error_code
        self.x_error = x_error
        self.request = request
        super().__init__(x_error)
        
    def __str__(self):
        #APIError: HTTP Status:403, X-Error-Code:158, X-Error:"User rejected code.", request: Get access token
        return ('APIError: HTTP Status:{}, X-Error-Code:{}, X-Error:"{}", request: {}'.
            format(self.status_code, self.x_error_code, self.x_error, self.request))

class Pocket(object):
    REQUEST_TOKEN_URL = 'https://getpocket.com/v3/oauth/request'
    AUTH_TOKEN_URL = 'https://getpocket.com/auth/authorize?request_token={}&redirect_uri={}'
    ACCESS_TOKEN_URL = 'https://getpocket.com/v3/oauth/authorize'

    POCKET_HEADERS = {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Accept': 'application/json'
    }

    def __init__(self, consumer_key, redirect_uri=None):
        self.consumer_key = str(consumer_key)
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.opener = UrlOpener(headers=self.POCKET_HEADERS)
        
    def _post(self, method_url, act, **kw):
        ret = self.opener.open(method_url, data=kw)
        if ret.status_code > 399:
            raise APIError(ret.status_code, ret.headers.get('X-Error-Code',''), ret.headers.get('X-Error',''), act)

        try:
            return json.loads(ret.content)
        except:
            return json.text
        
    def _authenticated_post(self, method_url, act, **kw):
        kw['consumer_key'] = self.consumer_key
        kw['access_token'] = self.access_token
        return self._post(method_url, act, **kw)

    def get_request_token(self):
        #此步仅用来直接通过一次http获取一个request_token(code)，pocket不会回调redirect_uri
        ret = self._post(self.REQUEST_TOKEN_URL, 'get request token', consumer_key=self.consumer_key, redirect_uri=self.redirect_uri)
        return ret.get('code', '') if isinstance(ret, dict) else ret.split('=')[-1]
        
    def get_authorize_url(self, code):
        if not self.redirect_uri:
            raise APIError(400, '140', 'Missing redirect url.', 'Get access token')
        return self.AUTH_TOKEN_URL.format(code, self.redirect_uri)
        
    def get_access_token(self, code):
        # access token : {"access_token":"dcba4321-dcba-4321-dcba-4321dc","username":"pocketuser"}.
        ret = self._post(self.ACCESS_TOKEN_URL, 'get access token', consumer_key=self.consumer_key, code=code)
        self.access_token = ret.get('access_token', '')
        return self.access_token

    def set_access_token(self, access_token):
        self.access_token = str(access_token)

    def add(self, **kw):
        #需要的参数：
        #url ： 要保存的URL，最好先urlencode
        #title  : 可选，如果保存的是一个图片或PDF，则需要，否则不需要
        #tags : 可选，逗号分隔的字符串列表
        #tweet_id  ： 可选，用于发推的ID
        #返回一个字典，包含的键可能有：https://getpocket.com/developer/docs/v3/add
        return self._authenticated_post('https://getpocket.com/v3/add', 'add an entry', **kw)

    def get(self, **kw):
        return self._authenticated_post('https://getpocket.com/v3/get', 'get an entry', **kw)

    def modify(self, **kw):
        pass


