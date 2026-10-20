"""LAN configuration, ownership and connection export boundaries (isolated files)."""
import asyncio
import json
from pathlib import Path
import tempfile
import socket
import unittest
from unittest.mock import AsyncMock, patch

import operit_service as service


class OperitServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='AI Doll 统一入口 ')
        self.root = Path(self.temp.name)
        self.patches = [patch.object(service, 'ROOT', self.root),
                        patch.object(service, 'WORK', self.root / 'build/device-lab/operit'),
                        patch.object(service, 'lan_addresses', return_value=['192.168.1.20'])]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_single_address_and_saved_modes(self):
        self.assertTrue(service.save('simulation')['saved'])
        self.assertEqual(service.config()['host'], '192.168.1.20')
        self.assertFalse(service.status()['background_chat_verified'])
        with patch.object(service, 'lan_addresses', return_value=['192.168.1.30']):
            with self.assertRaisesRegex(ValueError, '网络已变化'):
                service.config()

    def test_multiple_addresses_require_choice_and_never_bind_all_interfaces(self):
        with patch.object(service, 'lan_addresses', return_value=['192.168.1.20', '10.0.0.3']):
            with self.assertRaises(ValueError):
                service.save('simulation')
            for host in ('0.0.0.0', '127.0.0.1', '203.0.113.10'):
                with self.assertRaises(ValueError):
                    service.save('simulation', host)

    def test_running_mode_change_that_cannot_stop_preserves_configuration(self):
        service.save('simulation')
        before = service.config()
        with patch.object(service, 'alive', return_value=True), patch.object(service, 'terminate') as terminate:
            with self.assertRaisesRegex(ValueError, '原配置保留'):
                service.save('device')
            terminate.assert_called_once()
        self.assertEqual(service.config(), before)

    def test_changed_address_stops_only_owned_service_and_keeps_private_path_history_and_port(self):
        service.save('device')
        current = service.config()
        current['port'] = 8778
        service.write_json(service.WORK / 'settings-private.json', current)
        previous_url = service.address(current)
        history = service.WORK / 'history.sqlite3'
        history.write_bytes(b'preserve personal history')
        process = {'pid': 123, 'fixture': True}
        service.write_json(service.WORK / 'process-private.json', process)
        with patch.object(service, 'lan_addresses', return_value=['192.168.1.30']), \
                patch.object(service, 'alive', side_effect=[True, False]), \
                patch.object(service, 'terminate') as terminate:
            changed = service.save('device', '192.168.1.30')
        terminate.assert_called_once_with(process)
        self.assertTrue(changed['saved'])
        saved = service.read(service.WORK / 'settings-private.json')
        self.assertEqual(saved['port'], 8778)
        self.assertEqual(service.address(saved), previous_url.replace('192.168.1.20', '192.168.1.30'))
        self.assertEqual(history.read_bytes(), b'preserve personal history')

    def test_stale_address_status_guides_manual_phone_update_without_exposing_private_path(self):
        service.save('device')
        private_url = service.address(service.config())
        with patch.object(service, 'lan_addresses', return_value=['192.168.1.30']):
            result = service.status()
        self.assertFalse(result['host_available'])
        self.assertEqual(result['addresses'], ['192.168.1.30'])
        self.assertEqual(result['port'], 8775)
        self.assertIn('无需重新导入或绑定聊天', result['error'])
        self.assertNotIn(private_url.rsplit('/', 2)[1], json.dumps(result))

    def test_repeated_start_reuses_owned_process_and_discovers_real_tools(self):
        service.save('simulation')
        with patch.object(service, 'alive', return_value=True), \
                patch.object(service, 'launch') as launch, \
                patch.object(service, 'protocol_check', new=AsyncMock(return_value={'protocol_connected': True, 'tool_count': 19})):
            result = service.start()
            self.assertTrue(result['reused'])
            self.assertEqual(result['tool_count'], 19)
            launch.assert_not_called()

    def test_export_requires_connection_check_and_contains_only_phone_connection(self):
        service.save('simulation')
        with patch.object(service, 'status', return_value={'protocol_connected': False}):
            with self.assertRaises(ValueError):
                service.export_connection()
        with patch.object(service, 'status', return_value={'protocol_connected': True}):
            value = service.export_connection()
        self.assertEqual(value['kind'], 'ai-doll-operit-connection')
        self.assertEqual(set(value), {'schema', 'kind', 'mcp_url', 'mode', 'label', 'version'})
        self.assertEqual(value['mcp_url'], service.address(service.config()), 'address persists across exports')

    def test_pid_reuse_or_foreign_process_never_terminated(self):
        service.save('simulation')
        with patch.object(service, 'alive', return_value=False), patch.object(service, 'terminate') as terminate:
            self.assertTrue(service.stop()['stopped'])
            terminate.assert_not_called()

    def test_stopping_preserves_history_and_saved_configuration(self):
        service.save('simulation')
        history = self.root / 'build/operit-demo/simulation.sqlite3'
        history.parent.mkdir(parents=True)
        history.write_bytes(b'preserved fixture')
        service.stop()
        self.assertEqual(history.read_bytes(), b'preserved fixture')
        self.assertEqual(service.config()['mode'], 'simulation')


class OperitOwnedProcessIntegrationTests(unittest.TestCase):
    def test_real_simulation_process_restart_and_reuse_in_isolated_folder(self):
        addresses = service.lan_addresses()
        if not addresses:
            self.skipTest('No actual LAN interface available')
        host = addresses[0]
        with tempfile.TemporaryDirectory(prefix='AI Doll 进程验收 ') as temporary, \
                patch.object(service, 'WORK', Path(temporary)):
            service.save('simulation', host)
            with socket.socket() as listener:
                listener.bind((host, 0))
                port = listener.getsockname()[1]
            cfg = service.config()
            cfg['port'] = port
            service.write_json(service.WORK / 'settings-private.json', cfg)
            try:
                first = service.start()
                self.assertFalse(first['reused'])
                self.assertEqual(first['tool_count'], 19)
                record = service.read(service.WORK / 'process-private.json')
                self.assertTrue(service.start()['reused'])
                self.assertEqual(service.read(service.WORK / 'process-private.json'), record)
                address = service.export_connection()['mcp_url']
                self.assertTrue(service.status(verify=True)['protocol_connected'])
                service.stop()
                self.assertFalse(service.status()['running'])
                self.assertTrue((service.WORK / 'simulation/simulation.sqlite3').is_file())
                self.assertTrue(service.start()['protocol_connected'])
                self.assertEqual(service.export_connection()['mcp_url'], address)
            finally:
                service.stop()


if __name__ == '__main__':
    unittest.main()
