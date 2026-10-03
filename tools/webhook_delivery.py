"""HTTPS-only, DNS-pinned Standard Webhooks transport. Never follows redirects."""
import base64
import hashlib
import hmac
import http.client
import ipaddress
import json
import socket
import ssl
import time
import urllib.parse
import secrets
import uuid


def decode_secret(secret):
    if not isinstance(secret, str) or not secret.startswith('whsec_'):
        raise ValueError('A whsec_ signing secret is required')
    try: key = base64.b64decode(secret[6:], validate=True)
    except Exception: raise ValueError('Invalid webhook signing secret') from None
    if not 24 <= len(key) <= 64: raise ValueError('Signing key must contain 24..64 bytes')
    return key


def public_address(ip):
    return (ip.is_global and not ip.is_multicast and not ip.is_reserved and
            not (ip.version==6 and ip.ipv4_mapped and not public_address(ip.ipv4_mapped)))


def validate_url(url, resolve=True):
    if not isinstance(url, str) or len(url) > 2048: raise ValueError('Invalid callback URL')
    parsed = urllib.parse.urlsplit(url)
    try: port = parsed.port
    except ValueError: raise ValueError('Invalid callback port') from None
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or
        parsed.fragment or port not in (None, 443) or any(ord(c) < 33 or ord(c) > 126 for c in url)):
        raise ValueError('Callback must be an HTTPS public URL on port 443 without credentials or fragments')
    host = parsed.hostname
    if host.lower() == 'localhost' or host.endswith('.localhost'):
        raise ValueError('Private callbacks are not allowed')
    try: ip = ipaddress.ip_address(host)
    except ValueError: ip = None
    if ip is not None and not public_address(ip):
        raise ValueError('Private callbacks are not allowed')
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM) if resolve else []
    if resolve and not addresses: raise ValueError('Callback DNS unavailable')
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not public_address(ip):
            raise ValueError('Callback DNS includes a nonpublic address')
    return parsed, addresses


def signed_headers(secret, event_id, body, subscription_id, timestamp=None):
    stamp = str(int(time.time()) if timestamp is None else timestamp)
    signature = base64.b64encode(hmac.new(decode_secret(secret), event_id.encode()+b'.'+stamp.encode()+b'.'+body, hashlib.sha256).digest()).decode()
    return {'Content-Type': 'application/json', 'webhook-id': event_id, 'webhook-timestamp': stamp,
            'webhook-signature': 'v1,'+signature, 'X-MCP-Subscription-Id': subscription_id}


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, 443, timeout=5, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        family, socktype, proto, _, sockaddr = self.address
        raw = socket.socket(family, socktype, proto)
        raw.settimeout(self.timeout)
        try:
            raw.connect(sockaddr)
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close(); raise


class WebhookSender:
    def send(self, url, secret, payload, subscription_id, event_id):
        parsed, addresses = validate_url(url)
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
        if len(body) > 262144: raise ValueError('Event exceeds 256 KiB')
        headers = signed_headers(secret, event_id, body, subscription_id)
        path = (parsed.path or '/')+('?' + parsed.query if parsed.query else '')
        with PinnedHTTPSConnection(parsed.hostname, addresses[0]) as conn:
            conn.request('POST', path, body, headers)
            response = conn.getresponse(); raw = response.read(65537)
            if len(raw) > 65536: raise ValueError('Callback response exceeds limit')
            try: data = json.loads(raw) if raw else {}
            except (ValueError, UnicodeDecodeError): data = {}
            return response.status, data

    def verify(self, url, secret, subscription_id):
        challenge = secrets.token_urlsafe(32)
        status, data = self.send(url, secret, dict(type='verification', challenge=challenge),
                                 subscription_id, 'verification_'+uuid.uuid4().hex)
        if not 200 <= status < 300 or not isinstance(data, dict) or not isinstance(data.get('challenge'), str) or not hmac.compare_digest(data['challenge'], challenge):
            raise ValueError('Callback verification failed')


def webhook_worker(bridge, stop, sender=None):
    sender = sender or WebhookSender()
    while not stop.is_set():
        delivery = bridge.claim(transport='webhook')
        if delivery:
            try:
                status, _ = sender.send(delivery['callback'], delivery['secret'], delivery['payload'],
                                         delivery['subscription_id'], delivery['event_id'])
            except Exception:
                status = 0  # Do not persist URL, credentials or response bodies as errors.
            bridge.finish_webhook(delivery, status)
        stop.wait(.2)
