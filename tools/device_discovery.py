"""Bounded discovery of one already-paired device; credentials never go over UDP."""
import hashlib
import ctypes
import hmac
import ipaddress
import json
import os
import re
import secrets
import select
import socket
import struct
import subprocess
import threading
import time

PROTOCOL = 'ai-doll-discovery-v1'
PORT = 28768
_bindings_cache = (0.0, [])
_bindings_lock = threading.Lock()


def paired_identity(config):
    device = config.get('device_id') or config.get('state', {}).get('device_id')
    token = config.get('mcp_token')
    # Factory identities use the MAC suffix; standard USB flashes use 20 hex
    # digits from FlashJob. Both are paired with an exact identity and HMAC.
    if (not isinstance(device, str) or not re.fullmatch(r'AI-Doll-(?:[0-9a-f]{6}|[0-9a-f]{20})', device) or
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


def _windows_ipv4_rows(fetch=None):
    """Read GetIpAddrTable with native C alignment, without WMI or a child shell.

    https://learn.microsoft.com/windows/win32/api/iphlpapi/nf-iphlpapi-getipaddrtable
    """
    class Row(ctypes.Structure):
        _fields_ = [(name,ctypes.c_uint32) for name in ('address','index','mask','broadcast','reassembly')]+[
            ('reserved',ctypes.c_uint16),('kind',ctypes.c_uint16)]
    class Table(ctypes.Structure):
        _fields_ = [('count',ctypes.c_uint32),('rows',Row*1)]
    if fetch is None:
        fetch=ctypes.WinDLL('iphlpapi',use_last_error=True).GetIpAddrTable
        fetch.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32),ctypes.c_int]
        fetch.restype=ctypes.c_uint32
    size=ctypes.c_uint32(0)
    code=fetch(None,ctypes.byref(size),False)
    for _ in range(3):
        if code not in (0,122) or not 4<=size.value<=1048576:
            raise OSError('Could not read IPv4 adapter table')
        buffer=ctypes.create_string_buffer(size.value)
        code=fetch(buffer,ctypes.byref(size),False)
        if code==122:
            continue
        if code:
            raise OSError('Could not read IPv4 adapter table')
        count=ctypes.c_uint32.from_buffer(buffer).value
        offset=Table.rows.offset
        if count>4096 or offset+count*ctypes.sizeof(Row)>len(buffer):
            raise OSError('Invalid IPv4 adapter table')
        rows=[]
        for i in range(count):
            row=Row.from_buffer(buffer,offset+i*ctypes.sizeof(Row))
            address=socket.inet_ntoa(struct.pack('=I',row.address))
            mask=socket.inet_ntoa(struct.pack('=I',row.mask))
            try:
                prefix=ipaddress.IPv4Network('0.0.0.0/'+mask).prefixlen
                rows.append(dict(IPAddress=address,PrefixLength=prefix))
            except ValueError:
                continue
        return rows
    raise OSError('IPv4 adapter table kept changing')


def interface_bindings(timeout=1):
    """Read actual Windows prefixes, including multi-adapter hosts; never assume /24."""
    if os.name != 'nt':
        # Other hosts can still discover through their default broadcast route.
        return [('0.0.0.0', '255.255.255.255')]
    command = ('Get-NetIPAddress -AddressFamily IPv4 | '
               "Where-Object { $_.AddressState -eq 'Preferred' } | "
               'Select-Object IPAddress,PrefixLength | ConvertTo-Json -Compress')
    try:
        try:
            rows=_windows_ipv4_rows()
        except (OSError,AttributeError):
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                                    capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
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


def cached_interface_bindings(timeout=1):
    """Cache adapter enumeration, not device identity or authentication replies."""
    global _bindings_cache
    stamp, rows = _bindings_cache
    if rows and time.monotonic()-stamp < 15:
        return list(rows)
    if not _bindings_lock.acquire(blocking=False):
        return list(rows)
    try:
        fresh = interface_bindings(timeout=timeout)
        if fresh:
            _bindings_cache = (time.monotonic(), list(fresh))
        return list(fresh or rows)
    finally:
        _bindings_lock.release()


def discover_paired_device(config, timeout=1.5, *, bindings=None, port=PORT):
    """Fresh signed unicast first, then parallel LAN broadcasts within one budget."""
    device, token = paired_identity(config)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not .1 <= timeout <= 5:
        raise ValueError('Discovery timeout must be between 0.1 and 5 seconds')
    test_loopback = bindings is not None and all(ipaddress.ip_address(ip).is_loopback for ip, _ in bindings)
    automatic = bindings is None
    nonce = secrets.token_hex(16)
    wire = json.dumps(dict(protocol=PROTOCOL, nonce=nonce, device_id=device), separators=(',', ':')).encode()
    sockets = []
    started = time.monotonic()
    deadline = started + timeout
    method = 'lan-broadcast'
    def receive(until):
        while sockets and time.monotonic() < until:
            readable, _, _ = select.select(sockets, [], [], max(0, until-time.monotonic()))
            for sock in readable:
                try:
                    raw, sender = sock.recvfrom(2049)
                    verified = verify_reply(raw, sender, nonce, device, token, test_loopback)
                    if verified:
                        return dict(verified, method=method,
                                    elapsed_ms=round((time.monotonic()-started)*1000, 1))
                except OSError:
                    continue
        return None
    try:
        if automatic:
            # Send no credentials, even if DHCP gave the old address to someone else.
            host = config.get('device_host') or config.get('state', {}).get('ip')
            try:
                address = ipaddress.ip_address(host)
                if (address.version == 4 and address.is_private and not
                        (address.is_loopback or address.is_link_local or address.is_unspecified
                         or address.is_multicast or address.is_reserved)):
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sockets.append(sock)
                    sock.bind(('0.0.0.0', 0));sock.setblocking(False)
                    sock.sendto(wire, (str(address), port))
                    method = 'cached-address'
                    found = receive(min(deadline, started+.15))
                    if found:
                        return found
            except (ValueError, TypeError, OSError):
                pass
            remaining = deadline-time.monotonic()
            if remaining <= .05:
                return None
            bindings = cached_interface_bindings(timeout=min(.75, remaining-.05))
            method = 'lan-broadcast'
        broadcasts = []
        for address, broadcast in bindings[:16]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind((address, 0))
                sock.sendto(wire, (broadcast, port))
                sock.setblocking(False)
                sockets.append(sock)
                broadcasts.append((sock, broadcast))
            except OSError:
                sock.close()
        if automatic and bindings and not broadcasts:
            # A removed adapter must not remain cached until the normal TTL.
            global _bindings_cache
            _bindings_cache = (0.0, [])
        # A single bounded retry tolerates a dropped packet or the firmware's
        # 50 ms reply throttle; no host scan and no repeated credential probes.
        found = receive(min(deadline, time.monotonic()+.25))
        if found:
            return found
        for sock, broadcast in broadcasts:
            if time.monotonic() >= deadline:
                break
            try:
                sock.sendto(wire, (broadcast, port))
            except OSError:
                pass
        return receive(deadline)
    finally:
        for sock in sockets:
            sock.close()
