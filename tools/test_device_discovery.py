"""Discovery authentication, real UDP round-trip and recovery replay boundaries."""
import json
import pathlib
import socket
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from device_discovery import (PROTOCOL, discover_paired_device, interface_bindings,
                              signature, verify_reply)
from device_transport import DeviceConnectionError, WifiLink, create_device_link

TOKEN = 'unit-test-token-0123456789abcdef'
DEVICE = 'AI-Doll-abcdef'
CONFIG = {'mcp_token': TOKEN, 'device_id': DEVICE}
NONCE = '12' * 16


def reply(nonce=NONCE, **overrides):
    data = dict(protocol=PROTOCOL, nonce=nonce, device_id=DEVICE, port=80,
                firmware='doll-lab-2.4.0')
    data['proof'] = signature(TOKEN, nonce, DEVICE, data['firmware'])
    data.update(overrides)
    return json.dumps(data).encode()


class DiscoveryTests(unittest.TestCase):
    def test_authentication_and_sender_address(self):
        found = verify_reply(reply(), ('10.97.128.103', 28768), NONCE, DEVICE, TOKEN)
        self.assertEqual(found['device_host'], '10.97.128.103')
        self.assertTrue(found['verified'])
        self.assertNotIn(TOKEN, json.dumps(found))
        self.assertNotIn('proof', found)
        raw = reply(host='8.8.8.8')
        self.assertEqual(verify_reply(raw, ('10.0.1.5', 1), NONCE, DEVICE, TOKEN)['device_host'], '10.0.1.5')

    def test_forged_stale_and_malformed_replies_are_ignored(self):
        for raw in (reply(proof='0'*64), reply(nonce='34'*16), reply(device_id='AI-Doll-111111'),
                    reply(port=True), reply(port=81), reply(protocol='other'), reply(firmware='x\ny'),
                    b'[]', b'null', b'"hello"', b'bad-json', b'x'*2049):
            with self.subTest(raw=raw[:32]):
                self.assertIsNone(verify_reply(raw, ('10.0.0.1', 1), NONCE, DEVICE, TOKEN))
        self.assertIsNone(verify_reply(reply(), ('10.0.0.1', 1), NONCE, DEVICE, 'different-token'))

    def test_discovery_never_accepts_public_loopback_or_link_local(self):
        for host in ('8.8.8.8', '127.0.0.1', '169.254.2.1', '0.0.0.0', '224.0.0.1', '::1'):
            self.assertIsNone(verify_reply(reply(), (host, 1), NONCE, DEVICE, TOKEN))

    def test_actual_udp_challenge_contains_no_credentials(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('127.0.0.1', 0))
        sock.settimeout(3)
        errors = []

        def respond():
            try:
                raw, source = sock.recvfrom(4096)
                request = json.loads(raw)
                self.assertEqual(set(request), {'protocol', 'nonce', 'device_id'})
                self.assertNotIn(TOKEN.encode(), raw)
                sock.sendto(reply(request['nonce'], proof='invalid'), source)
                sock.sendto(reply(request['nonce']), source)
            except Exception as exc:
                errors.append(exc)

        worker = threading.Thread(target=respond)
        worker.start()
        try:
            found = discover_paired_device(CONFIG, timeout=1,
                    bindings=[('127.0.0.1', '127.0.0.1')], port=sock.getsockname()[1])
            self.assertEqual(found['device_id'], DEVICE)
        finally:
            worker.join(4)
            sock.close()
        self.assertFalse(errors)

    def test_no_reply_and_missing_pairing_are_bounded(self):
        self.assertIsNone(discover_paired_device(CONFIG, timeout=.1, bindings=[]))
        for cfg in ({}, {'device_id': DEVICE}, dict(CONFIG, device_id='other\nline'),
                    dict(CONFIG, mcp_token='unsafe\nheader')):
            with self.assertRaises(ValueError):
                discover_paired_device(cfg, bindings=[])
        for timeout in (True, 0, 10, '1'):
            with self.assertRaises(ValueError):
                discover_paired_device(CONFIG, timeout, bindings=[])

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows adapter discovery')
    def test_actual_prefixes_and_adapter_filtering(self):
        rows = [dict(IPAddress='10.97.128.106', PrefixLength=20),
                dict(IPAddress='192.168.1.19', PrefixLength=24),
                dict(IPAddress='127.0.0.1', PrefixLength=8),
                dict(IPAddress='169.254.4.2', PrefixLength=16),
                dict(IPAddress='8.8.8.8', PrefixLength=24)]
        with patch('device_discovery.subprocess.run', return_value=Mock(returncode=0,stdout=json.dumps(rows).encode())) as run:
            self.assertEqual(interface_bindings(), [('10.97.128.106', '10.97.143.255'),
                                                   ('192.168.1.19', '192.168.1.255')])
            self.assertIn('-NonInteractive', run.call_args.args[0])

    def link(self):
        found = dict(device_host='10.0.0.2', device_id=DEVICE, firmware='doll-lab-2.4.0', verified=True)
        discover = Mock(return_value=found)
        return WifiLink('10.0.0.1', CONFIG, discovery=discover), discover

    def test_read_recovers_once_at_verified_address(self):
        link, discover = self.link()
        with patch.object(link, '_exchange_once', side_effect=[DeviceConnectionError('offline'), {'ok':True}]) as call:
            self.assertTrue(link.exchange({'cmd':'status'})['ok'])
            self.assertEqual(call.call_count, 2)
        self.assertEqual(link.host, '10.0.0.2')
        discover.assert_called_once()

    def test_mutations_unknown_tools_and_wifi_changes_never_replay(self):
        for cmd in ({'cmd':'wifi'}, {'cmd':'scan'}, {'cmd':'rpc','request':{'method':'tools/call','params':{'name':'set_vibration'}}},
                    {'cmd':'rpc','request':{'method':'tools/call','params':{'name':'set_channel_config'}}},
                    {'cmd':'rpc','request':{'method':'tools/call','params':{'name':'get_unknown_future_tool'}}}):
            link, discover = self.link()
            with patch.object(link, '_exchange_once', side_effect=DeviceConnectionError('timeout')) as call:
                with self.assertRaises(DeviceConnectionError):
                    link.exchange(cmd)
                self.assertEqual(call.call_count, 1)
            discover.assert_not_called()

    def test_failed_or_same_address_discovery_is_rate_limited(self):
        link, discover = self.link()
        discover.return_value = None
        with patch.object(link, '_exchange_once', side_effect=DeviceConnectionError('offline')) as call:
            for _ in range(3):
                with self.assertRaises(DeviceConnectionError):
                    link.exchange({'cmd':'events'})
            self.assertEqual(call.call_count, 3)
        discover.assert_called_once()
        link, discover = self.link()
        discover.return_value['device_host'] = link.host
        with patch.object(link, '_exchange_once', side_effect=DeviceConnectionError('offline')) as call:
            with self.assertRaises(DeviceConnectionError):
                link.exchange({'cmd':'status'})
            self.assertEqual(call.call_count, 1)

    def test_save_failure_preserves_current_address(self):
        link, _ = self.link()
        link.on_recovered = Mock(side_effect=OSError('write failed'))
        with self.assertRaises(OSError):
            link.discover(True)
        self.assertEqual(link.host, '10.0.0.1')

    def test_explicit_discovery_and_atomic_saved_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            cfg, saved = root/'private.json', root/'connection.json'
            cfg.write_text(json.dumps(CONFIG), encoding='utf-8')
            link, info = create_device_link({'DOLL_TRANSPORT':'wifi','DOLL_DEVICE_HOST':'10.0.0.1'}, cfg, saved)
            _, discovery = self.link()
            link.discovery = discovery
            self.assertFalse(link.discover()['updated'])
            self.assertEqual(link.host, '10.0.0.1')
            self.assertTrue(link.discover(True)['updated'])
            self.assertEqual(info['device_host'], '10.0.0.2')
            self.assertEqual(json.loads(saved.read_text())['device_host'], '10.0.0.2')
            self.assertNotIn(TOKEN, saved.read_text())
            self.assertFalse(saved.with_suffix('.tmp').exists())


if __name__ == '__main__':
    unittest.main()
