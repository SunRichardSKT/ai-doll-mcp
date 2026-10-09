"""Explicit local-file OTA; never downloads images or reads third-party credentials."""
import argparse
import base64
import hashlib
import ipaddress
import json
import pathlib
import time
import urllib.error
import urllib.request

TARGET = 'ai-doll-supermini-v1'
MAX_IMAGE = 0x140000


def validate_image(image, manifest):
    if manifest.get('chip') != 'esp32c3' or manifest.get('target') != TARGET:
        raise ValueError('Manifest must identify ai-doll-supermini-v1 / esp32c3')
    entries = [entry for entry in manifest.get('images', [])
               if entry.get('file') == 'firmware.bin']
    if len(entries) != 1:
        raise ValueError('Manifest must contain exactly one firmware.bin')
    entry = entries[0]
    if type(entry.get('bytes')) is not int or not 288 <= len(image) <= MAX_IMAGE or len(image) != entry['bytes']:
        raise ValueError('Application size differs from manifest or partition capacity')
    digest = hashlib.sha256(image).hexdigest()
    if digest != entry.get('sha256'):
        raise ValueError('Application SHA-256 differs from manifest')
    if image[0] != 0xe9 or int.from_bytes(image[12:14], 'little') != 5 or image[32:36] != bytes.fromhex('3254cdab'):
        raise ValueError('Expected an ESP32-C3 application image, not merged flash or bootloader')
    if not str(manifest.get('firmware', '')).startswith('doll-lab-'):
        raise ValueError('Manifest firmware version required')
    return {'bytes': len(image), 'sha256': digest, 'target': TARGET, 'chip': 'esp32c3'}


class OtaClient:
    def __init__(self, host, config):
        address = ipaddress.ip_address(host)
        if address.version != 4 or not address.is_private or address.is_unspecified or address.is_multicast:
            raise ValueError('Use a private LAN IPv4 device address')
        self.base = 'http://' + str(address)
        self.headers = {'Content-Type': 'application/json', 'X-Setup-Token': config['mcp_token'],
                        'Authorization': 'Basic ' + base64.b64encode(
                            ('admin:' + config['ap_password']).encode()).decode()}
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, path, data=None):
        req = urllib.request.Request(self.base + path, headers=self.headers,
                                     data=None if data is None else json.dumps(data).encode())
        try:
            with self.opener.open(req, timeout=15) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                reason = json.loads(exc.read(6000)).get('error', 'Device rejected request')
            except (ValueError, UnicodeDecodeError):
                reason = 'Device rejected request'
            raise ValueError('OTA HTTP ' + str(exc.code) + ': ' + str(reason)) from None
        if result.get('error'):
            raise ValueError(str(result['error']))
        return result

    def upload(self, image, manifest, progress=None):
        metadata = validate_image(image, manifest)
        before = self.request('/api/status')
        if before.get('ota', {}).get('active') or before.get('ota', {}).get('pending_verification'):
            raise ValueError('Device busy; wait for startup verification')
        started = self.request('/api/ota', dict(metadata, action='start', confirmed=True))
        ticket = started['ticket']
        try:
            size = min(3072, int(started['chunk_bytes']))
            if size < 288:
                raise ValueError('Invalid device chunk size')
            for offset in range(0, len(image), size):
                chunk = image[offset:offset + size]
                reply = self.request('/api/ota', {'action': 'chunk', 'ticket': ticket,
                                     'offset': offset, 'data': base64.b64encode(chunk).decode()})
                if reply.get('received_bytes') != offset + len(chunk):
                    raise ValueError('Device offset mismatch')
                if progress:
                    progress(offset + len(chunk), len(image))
            self.request('/api/ota', {'action': 'finish', 'ticket': ticket})
        except Exception:
            # No automatic write retries. A lost finish reply may already mean
            # committed; abort cannot undo that. Always inspect the next boot.
            try:
                self.request('/api/ota', {'action': 'abort', 'ticket': ticket})
            except Exception:
                pass
            raise
        deadline = time.monotonic() + 90
        last = None
        while time.monotonic() < deadline:
            time.sleep(1)
            try:
                last = self.request('/api/status')
            except (OSError, ValueError):
                continue
            if (last.get('boot_id') != before.get('boot_id') and
                    not last.get('ota', {}).get('pending_verification')):
                if last.get('firmware') != manifest['firmware']:
                    raise ValueError('Device rebooted into a different version (possible rollback)')
                return {'ok': True, 'firmware': last['firmware'], 'boot_id': last['boot_id'],
                        'partition': last['ota']['running_partition'], 'sha256': metadata['sha256']}
        raise TimeoutError('Image sent, but new boot was not verified; inspect device before retrying')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--config', type=pathlib.Path, required=True, help='Private paired device config')
    parser.add_argument('--firmware', type=pathlib.Path, required=True)
    parser.add_argument('--manifest', type=pathlib.Path, required=True)
    parser.add_argument('--confirm', action='store_true', help='Explicitly authorize writing firmware')
    args = parser.parse_args()
    image = args.firmware.read_bytes()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    validate_image(image, manifest)
    if not args.confirm:
        parser.error('Review files, then add --confirm to write the device')
    client = OtaClient(args.host, json.loads(args.config.read_text(encoding='utf-8')))
    last_percent = [-1]
    def progress(done, total):
        percent = done * 100 // total
        if percent // 10 != last_percent[0] // 10:
            print(str(percent) + '%', flush=True)
            last_percent[0] = percent
    print(json.dumps(client.upload(image, manifest, progress), ensure_ascii=False))


if __name__ == '__main__':
    main()
