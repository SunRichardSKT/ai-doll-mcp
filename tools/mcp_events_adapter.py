"""MCP 2.0 event adapter; existing STDIO and embedded MCU protocol stay intact.

Hosted access/authentication is supplied by the user's authenticated gateway or
Secure MCP Tunnel. This loopback service does not publish itself to the internet.
"""
import datetime as dt
import hashlib
import json
from webhook_delivery import WebhookSender, decode_secret, validate_url

PROTOCOL = '2026-07-28'
EVENT_NAME = 'doll.interaction'
EVENT_ARGUMENTS = dict(type='object', properties={
    'device_id': {'type':'string'}, 'session_id': {'type':'string'},
    'channels': {'type':'array','items':{'type':'integer','minimum':0,'maximum':15},'uniqueItems':True,'minItems':1,'maxItems':16}
}, required=['device_id','session_id'], additionalProperties=False)
EVENT_DEFINITION = dict(name=EVENT_NAME,
    description='New user pressure inputs during an explicitly started interaction session. Call start_interaction first, then use its id and doll_get_status device_id. Simulation is labelled; output commands never trigger this event. Optional temperature triggers follow user preferences.',
    delivery=['webhook'], inputSchema=EVENT_ARGUMENTS,
    payloadSchema=dict(type='object', properties={
        'device_id': {'type':'string'}, 'session_id': {'type':'string'},
        'events': {'type':'array','items':{'type':'object'}},
        'feedback': {'type':'object'}, 'persona': {'type':'string'}, 'summary': {'type':'object'}
    }, required=['device_id','session_id','events','feedback','persona'], additionalProperties=False))


class RPCError(ValueError):
    def __init__(self, code, message, reason=None):
        super().__init__(message); self.code, self.reason = code, reason


class MCPEventsAdapter:
    def __init__(self, companion, tool_provider, sender=None):
        self.c = companion; self.tools = tool_provider; self.sender = sender or WebhookSender()

    def identity(self, params, owner):
        if params.get('name') != EVENT_NAME: raise ValueError('Unsupported event')
        args, delivery = params.get('arguments'), params.get('delivery')
        if not isinstance(args, dict) or set(args)-{'device_id','session_id','channels'}:
            raise ValueError('Invalid event arguments')
        for k in ['device_id','session_id']:
            if not isinstance(args.get(k), str) or not 1 <= len(args[k]) <= 128:
                raise ValueError(k+' required')
        channels = args.get('channels')
        if channels is not None and (not isinstance(channels,list) or not channels or len(channels)>16 or
            any(type(ch) is not int or not 0<=ch<=15 for ch in channels) or len(set(channels))!=len(channels)):
            raise ValueError('channels must be unique IDs 0..15')
        if not isinstance(delivery,dict): raise ValueError('Webhook delivery required')
        url = delivery.get('url'); validate_url(url, resolve=False)
        canonical = json.dumps(args, sort_keys=True, separators=(',', ':'))
        sid = 'sub_'+hashlib.sha256((owner+'\n'+url+'\n'+EVENT_NAME+'\n'+canonical).encode()).hexdigest()
        return args, delivery, sid

    def execute(self, method, params, owner):
        if method == 'server/discover':
            return dict(supportedVersions=[PROTOCOL], capabilities=dict(tools={},events={}),
                        serverInfo=dict(name='ai-doll-event-bridge',version='2.8.0'))
        if method == 'ping': return {}
        if method == 'events/list':
            return dict(events=[EVENT_DEFINITION])
        if method == 'tools/list': return dict(tools=self.tools())
        if method == 'tools/call':
            try:
                from jsonschema import Draft202012Validator
                name = params.get('name')
                tool = next((t for t in self.tools() if t['name']==name),None)
                if tool is None: raise ValueError('Unknown tool')
                arguments=params.get('arguments',{})
                if not Draft202012Validator(tool['inputSchema']).is_valid(arguments):raise ValueError('Invalid tool arguments')
                data = self.c.call(name, arguments)
                return dict(content=[dict(type='text',text=json.dumps(data,ensure_ascii=False))],structuredContent=data,isError=False)
            except (ValueError,TypeError):
                return dict(content=[dict(type='text',text='Tool arguments or state invalid; check the tool schema and active session.')],isError=True)
        if method in ('events/subscribe','events/unsubscribe'):
            args, delivery, sid = self.identity(params, owner)
            if method == 'events/unsubscribe':
                self.c.bridge.unsubscribe(owner, sid); return {}
            if delivery.get('mode') != 'webhook': raise ValueError('Only webhook delivery is implemented')
            if params.get('cursor') is not None: raise ValueError('Live subscriptions do not replay history; cursor must be null')
            ttl_ms = params.get('ttlMs',300000)
            if ttl_ms is None: ttl_ms = 3600000  # Finite lifetime; never claim permanent monitoring.
            if type(ttl_ms) is not int or not 1000 <= ttl_ms <= 86400000:
                raise ValueError('ttlMs must be 1000..86400000 or null')
            ttl = min(3600, ttl_ms/1000)
            secret = delivery.get('secret'); decode_secret(secret)
            status = self.c.device('doll_get_status',{})
            if args['device_id'] != status['device_id']: raise ValueError('Device not owned by this installation')
            with self.c.lock:
                current = self.c.active()
                if not current or current['id'] != args['session_id']:
                    raise ValueError('The requested interaction session is not active')
                existing = self.c.db.execute('SELECT id FROM bridge_subscriptions WHERE active=1 AND id<>?', (sid,)).fetchone()
                if existing: raise ValueError('Unsubscribe the current reply target first')
            try: self.sender.verify(delivery['url'],secret,sid)
            except Exception: raise RPCError(-32015,'Callback verification failed','challenge_failed') from None
            sub = self.c.bridge.subscribe(owner, 'mcp-events:'+sid, args['session_id'],args['device_id'],
                transport='webhook',ttl_sec=ttl,subscription_id=sid,callback=delivery['url'],secret=secret,arguments=args)
            return dict(id=sid,refreshBefore=dt.datetime.fromtimestamp(sub['expires'],dt.timezone.utc).isoformat(),cursor=None,truncated=False)
        raise RPCError(-32601,'Method not found')

    def rpc(self, request, owner='local-owner', protocol_header=None):
        response = {'jsonrpc':'2.0','id':request.get('id') if isinstance(request,dict) else None}
        try:
            if (not isinstance(request,dict) or request.get('jsonrpc')!='2.0' or
                type(request.get('id')) not in (int,str) or not isinstance(request.get('method'),str)):
                raise RPCError(-32600,'Invalid JSON-RPC request')
            params = request.get('params',{})
            if not isinstance(params,dict): raise ValueError('params must be object')
            meta = params.get('_meta',{})
            if not isinstance(meta,dict): raise ValueError('_meta must be object')
            version = meta.get('io.modelcontextprotocol/protocolVersion')
            if protocol_header and version and protocol_header != version:
                raise RPCError(-32020,'Protocol header and metadata mismatch')
            if request['method']!='server/discover' and (version or protocol_header) != PROTOCOL:
                raise RPCError(-32022,'Use per-request protocol metadata 2026-07-28')
            result = self.execute(request['method'],params,owner)
            response['result'] = dict(resultType='complete',**result)
        except RPCError as exc:
            response['error'] = dict(code=exc.code,message=str(exc))
            if exc.reason: response['error']['data'] = dict(reason=exc.reason)
        except (ValueError,TypeError):
            response['error'] = dict(code=-32602,message='Invalid arguments or subscription state')
        except Exception:
            response['error'] = dict(code=-32603,message='Bridge temporarily unavailable')
        return response
