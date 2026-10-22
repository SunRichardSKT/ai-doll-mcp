"""Management flow tests: bootstrap, credential transport, pairing and local HTTP boundaries."""
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

import control_panel as ui


class ControlPanelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.work = self.root / 'build/device-lab'
        self.work.mkdir(parents=True)
        self.patches = [patch.object(ui, 'ROOT', self.root), patch.object(ui, 'WORK', self.work),
                        patch.object(ui.Panel, 'check_environment', return_value=False)]
        for item in self.patches: item.start()
        self.panel = ui.Panel()

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()

    def put(self, name, value):
        path = self.work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def test_daily_start_recovers_independent_routes_after_secure_failure(self):
        self.panel.ready=True
        self.put('connection-private.json', {'transport':'wifi'})
        self.put('operit/settings-private.json', {'enabled':True,'mode':'device'})
        self.put('secure-mcp/secure-private.json', {'runtime_api_key':'fixture'})
        calls=[]
        def run(action, data=None):
            calls.append(action)
            if action in ('secure-start','secure-repair'):raise ValueError('network unavailable')
            return {'running':True}
        with patch.object(self.panel,'run_worker',side_effect=run):
            result=self.panel.perform('repair-connection',{})
        self.assertIn('operit-start',calls)
        self.assertIn('client-config',calls)
        self.assertTrue(result['operit']['running'])
        self.assertIn('secure',result['errors'])
        self.assertIn('network unavailable',result['message'])

    def test_collector_timeout_does_not_block_simulation_or_config(self):
        self.panel.ready=True
        self.put('operit/settings-private.json', {'enabled':True,'mode':'device'})
        def run(action, data=None):
            if action=='collector-start':raise subprocess.TimeoutExpired('collector',1)
            return {'running':True}
        with patch.object(self.panel,'run_worker',side_effect=run):
            result=self.panel.perform('daily-start',{})
        self.assertIn('collector',result['errors'])
        self.assertTrue(result['operit']['running'])

    def test_bootstrap_without_sdk_or_pairing(self):
        self.assertFalse(self.panel.state()['environment_ready'])
        with self.assertRaisesRegex(ValueError, '准备运行环境'):
            self.panel.perform('pair', {})

    def test_usb_shortcut_reads_identity_then_pairs_over_wifi(self):
        from device_lab import SerialLink
        with patch.object(SerialLink, '__init__', return_value=None), \
             patch.object(SerialLink, 'exchange', side_effect=[
                 {'wifi_connected': True, 'ip': '192.168.1.50'},
                 {'mcp_token': 'fixture-token', 'admin_user': 'owner'}]), \
             patch.object(SerialLink, 'close') as close, \
             patch.object(ui, 'pair_device', return_value={'paired': True}) as pair:
            self.assertTrue(ui.worker('usb-pair-wifi', {'port': 'COM3'})['paired'])
        close.assert_called_once()
        self.assertEqual(pair.call_args.args[0]['host'], '192.168.1.50')
        self.assertEqual(pair.call_args.args[0]['token'], 'fixture-token')

    def test_usb_shortcut_offline_does_not_overwrite_pairing(self):
        from device_lab import SerialLink
        with patch.object(SerialLink, '__init__', return_value=None), \
             patch.object(SerialLink, 'exchange', side_effect=[{'wifi_connected': False}, {}]), \
             patch.object(SerialLink, 'close') as close, patch.object(ui, 'pair_device') as pair:
            with self.assertRaisesRegex(ValueError, '配网'):
                ui.worker('usb-pair-wifi', {'port': 'COM3'})
        close.assert_called_once(); pair.assert_not_called()

    def test_usb_shortcut_is_reachable_from_the_real_panel_endpoint(self):
        self.panel.ready=True
        server=ui.ExclusiveLoopbackServer(('127.0.0.1',0),ui.make_handler(self.panel))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with patch.object(self.panel,'run_worker',return_value={'paired':True}) as run:
                request=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/action',
                    data=json.dumps({'action':'usb-pair-wifi','data':{'port':'COM3'}}).encode(),
                    headers={'Content-Type':'application/json','X-CSRF-Token':self.panel.csrf})
                with ui.OPENER.open(request,timeout=2) as response:self.assertEqual(response.status,202)
                deadline=time.monotonic()+2
                while self.panel.job['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
                self.assertEqual(self.panel.job['state'],'done')
                run.assert_called_once_with('usb-pair-wifi',{'port':'COM3'})
        finally:server.shutdown();server.server_close();thread.join(2)

    def test_state_omits_all_saved_credentials(self):
        self.put('device-private.json', dict(mcp_token='DEVICE_TEST_SECRET', device_id='AI-Doll-aaaaaa', ap_password='ADMIN_TEST_SECRET'))
        self.put('secure-mcp/secure-private.json', dict(runtime_api_key='RUNTIME_TEST_SECRET', tunnel_id='tunnel_'+'a'*32, profile='history'))
        raw = json.dumps(self.panel.state())
        for value in ('DEVICE_TEST_SECRET', 'ADMIN_TEST_SECRET', 'RUNTIME_TEST_SECRET'):
            self.assertNotIn(value, raw)
        self.assertTrue(self.panel.state()['secure_config']['key_saved'])

    def test_device_settings_entry_requires_csrf_and_reads_credentials_only_on_demand(self):
        server=ui.ExclusiveLoopbackServer(('127.0.0.1',0),ui.make_handler(self.panel))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_port}/api/device-settings'
        try:
            with patch.object(ui,'request_collector') as collect:
                with self.assertRaises(urllib.error.HTTPError) as denied:ui.OPENER.open(url,timeout=2)
                self.assertEqual(denied.exception.code,403);collect.assert_not_called()
                collect.side_effect=[{'wifi_connected':True,'ip':'192.168.1.23'},{'mcp_token':'fixture-paired-token'}]
                req=urllib.request.Request(url,headers={'X-CSRF-Token':self.panel.csrf})
                with ui.OPENER.open(req,timeout=2) as response:entry=json.load(response)
                self.assertEqual(entry['url'],'http://192.168.1.23/#setup_token=fixture-paired-token')
                collect.side_effect=OSError('collector offline')
                self.assertNotIn('fixture-paired-token',json.dumps(self.panel.state()))
                collect.side_effect=[{'wifi_connected':False,'ip':'0.0.0.0'}]
                with self.assertRaises(urllib.error.HTTPError) as offline:ui.OPENER.open(req,timeout=2)
                self.assertEqual(offline.exception.code,400)
        finally:server.shutdown();server.server_close();thread.join(2)

    def test_credentials_go_on_stdin_not_command_line(self):
        completed = subprocess.CompletedProcess([], 0, '{"paired":true}\n', '')
        with patch.object(ui.subprocess, 'run', return_value=completed) as run:
            self.panel.run_worker('pair', {'token': 'DEVICE_TEST_SECRET'})
        self.assertNotIn('DEVICE_TEST_SECRET', str(run.call_args.args))
        self.assertIn('DEVICE_TEST_SECRET', run.call_args.kwargs['input'])

    def test_pairing_failure_preserves_existing_configuration_and_service(self):
        from device_transport import WifiLink
        path = self.put('device-private.json', dict(mcp_token='a'*32, device_id='AI-Doll-aaaaaa'))
        before = path.read_bytes()
        with patch.object(WifiLink, 'exchange', side_effect=ValueError('offline')), patch.object(ui, 'collector_stop') as stop:
            with self.assertRaisesRegex(ValueError, '原配置未修改'):
                ui.pair_device({'host': '192.168.1.10', 'token': 'b'*32})
            stop.assert_not_called()
        self.assertEqual(path.read_bytes(), before)

    def test_pairing_validates_then_restarts_project_service(self):
        from device_transport import WifiLink
        self.put('companion-private.json', {'token': 'c'*32})
        order = []
        with patch.object(WifiLink, 'exchange', side_effect=lambda _: order.append('validate') or {'device_id': 'AI-Doll-aaaaaa'}), \
             patch.object(ui, 'collector_stop', side_effect=lambda: order.append('stop')), \
             patch.object(ui, 'collector_start', side_effect=lambda: order.append('start')):
            result = ui.pair_device({'host': '192.168.1.10', 'token': 'b'*32})
        self.assertEqual(order, ['validate', 'stop', 'start'])
        self.assertEqual(result['device_host'], '192.168.1.10')
        self.assertEqual(ui.read_json(self.work / 'connection-private.json')['transport'], 'wifi')

    def test_install_failure_is_reported_without_losing_data(self):
        path = self.put('device-private.json', {'mcp_token': 'a'*32})
        before = path.read_bytes()
        self.panel.python.parent.mkdir(parents=True)
        self.panel.python.touch()
        with patch.object(ui.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, b'', b'')):
            with self.assertRaisesRegex(ValueError, '依赖安装失败'):
                self.panel.install()
        self.assertEqual(path.read_bytes(), before)

    def test_collector_stop_does_not_kill_unrelated_processes(self):
        with patch.object(ui, 'request_collector', side_effect=ValueError('Forbidden')):
            with self.assertRaisesRegex(ValueError, 'Forbidden'):
                ui.collector_stop()

    def test_shutdown_connection_reset_is_success_not_a_failed_stop(self):
        with patch.object(ui, 'request_collector', side_effect=[{'stopping': True}, ConnectionResetError()]):
            self.assertFalse(ui.collector_stop()['running'])

    def test_offline_device_check_keeps_collector_result(self):
        with patch.object(ui, 'collector_start'), \
             patch.object(ui, 'request_collector', side_effect=[{'database_open': True}, ValueError('offline')]):
            result = ui.worker('collector-check', {})
        self.assertTrue(result['installation']['database_open'])
        self.assertIsNone(result['device'])
        self.assertIn('历史仍可查询', result['device_error'])

    def test_usb_failure_explains_transport_and_suggests_discovery(self):
        with patch.object(ui,'collector_start'), \
             patch.object(ui,'request_collector',side_effect=[{'runtime':{'transport':'usb'}},ValueError('offline')]):
            result=ui.worker('collector-check',{})
        self.assertIn('USB',result['device_error'])
        self.assertIn('搜索',result['device_error'])
        self.assertIn('历史仍可查询',result['device_error'])

    def test_duplicate_actions_are_rejected_while_live_job_runs(self):
        started, release = threading.Event(), threading.Event()
        def action(*args):
            started.set(); release.wait(3); return {'ok': True}
        with patch.object(self.panel, 'perform', side_effect=action):
            self.panel.submit('install', {})
            self.assertTrue(started.wait(1))
            try:
                with self.assertRaisesRegex(ValueError, '上一项'):
                    self.panel.submit('install', {})
            finally:
                release.set()
            deadline = time.monotonic()+2
            while self.panel.job['state'] == 'running' and time.monotonic() < deadline: time.sleep(.01)
            self.assertEqual(self.panel.job['state'], 'done')

    def test_http_rejects_cross_origin_and_missing_csrf(self):
        server = ui.ExclusiveLoopbackServer(('127.0.0.1', 0), ui.make_handler(self.panel))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        try:
            for headers in ({}, {'X-CSRF-Token': self.panel.csrf, 'Origin': 'http://foreign.invalid'},
                            {'X-CSRF-Token': self.panel.csrf, 'Host': 'foreign.invalid'}):
                req = urllib.request.Request(base+'/api/state', headers=headers)
                with self.assertRaises(urllib.error.HTTPError) as error: ui.OPENER.open(req)
                self.assertEqual(error.exception.code, 403)
            with ui.OPENER.open(urllib.request.Request(base+'/api/state', headers={'X-CSRF-Token': self.panel.csrf})) as response:
                self.assertFalse(json.load(response)['environment_ready'])
                self.assertEqual(response.headers['X-Frame-Options'], 'DENY')
        finally:
            server.shutdown(); server.server_close(); thread.join(2)

    def test_unknown_action_never_runs_shell_or_worker(self):
        with patch.object(self.panel, 'run_worker') as run:
            with self.assertRaisesRegex(ValueError, '未知'):
                self.panel.submit('powershell', {'command': 'arbitrary'})
            run.assert_not_called()

    def test_ota_requires_confirmation_before_any_write(self):
        from ota_device import OtaClient
        with patch.object(OtaClient, 'upload') as upload:
            with self.assertRaisesRegex(ValueError, '确认'):
                ui.worker('ota', {'bundled': True})
            upload.assert_not_called()

    def test_ota_rejects_invalid_image_before_any_device_request(self):
        from ota_device import OtaClient
        self.put('connection-private.json', {'transport': 'wifi', 'device_host': '192.168.1.10'})
        self.put('device-private.json', {'ap_password': 'test-fixture', 'mcp_token': 'a'*32})
        with patch.object(OtaClient, 'upload') as upload:
            with self.assertRaises(ValueError):
                ui.worker('ota', {'confirmed': True, 'image_base64': 'AA==', 'manifest': {}})
            upload.assert_not_called()


if __name__ == '__main__':
    unittest.main()
