#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Minimal MCP (Model Context Protocol) server protocol layer for KindleEar.
#Implements the stateless subset of the "Streamable HTTP" transport:
#  POST /mcp with a JSON-RPC 2.0 body, reply with "application/json".
#No server->client requests, no SSE stream, no session id, no OAuth.
#The tool/resource/prompt registry lives in mcp_tools.py.
#Author: cdhigh <https://github.com/cdhigh>
import json

MCP_PROTOCOL_VERSION = '2025-06-18'
SUPPORTED_VERSIONS = ('2024-11-05', '2025-03-26', '2025-06-18')

#JSON-RPC 2.0 error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

def _error_resp(id_, code, message, data=None):
    err = {'code': code, 'message': message}
    if data is not None:
        err['data'] = data
    return {'jsonrpc': '2.0', 'id': id_, 'error': err}

def _result_resp(id_, result):
    return {'jsonrpc': '2.0', 'id': id_, 'result': result}

def handle_jsonrpc(body, user):
    """Handle one HTTP request body of the MCP endpoint.
    body: the raw text (or already decoded dict/list) of the request.
    user: the authenticated KeUser instance.
    Returns (resp, http_status):
      resp is a dict (single), a list (batch), or None (notification only -> 202).
    """
    if isinstance(body, (bytes, bytearray)):
        body = body.decode('utf-8', 'replace')
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError as e:
            return _error_resp(None, PARSE_ERROR, 'Parse error', str(e)), 400

    if isinstance(body, list):
        if not body:
            return _error_resp(None, INVALID_REQUEST, 'Invalid Request'), 400
        replies = []
        for item in body:
            resp, _status = _handle_single(item, user)
            if resp is not None:
                replies.append(resp)
        if not replies: #batch of notifications only
            return None, 202
        return (replies[0] if len(replies) == 1 else replies), 200
    elif isinstance(body, dict):
        return _handle_single(body, user)
    else:
        return _error_resp(None, INVALID_REQUEST, 'Invalid Request'), 400

def _handle_single(msg, user):
    if not isinstance(msg, dict):
        return _error_resp(None, INVALID_REQUEST, 'Invalid Request'), 400
    id_ = msg.get('id')
    is_notification = ('id' not in msg) or (id_ is None)
    method = msg.get('method')
    if not isinstance(method, str):
        return _error_resp(id_, INVALID_REQUEST, 'Invalid Request'), 400

    params = msg.get('params')
    if params is not None and not isinstance(params, dict):
        if isinstance(params, list):
            params = {}
        else:
            return _error_resp(id_, INVALID_REQUEST, 'Invalid Request'), 400

    try:
        result = _dispatch(method, params, user)
    except McpError as e:
        return _error_resp(id_, e.code, str(e), e.data), 200
    except Exception as e:
        from application.ke_utils import loc_exc_pos
        default_log.error('[MCP] %s failed: %s', method, loc_exc_pos(method))
        return _error_resp(id_, INTERNAL_ERROR, str(e) or repr(e)), 200

    if is_notification:
        return None, 202
    return _result_resp(id_, result), 200

def _dispatch(method, params, user):
    #lazy import to keep this module importable without the whole app
    from mcp_tools import get_tool_registry, get_resources, read_resource, get_prompts, get_prompt
    if method == 'initialize':
        clientVer = (params or {}).get('protocolVersion')
        version = clientVer if clientVer in SUPPORTED_VERSIONS else MCP_PROTOCOL_VERSION
        return {
            'protocolVersion': version,
            'capabilities': {
                'tools': {'listChanged': False},
                'resources': {'subscribe': False, 'listChanged': False},
                'prompts': {'listChanged': False},
                'logging': {},
            },
            'serverInfo': {'name': 'kindleear', 'title': 'KindleEar', 'version': appVer},
            'instructions': ('KindleEar personal Kindle push service. Tools operate on the account '
                'identified by the Bearer token: subscriptions, delivery, online shelf, '
                'inbound mail, recipe and mail-hook authoring workbench.'),
        }
    elif method == 'notifications/initialized':
        return None
    elif method == 'notifications/cancelled':
        return None
    elif method == 'ping':
        return {}
    elif method == 'logging/setLevel':
        return {}
    elif method == 'tools/list':
        tools = [{'name': t['name'], 'title': t.get('title', ''), 'description': t['description'],
                  'inputSchema': t['inputSchema'], 'annotations': {'readOnlyHint': t['readonly']}}
                 for t in get_tool_registry()]
        return {'tools': tools}
    elif method == 'tools/call':
        return _call_tool(params, user)
    elif method == 'resources/list':
        return {'resources': get_resources()}
    elif method == 'resources/templates/list':
        return {'resourceTemplates': []}
    elif method == 'resources/read':
        uri = (params or {}).get('uri', '')
        contents = read_resource(user, uri)
        return {'contents': contents}
    elif method == 'prompts/list':
        return {'prompts': get_prompts()}
    elif method == 'prompts/get':
        name = (params or {}).get('name', '')
        args = (params or {}).get('arguments') or {}
        return get_prompt(user, name, args)
    else:
        raise McpError(METHOD_NOT_FOUND, f'Method not found: {method}')

def _call_tool(params, user):
    from mcp_tools import get_tool_by_name, ToolWriteForbidden
    name = (params or {}).get('name', '')
    args = (params or {}).get('arguments') or {}
    tool = get_tool_by_name(name)
    if tool is None:
        raise McpError(INVALID_PARAMS, f'Unknown tool: {name}')
    default_log.info('[MCP] user=%s calls tool=%s', user.name, name)
    try:
        if not tool.get('readonly', False) and user.custom.get('mcp_readonly'):
            raise ToolWriteForbidden(name)
        ret = tool['handler'](user, args)
    except ToolWriteForbidden as e:
        return _tool_text({'status': 'error',
            'error': f'This tool is not available because read-only mode is enabled: {e}'}, is_error=True)
    except Exception as e:
        from application.ke_utils import loc_exc_pos
        import traceback as tracebackMod
        default_log.error('[MCP] tool %s failed: %s', name, loc_exc_pos(name))
        return _tool_text({'status': 'error', 'error': str(e) or repr(e),
            'traceback': tracebackMod.format_exc()[-2000:]}, is_error=True)
    return _tool_text(ret)

def _tool_text(data, is_error=False):
    if isinstance(data, str):
        text = data
    else:
        try:
            text = json.dumps(data, ensure_ascii=False, indent=1, default=str)
        except Exception:
            text = str(data)
    result = {'content': [{'type': 'text', 'text': text}]}
    if is_error:
        result['isError'] = True
    return result

class McpError(Exception):
    """JSON-RPC protocol level error raised inside _dispatch."""
    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.code = code
        self.data = data

class ToolWriteForbidden(Exception):
    """A write tool was invoked while the user enabled read-only mode."""
