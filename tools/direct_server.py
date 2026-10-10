"""Device-outbound event receiver, configuration relay and existing-chat event API.

Run behind HTTPS on a server, or on a LAN for a local custom frontend. No PC
collector, model key or new chat UI is involved. Each paired device owns a
separate Companion archive. Device acknowledgements follow its SQLite commit.
"""
import argparse
import hashlib
import hmac
import json
import os
import secrets
import socket
import sqlite3
import threading
import time
from contextlib import nullcontext
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from companion import Companion
from private_storage import write_json

DEVICE_READS = {'get_channel_config': 'channels', 'get_channel_capabilities': 'capabilities',
                'read_channel_values': 'values', 'get_operating_mode': 'operating_mode',
                'get_pressure_calibration': 'calibration', 'get_sensor_config': 'sensors'}
DEVICE_COMMANDS = {'set_channel_config', 'set_body_map', 'simulate_channel_input',
                   'doll_simulate_press', 'set_input_enabled', 'set_output_enabled',
                   'set_vibration', 'set_operating_mode', 'doll_set_led',
                   'capture_pressure_calibration', 'get_pressure_calibration',
                   'apply_pressure_calibration', 'cancel_pressure_calibration',
                   'scan_input_devices', 'get_sensor_config', 'set_sensor_config'}
OWNER = 'direct-owner'


class DirectHTTPServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR permits two listeners on one address; requests can
    # land in the wrong process. Refuse a second server instead.
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class PushCompanion(Companion):
    def device_connection(self):
        # Snapshot reads and queued commands use SQLite locks, not a serial
        # socket. Holding the old serial mutex while awaiting a command would
        # make status polling block all remote configuration buttons.
        return nullcontext()

    def sync(self):
        # The device pushes and commits pages; starting a session takes a
        # boundary from that committed sequence, without a LAN/USB read.
        self.exchange({'cmd': 'status'})

    def archive_metadata(self):
        result = dict(super().archive_metadata(), history_source='server_sqlite', transport='device_push')
        if self.last_sync is None:
            result['collector_error'] = 'waiting_for_device'
        elif time.time()-self.last_sync >= 15:
            result['collector_error'] = 'device_offline'
        return result


class Device:
    def __init__(self, folder, ident):
        self.id = ident
        self.incoming = threading.RLock()
        self.c = PushCompanion(folder / (ident+'.sqlite3'), self.exchange, threading.Lock())
        with self.c.lock, self.c.db:
            self.c.db.executescript('''
              CREATE TABLE IF NOT EXISTS remote_commands(
                id TEXT PRIMARY KEY,name TEXT NOT NULL,arguments TEXT NOT NULL,
                created REAL NOT NULL,expires REAL NOT NULL,state TEXT NOT NULL,result TEXT);
            ''')
        self.c.runtime_info = dict(transport='device_push', version='direct-server-1.0.0')

    def snapshot(self):
        return json.loads(self.c.setting('remote_snapshot', '{}'))

    def online(self):
        return self.c.last_sync is not None and time.time()-self.c.last_sync < 15

    def exchange(self, command):
        if not self.online():
            raise ConnectionError('Device offline; saved history remains available')
        snapshot = self.snapshot()
        if command['cmd'] == 'status':
            return snapshot['status']
        if command['cmd'] != 'rpc':
            raise ValueError('Push mode has no polling transport')
        params = command['request']['params']
        name, args = params['name'], params.get('arguments', {})
        if name == 'doll_get_status':
            value = dict(snapshot['status'], transport='device_push', last_sync=self.c.last_sync)
        elif name in DEVICE_READS and DEVICE_READS[name] in snapshot:
            value = snapshot[DEVICE_READS[name]]
        elif name == 'get_event_storage_status':
            value = snapshot['status']['event_storage']
        elif name == 'get_body_map':
            value = {'parts': [ch['name'] for ch in snapshot['channels']['channels']]}
        elif name in DEVICE_COMMANDS:
            queued = self.queue(name, args, ttl=8)
            while time.time() < queued['expires']:
                result = self.command(queued['id'])
                if result['state'] == 'completed':
                    if 'error' in result['result']:
                        raise ValueError(result['result']['error'])
                    return result['result']['rpc']
                time.sleep(.1)
            with self.c.lock, self.c.db:
                self.c.db.execute("UPDATE remote_commands SET state='cancelled' WHERE id=? AND state='pending'", (queued['id'],))
            raise TimeoutError('Command result not received; inspect command status before retrying')
        else:
            raise ValueError('Device tool unavailable in direct mode')
        return {'result': {'content': [{'type': 'text', 'text': json.dumps(value, ensure_ascii=False)}]}}

    def queue(self, name, arguments, ttl=30):
        if name not in DEVICE_COMMANDS or not isinstance(arguments, dict):
            raise ValueError('Unsupported device configuration command')
        if not self.online():
            raise ConnectionError('Device offline; commands are not queued for later execution')
        ident, now = secrets.token_hex(16), time.time()
        with self.c.lock, self.c.db:
            count = self.c.db.execute("SELECT COUNT(*) FROM remote_commands WHERE state='pending' AND expires>?", (now,)).fetchone()[0]
            if count >= 16:
                raise ValueError('Device command queue full')
            self.c.db.execute('INSERT INTO remote_commands VALUES(?,?,?,?,?,?,NULL)',
                              (ident, name, json.dumps(arguments), now, now+ttl, 'pending'))
        return dict(id=ident, state='pending', expires=now+ttl)

    def command(self, ident):
        with self.c.lock, self.c.db:
            self.c.db.execute("UPDATE remote_commands SET state='expired' WHERE state IN ('pending','dispatched') AND expires<=?", (time.time(),))
            row = self.c.db.execute('SELECT * FROM remote_commands WHERE id=?', (ident,)).fetchone()
            if not row:
                raise ValueError('Unknown command')
            return dict(id=row['id'], name=row['name'], state=row['state'], expires=row['expires'],
                        result=json.loads(row['result']) if row['result'] else None)

    def receive(self, body):
        batch, snapshot = body['batch'], body['snapshot']
        if (not isinstance(batch, dict) or not isinstance(snapshot, dict) or
                not isinstance(batch.get('events'), list) or len(batch['events']) > 24 or
                snapshot.get('status', {}).get('device_id') != batch.get('device_id') or
                snapshot['status'].get('boot_id') != batch.get('boot_id')):
            raise ValueError('Invalid batch or snapshot identity')
        for field in ('channels', 'capabilities', 'values', 'operating_mode'):
            if not isinstance(snapshot.get(field), dict):
                raise ValueError('Missing device snapshot field: '+field)
        with self.incoming:
            # Nothing may be acknowledged until validation and archive commit
            # have succeeded. Companion owns transactional event/outbox dedup.
            self.c.ingest(batch)
            with self.c.lock, self.c.db:
                now = time.time()
                self.c.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',
                                  ('remote_snapshot', json.dumps(snapshot, ensure_ascii=False)))
                for tool, field in DEVICE_READS.items():
                    if tool in ('get_channel_config', 'get_channel_capabilities'):
                        self.c.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',
                            ('cached_'+tool, json.dumps(dict(data=snapshot[field], saved_at=now))))
                acknowledged = []
                for result in body.get('command_results', []):
                    if not isinstance(result, dict) or not isinstance(result.get('id'), str):
                        raise ValueError('Invalid command result')
                    row = self.c.db.execute('SELECT state FROM remote_commands WHERE id=?', (result['id'],)).fetchone()
                    if row and row['state'] in ('dispatched', 'expired', 'completed'):
                        self.c.db.execute("UPDATE remote_commands SET state='completed',result=? WHERE id=?",
                                          (json.dumps(result), result['id']))
                        acknowledged.append(result['id'])
                self.c.db.execute("UPDATE remote_commands SET state='expired' WHERE state IN ('pending','dispatched') AND expires<=?", (now,))
                row = self.c.db.execute("SELECT * FROM remote_commands WHERE state='pending' ORDER BY created LIMIT 1").fetchone()
                commands = []
                if row:
                    # At most once dispatch. A lost response is ambiguous; no
                    # automatic replay of simulation or physical commands.
                    self.c.db.execute("UPDATE remote_commands SET state='dispatched' WHERE id=?", (row['id'],))
                    commands.append(dict(id=row['id'], name=row['name'], arguments=json.loads(row['arguments']),
                                         expires_at_ms=round(row['expires']*1000)))
            try:
                self.c.history_manager.maintain()
                self.c.maintenance_error = None
            except Exception:
                self.c.maintenance_error = 'History retention unavailable; archive preserved'
            return dict(accepted=True, boot_id=batch['boot_id'],
                        storage_epoch=batch.get('event_storage', {}).get('storage_epoch'),
                        storage_cursor=batch.get('storage_cursor', 0), next_cursor=batch['next_cursor'],
                        unix_time_ms=round(time.time()*1000), commands=commands, acknowledged_commands=acknowledged)


class DirectServer:
    def __init__(self, folder, public_url='', origins=()):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.public_url = public_url.rstrip('/')
        self.origins = set(origins)
        if public_url:
            parsed = urlsplit(public_url)
            if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
                raise ValueError('public-url must be a complete origin, without a path')
            self.origins.add(self.public_url)
        config_file = self.folder/'server-private.json'
        if not config_file.exists():
            write_json(config_file, dict(admin_token=secrets.token_hex(32)))
        self.admin_token = json.loads(config_file.read_text(encoding='utf-8'))['admin_token']
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.folder/'server.sqlite3', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,token_hash TEXT UNIQUE,label TEXT,hardware_id TEXT,revoked INTEGER DEFAULT 0)')
        self.db.commit()
        self.devices = {}
        self.stop = threading.Event()
        self.streams = {}

    def pair(self, label):
        if not isinstance(label, str) or not 1 <= len(label) <= 80:
            raise ValueError('Device label required, up to 80 characters')
        ident, token = secrets.token_hex(16), secrets.token_hex(32)
        with self.lock, self.db:
            self.db.execute('INSERT INTO devices VALUES(?,?,?,?,0)', (ident, digest(token), label, None))
        return dict(id=ident, device_token=token, server_url=self.public_url,
                    instruction='在设备设置页的“直连服务器”中填写服务器地址与设备连接令牌')

    def resolve(self, ident):
        with self.lock:
            row = self.db.execute('SELECT * FROM devices WHERE id=? AND revoked=0', (ident,)).fetchone()
            if not row:
                raise ValueError('Unknown or revoked device')
            if ident not in self.devices:
                self.devices[ident] = Device(self.folder, ident)
            return self.devices[ident]

    def receive(self, token, data):
        if type(data.get('protocol')) is not int or data['protocol'] != 1 or not isinstance(data.get('batch'), dict):
            raise ValueError('Direct protocol 1 and event batch required')
        hardware = data.get('batch', {}).get('device_id')
        if not isinstance(hardware, str) or not 1 <= len(hardware) <= 128:
            raise ValueError('Device ID required')
        with self.lock:
            row = self.db.execute('SELECT * FROM devices WHERE token_hash=? AND revoked=0', (digest(token),)).fetchone()
            if not row:
                raise PermissionError('Invalid device connection token')
            if row['hardware_id'] and row['hardware_id'] != hardware:
                raise PermissionError('Token is bound to another device')
            device = self.resolve(row['id'])
            response = device.receive(data)
            with self.db:
                self.db.execute('UPDATE devices SET hardware_id=? WHERE id=?', (hardware, row['id']))
        return response

    def list_devices(self):
        with self.lock:
            rows = self.db.execute('SELECT id,label,hardware_id FROM devices WHERE revoked=0').fetchall()
        return [dict(row, online=self.resolve(row['id']).online(), last_sync=self.resolve(row['id']).c.last_sync) for row in rows]

    def close(self):
        self.stop.set()
        for device in self.devices.values():
            device.c.stop.set()
            device.c.db.close()
        self.db.close()


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def token(self):
            value = self.headers.get('Authorization', '')
            return value[7:] if value.startswith('Bearer ') else ''

        def admin(self):
            token = self.token()
            if not token:
                cookies = SimpleCookie(self.headers.get('Cookie', ''))
                token = cookies['doll_admin'].value if 'doll_admin' in cookies else ''
            return bool(token) and hmac.compare_digest(token, app.admin_token)

        def origin_ok(self):
            origin = self.headers.get('Origin')
            if not origin:
                return True
            local = 'http://'+self.headers.get('Host', '')
            return origin in app.origins or (not app.public_url and origin == local)

        def begin_response(self, code, mime='application/json; charset=utf-8', length=None):
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'SAMEORIGIN')
            origin = self.headers.get('Origin')
            if origin and self.origin_ok():
                self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Vary', 'Origin')
                self.send_header('Access-Control-Allow-Credentials', 'true')
            if length is not None:
                self.send_header('Content-Length', str(length))

        def send(self, code, value):
            raw = json.dumps(value, ensure_ascii=False).encode()
            self.begin_response(code, length=len(raw))
            self.end_headers()
            self.wfile.write(raw)

        def body(self):
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 65536:
                raise ValueError('Request size must be 1..65536 bytes')
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict):
                raise ValueError('Request must be an object')
            return value

        def device_path(self):
            path = urlsplit(self.path).path.split('/')
            if len(path) >= 4 and path[1] == 'd':
                return app.resolve(path[2]), '/'+ '/'.join(path[3:])
            return None, None

        def do_OPTIONS(self):
            if not self.origin_ok():
                return self.send(403, {'error': 'Origin not allowed'})
            self.begin_response(204, length=0)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
            self.end_headers()

        def stream(self, device, subscription):
            c = device.c
            with c.lock, c.db:
                valid = c.db.execute('SELECT id FROM bridge_subscriptions WHERE id=? AND owner=? AND active=1', (subscription, OWNER)).fetchone()
            if not valid:
                return self.send(404, {'error': 'Subscription ended'})
            identity, stream_id = (device.id, subscription), secrets.token_hex(16)
            with app.lock:
                app.streams[identity] = stream_id
            self.begin_response(200, 'text/event-stream; charset=utf-8')
            self.send_header('X-Accel-Buffering', 'no')
            self.end_headers()
            try:
                deadline = time.monotonic()+25
                while time.monotonic() < deadline and not app.stop.is_set():
                    with app.lock:
                        if app.streams.get(identity) != stream_id:
                            break
                    message = c.bridge.claim(owner=OWNER, subscription_id=subscription)
                    if message:
                        data = dict(event=message['payload'], lease=message['lease'], subscription_id=subscription)
                        raw = 'event: interaction\nid: '+message['event_id']+'\ndata: '+json.dumps(data, ensure_ascii=False)+'\n\n'
                    else:
                        raw = ': heartbeat\n\n'
                    self.wfile.write(raw.encode()); self.wfile.flush()
                    app.stop.wait(.25 if message else .5)
            except (OSError, ConnectionError):
                pass
            finally:
                self.close_connection = True
                with app.lock:
                    if app.streams.get(identity) == stream_id:
                        app.streams.pop(identity, None)

        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path == '/healthz':
                return self.send(200, {'ready': True, 'mode': 'device_push'})
            if parsed.path in ('/', '/direct-server.js', '/bridge-client.js', '/conversation-queue.js', '/channel-editor.js', '/history-manager.js', '/console-embed.js'):
                asset = {'/': 'direct_server.html', '/direct-server.js': 'direct_server.js',
                         '/bridge-client.js': 'bridge_client.js', '/conversation-queue.js': 'conversation_queue.js',
                         '/channel-editor.js': 'channel_editor.js', '/history-manager.js': 'history_manager.js', '/console-embed.js': 'console_embed.js'}[parsed.path]
                raw = Path(__file__).with_name(asset).read_bytes()
                self.begin_response(200, 'text/html; charset=utf-8' if asset.endswith('.html') else 'application/javascript; charset=utf-8', len(raw))
                self.end_headers(); self.wfile.write(raw)
                return
            if not self.origin_ok() or not self.admin():
                return self.send(401, {'error': 'Server connection token required'})
            try:
                if parsed.path == '/api/devices':
                    return self.send(200, {'devices': app.list_devices()})
                device, path = self.device_path()
                if path == '/companion':
                    page = Path(__file__).with_name('companion.html').read_text(encoding='utf-8')
                    page = page.replace("const csrf='__CSRF__'", "const deviceBase="+json.dumps('/d/'+device.id)+";const csrf=''")
                    page = page.replace('fetch(path,{', 'fetch(deviceBase+path,{').replace('电脑', '服务器')
                    page = page.replace("c.transport==='wifi'?", "c.transport==='device_push'?'设备连接：直连服务器 · 无需电脑采集':c.transport==='wifi'?")
                    raw = page.encode()
                    self.begin_response(200, 'text/html; charset=utf-8', len(raw))
                    self.end_headers(); self.wfile.write(raw)
                    return
                if path == '/status':
                    return self.send(200, dict(online=device.online(), last_sync=device.c.last_sync, snapshot=device.snapshot(), active_session=device.c.active()))
                if path == '/companion/state':
                    return self.send(200, dict(active_session=device.c.active(), collector_error=None if device.online() else '设备离线，显示已存历史', last_sync=device.c.last_sync, persona=device.c.setting('persona')))
                if path == '/connection':
                    return self.send(200, dict(transport='device_push', collector_error=None if device.online() else 'device_offline', last_sync=device.c.last_sync))
                if path == '/bridge/events':
                    ids = parse_qs(parsed.query).get('subscription_id', [])
                    if len(ids) != 1:
                        raise ValueError('subscription_id required')
                    return self.stream(device, ids[0])
                if path and path.startswith('/commands/'):
                    return self.send(200, device.command(path.split('/')[-1]))
                return self.send(404, {'error': 'Not found'})
            except ValueError as exc:
                return self.send(400, {'error': str(exc)})

        def do_POST(self):
            path = urlsplit(self.path).path
            try:
                if path == '/api/device/exchange':
                    return self.send(200, app.receive(self.token(), self.body()))
                if not self.origin_ok():
                    return self.send(403, {'error': 'Origin not allowed'})
                if path == '/api/connect':
                    data = self.body()
                    if not hmac.compare_digest(str(data.get('token', '')), app.admin_token):
                        return self.send(401, {'error': 'Connection token incorrect'})
                    raw = b'{"connected":true}'
                    self.begin_response(200, length=len(raw))
                    secure = '; Secure' if app.public_url.startswith('https://') else ''
                    self.send_header('Set-Cookie', 'doll_admin='+app.admin_token+'; HttpOnly; SameSite=Strict; Path=/'+secure)
                    self.end_headers(); self.wfile.write(raw)
                    return
                if not self.admin():
                    return self.send(401, {'error': 'Server connection token required'})
                data = self.body()
                if path == '/api/disconnect':
                    self.begin_response(200, length=2)
                    self.send_header('Set-Cookie', 'doll_admin=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/')
                    self.end_headers(); self.wfile.write(b'{}')
                    return
                if path == '/api/pairings':
                    return self.send(200, app.pair(data.get('label')))
                if path == '/api/revoke':
                    with app.lock, app.db:
                        app.db.execute('UPDATE devices SET revoked=1 WHERE id=?', (data.get('id'),))
                    return self.send(200, {'revoked': True})
                device, route = self.device_path()
                if route == '/companion/tool':
                    return self.send(200, device.c.call(data.get('name'), data.get('arguments', {})))
                if route == '/commands':
                    return self.send(202, device.queue(data.get('name'), data.get('arguments', {})))
                if route == '/bridge/subscriptions':
                    if set(data)-{'target_id', 'session_id', 'device_id', 'ttl_sec', 'arguments', 'policy', 'feedback'}:
                        raise ValueError('Unknown subscription fields')
                    if data.get('device_id') != device.snapshot().get('status', {}).get('device_id'):
                        raise ValueError('Subscription must match this paired device')
                    return self.send(200, device.c.bridge.subscribe(OWNER, **data))
                if route == '/bridge/next':
                    wait = data.get('wait_sec', 0)
                    if type(wait) is not int or not 0 <= wait <= 20:
                        raise ValueError('wait_sec must be 0..20')
                    deadline = time.monotonic()+wait
                    while True:
                        delivery = device.c.bridge.claim(owner=OWNER, subscription_id=data.get('subscription_id'))
                        if delivery:
                            return self.send(200, dict(event=delivery['payload'], lease=delivery['lease'], subscription_id=delivery['subscription_id']))
                        if time.monotonic() >= deadline or app.stop.is_set():
                            return self.send(200, {'event': None})
                        time.sleep(.1)
                if route in ('/bridge/unsubscribe', '/bridge/renew', '/bridge/ack'):
                    method = {'/bridge/unsubscribe': 'unsubscribe', '/bridge/renew': 'renew', '/bridge/ack': 'acknowledge'}[route]
                    return self.send(200, getattr(device.c.bridge, method)(OWNER, **data))
                if route == '/bridge/preferences':
                    return self.send(200, device.c.bridge.save_preferences(**data))
                return self.send(404, {'error': 'Not found'})
            except PermissionError as exc:
                return self.send(401, {'error': str(exc)})
            except (ValueError, KeyError, TypeError) as exc:
                return self.send(400, {'error': str(exc)})
            except (ConnectionError, TimeoutError) as exc:
                return self.send(503, {'error': str(exc)})
            except sqlite3.Error:
                return self.send(503, {'error': 'Storage unavailable; device page was not acknowledged'})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default='build/direct-server')
    parser.add_argument('--listen', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8781)
    parser.add_argument('--public-url', default='')
    parser.add_argument('--origin', action='append', default=[])
    parser.add_argument('--show-token', action='store_true', help='Display owner connection token locally')
    args = parser.parse_args()
    app = DirectServer(args.data_dir, args.public_url, args.origin)
    if args.show_token:
        print(app.admin_token, flush=True)
        app.close()
        return
    httpd = DirectHTTPServer((args.listen, args.port), handler_for(app))
    print('Device direct server: http://'+args.listen+':'+str(httpd.server_port), flush=True)
    print('Owner connection token: saved in '+str(app.folder/'server-private.json'), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop.set(); httpd.server_close(); app.close()


if __name__ == '__main__':
    main()
