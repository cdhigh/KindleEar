#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pocketd V3 API封装，使用OAuth 2.
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

try:
    import json
except ImportError:
    import simplejson as json

from lib.urlopener import URLOpener

class APIError(StandardError):
    def __init__(self, status_code, x_error_code, x_error, request):
        self.status_code = status_code
        self.x_error_code = x_error_code
        self.x_error = x_error
        self.request = request
        StandardError.__init__(self, x_error)
        
    def __str__(self):
        #APIError: HTTP Status:403, X-Error-Code:158, X-Error:"User rejected code.", request: Get access token
        return 'APIError: HTTP Status:%d, X-Error-Code:%s, X-Error:"%s", request: %s' \
            % (self.status_code, self.x_error_code, self.x_error, self.request)

REQUEST_TOKEN_URL = 'https://getpocket.com/v3/oauth/request'
AUTH_TOKEN_URL = 'https://getpocket.com/auth/authorize?request_token=%(request_token)s&redirect_uri=%(redirect_uri)s'
ACCESS_TOKEN_URL = 'https://getpocket.com/v3/oauth/authorize'

POCKET_HEADERS = {
    'Content-Type': 'application/json; charset=UTF-8',
    'X-Accept': 'application/json'
}

class Pocket(object):
    def __init__(self, consumer_key, redirect_uri=None):
        self.consumer_key = str(consumer_key)
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.opener = URLOpener(headers=POCKET_HEADERS)
        
    def _post(self, method_url, **kw):
        ret = self.opener.open(method_url, data=json.dumps(kw))
        if ret.status_code != 200 or not ret.content:
            raise APIError(ret.status_code, ret.headers.get('X-Error-Code',''), ret.headers.get('X-Error',''), 'Get access token')
        return json.loads(ret.content)
        
    def _authenticated_post(self, method_url, **kw):
        kw['consumer_key'] = self.consumer_key
        kw['access_token'] = self.access_token
        return self._post(method_url, **kw)

    def get_request_token(self):
        #此步仅用来直接通过一次http获取一个request_token(code)，pocket不会回调redirect_uri
        ret = self._post(REQUEST_TOKEN_URL, consumer_key=self.consumer_key, redirect_uri=self.redirect_uri)
        return ret.get('code', '')
        
    def get_authorize_url(self, code):
        if not self.redirect_uri:
            raise APIError(400, '140', 'Missing redirect url.', 'Get access token')
        url = AUTH_TOKEN_URL % {'request_token' : code, 'redirect_uri' : self.redirect_uri}
        return url
        
    def get_access_token(self, code):
        # access token : {"access_token":"dcba4321-dcba-4321-dcba-4321dc","username":"pocketuser"}.
        ret = self._post(ACCESS_TOKEN_URL, consumer_key=self.consumer_key, code=code)
        self.access_token = ret.get('access_token', '')
        return ret

    def set_access_token(self, access_token):
        self.access_token = str(access_token)

    def add(self, **kw):
        #需要的参数：
        #url ： 要保存的URL，最好先urlencode
        #title  : 可选，如果保存的是一个图片或PDF，则需要，否则不需要
        #tags : 可选，逗号分隔的字符串列表
        #tweet_id  ： 可选，用于发推的ID
        #返回一个字典，包含的键可能有：https://getpocket.com/developer/docs/v3/add
        return self._authenticated_post('https://getpocket.com/v3/add', **kw)

    def get(self, **kw):
        return self._authenticated_post('https://getpocket.com/v3/get', **kw)

    def modify(self, **kw):
        pass


