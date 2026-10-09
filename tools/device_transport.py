"""Selectable USB or authenticated LAN MCP transport for the same collector."""
import base64
import ipaddress
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

from device_lab import CONFIG, WORK, SerialLink
from device_discovery import discover_paired_device

VERSION = 'doll-bridge-2.10.0'
PROTOCOL = '2025-11-25'


class DeviceConnectionError(RuntimeError):
    """Safe error text: never include response bodies or authentication values."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fp.close()
        raise DeviceConnectionError('Device redirects are not accepted; check its LAN IP')


def lan_address(host):
    """Accept a private IPv4 address and optional port; no URL credentials or DNS."""
    if not isinstance(host, str) or not host or any(ord(c) < 33 for c in host):
        raise ValueError('DeviceHost must be a private IPv4 address, optionally with a port')
    try:
        parsed = urllib.parse.urlsplit('http://' + host)
        address = ipaddress.ip_address(parsed.hostname)
        port = parsed.port or 80
        if (address.version != 4 or not address.is_private or address.is_unspecified or
                address.is_multicast or address.is_reserved or parsed.username is not None or
                parsed.password is not None or parsed.path or parsed.query or parsed.fragment):
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('DeviceHost must be a private IPv4 address, optionally with a port') from None
    return str(address) + (':' + str(port) if port != 80 else '')


class WifiLink:
    def __init__(self, host, config, timeout=4, discovery=discover_paired_device, on_recovered=None):
        self.host = lan_address(host)
        self.base = 'http://' + self.host
        self.token = config.get('mcp_token', '')
        if (not isinstance(self.token, str) or not 16 <= len(self.token) <= 1024 or
                '\r' in self.token or '\n' in self.token):
            raise ValueError('Pair the device first: python tools/pair_wifi_device.py --host <LAN-IP>')
        self.admin_password = config.get('ap_password', '')
        self.expected_device = config.get('device_id') or config.get('state', {}).get('device_id')
        self.config = config
        self.discovery = discovery
        self.on_recovered = on_recovered
        self.last_discovery = -float('inf')
        self.timeout = timeout
        self.initialized = False
        self.ident = 0
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def close(self):
        self.initialized = False

    def _request(self, path, payload, admin=False):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
                   'MCP-Protocol-Version': PROTOCOL, 'Authorization': 'Bearer ' + self.token}
        if admin:
            if not self.admin_password:
                raise ValueError('Open the device settings page to manage Wi-Fi; no admin password is paired')
            headers['Authorization'] = 'Basic ' + base64.b64encode(
                ('admin:' + self.admin_password).encode()).decode()
            headers['X-Setup-Token'] = self.token
        wire = json.dumps(payload, ensure_ascii=True).encode()
        req = urllib.request.Request(self.base + path, data=wire, headers=headers, method='POST')
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                data = response.read(524289)
                if len(data) > 524288:
                    raise DeviceConnectionError('Device response is too large')
                if response.status == 202 and not data:
                    return None
                if response.status != 200:
                    raise DeviceConnectionError('Unexpected device HTTP status')
                result = json.loads(data)
                if not isinstance(result, dict):
                    raise ValueError()
                return result
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            raise DeviceConnectionError('Device HTTP ' + str(status) + '; check IP, MCP switch and pairing') from None
        except (urllib.error.URLError, OSError):
            raise DeviceConnectionError('Wi-Fi device unavailable; check power and LAN connection') from None
        except (ValueError, UnicodeDecodeError):
            raise DeviceConnectionError('Invalid device JSON response') from None

    def _rpc(self, method, params=None):
        self.ident += 1
        ident = self.ident
        response = self._request('/mcp', {'jsonrpc': '2.0', 'id': ident,
                                        'method': method, 'params': params or {}})
        if not response or response.get('jsonrpc') != '2.0' or response.get('id') != ident:
            raise DeviceConnectionError('Device MCP response ID mismatch')
        return response

    def _initialize(self):
        if self.initialized:
            return
        reply = self._rpc('initialize', {'protocolVersion': PROTOCOL, 'capabilities': {},
                                       'clientInfo': {'name': 'ai-doll-wifi-collector', 'version': '2.10.0'}})
        if reply.get('result', {}).get('protocolVersion') != PROTOCOL:
            raise DeviceConnectionError('Device MCP initialization failed')
        self._request('/mcp', {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.initialized = True

    def _tool(self, name, arguments):
        response = self._rpc('tools/call', {'name': name, 'arguments': arguments})
        if 'error' in response or response.get('result', {}).get('isError'):
            raise ValueError('Device rejected this tool; check its channel configuration')
        try:
            data = json.loads(next(item['text'] for item in response['result']['content']
                                   if item.get('type') == 'text'))
        except (KeyError, StopIteration, ValueError, TypeError):
            raise DeviceConnectionError('Invalid device tool response') from None
        if not isinstance(data, dict):
            raise DeviceConnectionError('Invalid device tool response')
        if self.expected_device and data.get('device_id', self.expected_device) != self.expected_device:
            raise DeviceConnectionError('Device ID differs from paired device; check its LAN IP')
        return data

    def discover(self, update_connection=False):
        if type(update_connection) is not bool:
            raise ValueError('update_connection must be boolean')
        self.last_discovery = time.monotonic()
        found = self.discovery(self.config)
        if not found:
            return {'found': False, 'updated': False,
                    'message': 'No authenticated reply; check power, same LAN, MCP and UDP broadcast permission'}
        # The discovery helper validates identity and HMAC before returning an address.
        host = lan_address(found['device_host'])
        changed = update_connection and host != self.host
        if changed:
            if self.on_recovered:
                self.on_recovered(host)
            self.host, self.base, self.initialized = host, 'http://' + host, False
        return dict(found, found=True, updated=bool(changed))

    @staticmethod
    def _read_only(command):
        if command.get('cmd') in ('status', 'events'):
            return True
        if command.get('cmd') != 'rpc':
            return False
        request = command.get('request', {})
        if request.get('method') in ('ping', 'tools/list'):
            return True
        return (request.get('method') == 'tools/call' and
                request.get('params', {}).get('name') in {
                    'doll_get_status', 'get_touch_events', 'get_body_map', 'get_sensor_config',
                    'get_channel_capabilities', 'get_channel_config', 'read_channel_values',
                    'get_operating_mode', 'get_pressure_calibration', 'get_event_storage_status'})

    def exchange(self, command, timeout=None):
        try:
            return self._exchange_once(command)
        except DeviceConnectionError:
            self.initialized = False
            # Only reads may be retried at a newly authenticated address. A timed-out
            # LED/motor/configuration operation is never replayed, even after recovery.
            if self._read_only(command) and time.monotonic() - self.last_discovery >= 10:
                try:
                    recovered = self.discover(update_connection=True)
                except (ValueError, OSError):
                    recovered = {'updated': False}
                if recovered['updated']:
                    return self._exchange_once(command)
            raise

    def _exchange_once(self, command):
        cmd = command.get('cmd')
        if cmd == 'setup':
            return {'mcp_token': self.token, 'ap_password': self.admin_password,
                    'admin_user': 'admin', 'transport': 'wifi'}
        if cmd == 'scan':
            return self._request('/api/scan', {'start': bool(command.get('start', False))}, admin=True)
        if cmd == 'wifi':
            return self._request('/api/wifi', {k: command.get(k) for k in ('ssid', 'password')}, admin=True)
        if cmd == 'reboot':
            raise ValueError('Use the device RST button to restart in Wi-Fi mode')
        try:
            self._initialize()
            if cmd == 'status':
                return self._tool('doll_get_status', {})
            if cmd == 'events':
                return self._tool('get_touch_events', {'boot_id': command.get('boot_id', ''),
                                                       'after': command.get('after', 0), 'include_persistent':True})
            if cmd == 'ack_events':
                return self._tool('acknowledge_events', {k:command.get(k) for k in ('boot_id','storage_epoch','storage_cursor')})
            if cmd == 'sync_time':
                return self._tool('set_device_time', {k:command.get(k) for k in ('boot_id','unix_time_ms')})
            if cmd == 'rpc':
                request = command['request']
                response = self._rpc(request['method'], request.get('params'))
                response['id'] = request.get('id')
                return response
            raise ValueError('Unsupported Wi-Fi device command')
        except DeviceConnectionError:
            # Retry initialization on the NEXT operation; never replay a timed-out output command.
            self.initialized = False
            raise


def save_connection(path, mode, host='', port='COM3'):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps({'transport': mode, 'device_host': host,
                               'serial_port': port}, indent=2), encoding='utf-8')
    os.replace(temp, path)


def create_device_link(environ=None, config_path=CONFIG, connection_path=None):
    environ = os.environ if environ is None else environ
    connection_path = pathlib.Path(connection_path or WORK/'connection-private.json')
    saved = json.loads(connection_path.read_text(encoding='utf-8-sig')) if connection_path.exists() else {}
    explicit = environ.get('DOLL_TRANSPORT', '')
    host = environ.get('DOLL_DEVICE_HOST') or saved.get('device_host', '')
    mode = explicit or ('wifi' if environ.get('DOLL_DEVICE_HOST') else saved.get('transport', 'usb'))
    port = environ.get('DOLL_SERIAL_PORT') or saved.get('serial_port', 'COM3')
    if mode == 'wifi':
        config = json.loads(pathlib.Path(config_path).read_text(encoding='utf-8-sig')) if pathlib.Path(config_path).exists() else {}
        host = host or config.get('state', {}).get('ip', '')
        if host in ('', '0.0.0.0'):
            found = discover_paired_device(config)
            if not found:
                raise ValueError('No paired device found; check LAN or provide its private IPv4 address')
            host = found['device_host']
        link = WifiLink(host, config)
        host = link.host
    elif mode == 'usb':
        link = SerialLink(port)
    else:
        raise ValueError('DOLL_TRANSPORT must be usb or wifi')
    save_connection(connection_path, mode, host, port)
    info = {'bridge_version': VERSION, 'transport': mode,
                  'device_host': host if mode == 'wifi' else None,
                  'serial_port': port if mode == 'usb' else None}
    if mode == 'wifi':
        def recovered(new_host):
            save_connection(connection_path, mode, new_host, port)
            info['device_host'] = new_host
            info['last_address_recovery'] = time.time()
        link.on_recovered = recovered
    return link, info
