"""Private-address Streamable HTTP MCP. No account, password, or OAuth login."""
import argparse
import asyncio
import datetime as dt
import hmac
import json
import logging
from pathlib import Path
import re
import secrets
import threading
import uuid
from urllib.parse import urlsplit

from chat_mcp_gateway import create_gateway, normalize_public_origin, ROOT, PROFILES
from private_storage import write_json, private_directory
from service_lifecycle import ServiceLease
from mcp.server.transport_security import TransportSecurityMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CapabilityStore:
    def __init__(self, folder, allow_corrupt=False):
        self.folder = private_directory(folder)
        self.path = self.folder / 'address-private.json'
        with ServiceLease(self.folder / 'address.lock'):
            if not self.path.exists():
                self._new_key()
            if not allow_corrupt:self.key()

    def _new_key(self):
        write_json(self.path, {'schema': 1, 'key': secrets.token_hex(32)})

    def key(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            value = data['key']
            if data['schema'] != 1 or not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
                raise ValueError()
            return value
        except (KeyError, ValueError, OSError):
            raise RuntimeError('Private address state unavailable; restore it or explicitly reset the address') from None

    def reset(self):
        with ServiceLease(self.folder / 'address.lock'):
            self._new_key()

    def url(self, origin):
        return normalize_public_origin(origin)+'/'+self.key()+'/mcp'

    def local_url(self, host, port):
        import ipaddress
        address = ipaddress.ip_address(host)
        if (not address.is_private or address.is_unspecified or address.is_multicast
                or address.is_link_local or address.is_reserved or type(port) is not int
                or not 1024 <= port <= 65535):
            raise ValueError('A specific LAN/loopback IP and valid port are required')
        authority = ('['+host+']' if address.version == 6 else host)+':'+str(port)
        return 'http://'+authority+'/'+self.key()+'/mcp'


class PrivateAddressGate:
    """Reject before MCP discovery. Read persisted key each request for immediate rotation."""
    def __init__(self, app, store, transport_security):
        self.app, self.store = app, store
        self.security = TransportSecurityMiddleware(transport_security)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        try:
            expected = ('/'+self.store.key()+'/mcp').encode('ascii')
            offered = scope.get('raw_path', scope.get('path','').encode('utf-8'))
            accepted = hmac.compare_digest(offered, expected) and not scope.get('query_string')
        except RuntimeError:
            accepted = False
        if not accepted:
            return await Response(status_code=404, headers={'Cache-Control': 'no-store'})(scope, receive, send)
        scope = dict(scope, path='/mcp', raw_path=b'/mcp')
        async def private_send(message):
            if message['type'] == 'http.response.start':
                message = dict(message, headers=list(message.get('headers',[]))+[(b'cache-control',b'no-store')])
            await send(message)
        if scope.get('method') == 'GET':
            # This JSON-only service has no server-initiated SSE notifications.
            # Validate the same SDK Host/Origin rules before refusing GET.
            response = await self.security.validate_request(Request(scope, receive))
            if response is None:
                response = Response(status_code=405, headers={'Allow':'POST'})
            return await response(scope, receive, private_send)
        return await self.app(scope, receive, private_send)


class ConnectionDiagnostics:
    """Bounded private transport evidence, with no URLs, credentials or payloads."""
    RPC_METHODS = frozenset({'initialize', 'notifications/initialized', 'tools/list',
                            'tools/call', 'prompts/list', 'prompts/get',
                            'resources/list', 'resources/templates/list', 'resources/read', 'ping'})

    def __init__(self, app, store, origin=None, max_bytes=262144):
        self.app, self.store = app, store
        self.public_host = urlsplit(origin).netloc if origin else None
        self.path = store.folder / 'connection-diagnostics.jsonl'
        self.max_bytes = max_bytes
        self.lock = threading.Lock()

    def record(self, entry):
        try:
            with self.lock:
                if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
                    self.path.replace(self.path.with_suffix('.previous.jsonl'))
                with self.path.open('a', encoding='utf-8') as handle:
                    handle.write(json.dumps(entry) + '\n')
        except OSError:
            # Diagnostics must never prevent a legitimate MCP operation.
            pass

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        host = headers.get(b'host', b'').decode('latin-1')
        accept = headers.get(b'accept', b'').decode('latin-1').lower()
        method = scope.get('method', '')
        try:
            matched = hmac.compare_digest(scope.get('raw_path', b''),
                                          ('/' + self.store.key() + '/mcp').encode('ascii'))
        except RuntimeError:
            matched = False
        entry = dict(request_id=uuid.uuid4().hex,
                     at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                     method=method if method in {'GET', 'POST', 'DELETE', 'OPTIONS', 'HEAD'} else 'other',
                     private_path_matched=matched,
                     query_present=bool(scope.get('query_string')),
                     host_kind='public' if host == self.public_host else 'loopback' if
                     host.split(':')[0] in {'127.0.0.1', 'localhost'} else 'other',
                     origin_present=b'origin' in headers,
                     accepts_json='application/json' in accept,
                     accepts_sse='text/event-stream' in accept,
                     # Untrusted diagnostic hints, never authentication.
                     probe_kind={b'health':'health', b'verification':'verification'}.get(
                         headers.get(b'x-ai-doll-probe', b''), 'unmarked'),
                     rpc_method=None, status=None)
        # Capture arrival before the application can block reading the body or
        # fail. The same request_id ties this entry to its eventual response.
        self.record(dict(entry, stage='received'))
        body = bytearray()
        oversized = False
        response_started = False

        async def diagnostic_receive():
            nonlocal oversized
            message = await receive()
            if matched and method == 'POST' and message['type'] == 'http.request':
                chunk = message.get('body', b'')
                if not oversized and len(body) + len(chunk) <= 16384:
                    body.extend(chunk)
                else:
                    oversized = True
                    body.clear()
                if not message.get('more_body') and not oversized:
                    try:
                        value = json.loads(body)
                        rpc = value.get('method') if isinstance(value, dict) else None
                        entry['rpc_method'] = rpc if rpc in self.RPC_METHODS else 'other'
                    except (ValueError, TypeError):
                        entry['rpc_method'] = 'invalid_json'
                    finally:
                        body.clear()
            return message

        async def diagnostic_send(message):
            nonlocal response_started
            if message['type'] == 'http.response.start':
                response_started = True
                entry['status'] = message['status']
                self.record(dict(entry, stage='response'))
            await send(message)

        outcome = 'returned_without_response'
        try:
            return await self.app(scope, diagnostic_receive, diagnostic_send)
        except BaseException as error:
            # Never serialize the exception: its text may contain request data.
            outcome = 'cancelled' if isinstance(error, asyncio.CancelledError) else 'exception'
            raise
        finally:
            if not response_started:
                self.record(dict(entry, stage='unanswered', outcome=outcome))


def create_private_remote(folder, origin=None, port=8771, profile='interaction', listen_host='127.0.0.1'):
    if origin is not None:
        origin = normalize_public_origin(origin)
    if profile not in PROFILES or type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Invalid profile or port')
    store = CapabilityStore(folder)
    gateway = create_gateway(profile, port, folder, origin, capability_store=store)
    if listen_host != '127.0.0.1':
        import ipaddress
        address = ipaddress.ip_address(listen_host)
        if (not address.is_private or address.is_unspecified or address.is_multicast
                or address.is_link_local or address.is_reserved):
            raise ValueError('Listen host must be a specific LAN/loopback IP, not all interfaces')
        authority = ('['+listen_host+']' if address.version == 6 else listen_host)+':'+str(port)
        gateway.settings.transport_security.allowed_hosts.append(authority)
        gateway.settings.transport_security.allowed_origins.append('http://'+authority)
    app = PrivateAddressGate(gateway.streamable_http_app(), store, gateway.settings.transport_security)
    return gateway, ConnectionDiagnostics(app, store, origin), store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-origin', help='Exact HTTPS origin; local-only testing can omit it')
    parser.add_argument('--port', type=int, default=8771)
    parser.add_argument('--profile', choices=PROFILES, default='interaction')
    parser.add_argument('--folder', type=Path, default=ROOT / 'build/device-lab/remote-mcp')
    parser.add_argument('--listen-host', default='127.0.0.1', help='Specific LAN IP for custom hosts; default stays loopback')
    parser.add_argument('--print-address', action='store_true', help='Print this local/private client URL before serving')
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    with ServiceLease(args.folder / 'remote.lock'):
        _, app, store = create_private_remote(args.folder, args.public_origin, args.port, args.profile, args.listen_host)
        if args.print_address:
            print(store.url(args.public_origin) if args.public_origin else store.local_url(args.listen_host,args.port), flush=True)
        print('Private-address MCP ready on configured port '+str(args.port)+'. Access logging disabled.', flush=True)
        import uvicorn
        uvicorn.run(app, host=args.listen_host, port=args.port, log_level='critical', access_log=False)


if __name__ == '__main__':
    main()
