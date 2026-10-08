"""Bounded discovery of one already-paired device; credentials never go over UDP."""
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import select
import socket
import subprocess
import time

PROTOCOL = 'ai-doll-discovery-v1'
PORT = 28768


def paired_identity(config):
    device = config.get('device_id') or config.get('state', {}).get('device_id')
    token = config.get('mcp_token')
    if (not isinstance(device, str) or not re.fullmatch(r'AI-Doll-[0-9a-f]{6}', device) or
            not isinstance(token, str) or not 16 <= len(token) <= 1024 or
            '\n' in token or '\r' in token):
        raise ValueError('Device discovery requires an existing paired device identity and token')
    return device, token


def signature(token, nonce, device, firmware, port=80):
    message = '\n'.join((PROTOCOL, nonce, device, str(port), firmware)).encode('utf-8')
    return hmac.new(token.encode('utf-8'), message, hashlib.sha256).hexdigest()


def verify_reply(raw, sender, nonce, device, token, allow_loopback=False):
    """The host comes from the socket, never from an untrusted JSON host field."""
    try:
        address = ipaddress.ip_address(sender[0])
        if (address.version != 4 or not address.is_private or address.is_unspecified or
                address.is_multicast or address.is_reserved or address.is_link_local or
                (address.is_loopback and not allow_loopback) or len(raw) > 2048):
            return None
        data = json.loads(raw)
        firmware = data.get('firmware')
        if (data.get('protocol') != PROTOCOL or data.get('nonce') != nonce or
                data.get('device_id') != device or type(data.get('port')) is not int or data['port'] != 80 or
                not isinstance(firmware, str) or not re.fullmatch(r'doll-lab-[0-9]+\.[0-9]+\.[0-9]+', firmware) or
                not isinstance(data.get('proof'), str) or
                not hmac.compare_digest(data['proof'], signature(token, nonce, device, firmware))):
            return None
        return dict(device_host=str(address), device_id=device, firmware=firmware, verified=True)
    except (ValueError, TypeError, AttributeError, UnicodeDecodeError):
        return None


def interface_bindings():
    """Read actual Windows prefixes, including multi-adapter hosts; never assume /24."""
    if os.name != 'nt':
        # Other hosts can still discover through their default broadcast route.
        return [('0.0.0.0', '255.255.255.255')]
    command = ('Get-NetIPAddress -AddressFamily IPv4 | '
               "Where-Object { $_.AddressState -eq 'Preferred' } | "
               'Select-Object IPAddress,PrefixLength | ConvertTo-Json -Compress')
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                                capture_output=True, timeout=4, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode or len(result.stdout) > 16384:
            return []
        rows = json.loads(result.stdout.decode('utf-8-sig'))
        rows = rows if isinstance(rows, list) else [rows]
        bindings = []
        for row in rows:
            interface = ipaddress.ip_interface(str(row['IPAddress']) + '/' + str(row['PrefixLength']))
            address = interface.ip
            if (address.version != 4 or not address.is_private or address.is_loopback or
                    address.is_link_local or address.is_reserved or address.is_unspecified or
                    address.is_multicast or interface.network.prefixlen >= 31):
                continue
            pair = (str(address), str(interface.network.broadcast_address))
            if pair not in bindings:
                bindings.append(pair)
        return bindings[:16]
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError):
        return []


def discover_paired_device(config, timeout=1.5, *, bindings=None, port=PORT):
    """One challenge on each private interface; ignore unrelated or forged replies."""
    device, token = paired_identity(config)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not .1 <= timeout <= 5:
        raise ValueError('Discovery timeout must be between 0.1 and 5 seconds')
    test_loopback = bindings is not None and all(ipaddress.ip_address(ip).is_loopback for ip, _ in bindings)
    bindings = interface_bindings() if bindings is None else bindings
    nonce = secrets.token_hex(16)
    wire = json.dumps(dict(protocol=PROTOCOL, nonce=nonce, device_id=device), separators=(',', ':')).encode()
    sockets = []
    try:
        for address, broadcast in bindings[:16]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind((address, 0))
                sock.sendto(wire, (broadcast, port))
                sock.setblocking(False)
                sockets.append(sock)
            except OSError:
                sock.close()
        deadline = time.monotonic() + timeout
        while sockets and time.monotonic() < deadline:
            readable, _, _ = select.select(sockets, [], [], max(0, deadline - time.monotonic()))
            for sock in readable:
                try:
                    raw, sender = sock.recvfrom(2049)
                    verified = verify_reply(raw, sender, nonce, device, token, test_loopback)
                    if verified:
                        return verified
                except OSError:
                    continue
        return None
    finally:
        for sock in sockets:
            sock.close()
