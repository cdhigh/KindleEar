#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#MCP (Model Context Protocol) server endpoint for KindleEar.
#Streamable HTTP transport, stateless JSON mode: POST /mcp with JSON-RPC 2.0,
#authenticated by a per-user Bearer token (user.custom['mcp_token']).
#Author: cdhigh <https://github.com/cdhigh>
import json
from flask import Blueprint, request, jsonify, make_response, current_app as app
from flask_babel import gettext as _
from ..base_handler import login_required, get_login_user
from ..back_end.db_models import *
from ..ke_utils import new_secret_key, str_to_bool

bpMcp = Blueprint('bpMcp', __name__)

#解析Authorization头部，返回token或None
def _bearer_token():
    header = request.headers.get('Authorization', '') or request.headers.get('authorization', '')
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        return parts[1].strip()
    return None

def _find_user_by_token(token):
    if not token:
        return None
    for user in KeUser.get_all():
        if user.custom.get('mcp_token') == token:
            return user
    return None

def _jsonrpc_response(payload, status=200):
    resp = make_response(jsonify(payload) if payload is not None else '', status)
    resp.headers['Content-Type'] = 'application/json'
    return resp

#MCP协议端点
@bpMcp.route('/mcp', methods=['POST', 'GET', 'DELETE'])
def McpRoute():
    if request.method != 'POST':
        resp = make_response('', 405)
        resp.headers['Allow'] = 'POST'
        resp.headers['MCP-Protocol-Version'] = '2025-06-18'
        return resp

    from application.lib.mcp_protocol import handle_jsonrpc

    user = _find_user_by_token(_bearer_token())
    if user is None or not user.custom.get('mcp_enabled'):
        return _jsonrpc_response({'jsonrpc': '2.0', 'id': None,
            'error': {'code': -32000, 'message': 'Unauthorized: missing token or MCP server disabled.'}}, 401)

    resp, status = handle_jsonrpc(request.get_data(), user)
    return _jsonrpc_response(resp, status)

#生成/重置MCP访问令牌（吊销由"启用 MCP 服务器"开关承担）
@bpMcp.post('/mcp/token', endpoint='McpTokenPost')
@login_required(forAjax=True)
def McpTokenPost(user: KeUser):
    token = new_secret_key(32)
    user.set_custom('mcp_token', token)
    user.save()
    return {'status': 'ok', 'token': token}

#MCP服务器设置页（高级设置子页面）
@bpMcp.route('/advanced/mcp', endpoint='McpAdvPage', methods=['GET', 'POST'])
@login_required()
def McpAdvPage(user: KeUser):
    tips = ''
    if request.method == 'POST':
        user.set_custom('mcp_enabled', str_to_bool(request.form.get('mcp_enabled', '')))
        user.set_custom('mcp_readonly', str_to_bool(request.form.get('mcp_readonly', '')))
        user.save()
        tips = _("Settings Saved!")

    from .adv import adv_render_template
    endpointUrl = request.url_root.rstrip('/') + '/mcp'
    clientConfig = json.dumps({'mcpServers': {'kindleear': {
        'url': endpointUrl,
        'headers': {'Authorization': 'Bearer ' + (user.custom.get('mcp_token') or '<MCP Token>')}}}},
        indent=2)
    return adv_render_template('adv_mcp.html', 'mcp', user=user, tips=tips,
        endpointUrl=endpointUrl, clientConfig=clientConfig)
