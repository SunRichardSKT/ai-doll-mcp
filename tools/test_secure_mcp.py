"""Secure deployment fault paths and fresh evidence, independent of Chat acceptance."""
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import zipfile

import install_tunnel_client as installer
import secure_mcp as service
from verify_chat_calls import correlate
from private_storage import write_json

FIXTURE_ID = 'tunnel_' + 'a' * 32
FIXTURE_KEY = 'sk-' + '0' * 32  # Generated test value; never an issued credential.


class SecureDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        service.configure(self.folder, FIXTURE_ID, FIXTURE_KEY)
        self.cfg = service.configuration(self.folder)

    def tearDown(self):
        self.temp.cleanup()

    def alias_record(self, **changes):
        value = dict(alias=self.cfg['alias'], tunnel_id=FIXTURE_ID,
                     config_path=str(self.folder / 'profiles' / (self.cfg['alias'] + '.yaml')))
        value.update(changes)
        write_json(self.folder / 'native-state/aliases.yaml', {self.cfg['alias']: value})

    def test_invalid_config_keeps_previous_key_and_id(self):
        before = (self.folder / 'secure-private.json').read_bytes()
        for tunnel, key in ((FIXTURE_ID+'/', FIXTURE_KEY), (FIXTURE_ID, 'sk-admin-12345678901234')):
            with self.assertRaises(service.SecureError):
                service.configure(self.folder, tunnel, key)
        self.assertEqual(before, (self.folder / 'secure-private.json').read_bytes())
        service.configure(self.folder, FIXTURE_ID)
        self.assertEqual(service.configuration(self.folder)['runtime_api_key'], FIXTURE_KEY)

    def test_changed_configuration_stops_using_old_target_before_commit(self):
        seen = []
        with patch.object(service, '_stop', side_effect=lambda folder, cfg: seen.append(cfg.copy())):
            service.configure(self.folder, 'tunnel_'+'b'*32, profile='history')
        self.assertEqual(seen[0]['tunnel_id'], FIXTURE_ID)
        self.assertEqual(service.configuration(self.folder)['profile'], 'history')
        self.assertEqual(service.configuration(self.folder)['alias'], self.cfg['alias'])

    def test_native_alias_mismatch_is_never_stopped(self):
        self.alias_record(tunnel_id='tunnel_'+'b'*32)
        with patch.object(service, 'native') as native:
            with self.assertRaises(service.SecureError): service.stop(self.folder)
            native.assert_not_called()

    def test_foreign_gateway_record_is_never_killed(self):
        write_json(self.folder / 'gateway-process-private.json', dict(entry='another-script.py'))
        with patch.object(service, 'terminate') as terminate:
            with self.assertRaises(service.SecureError): service.stop(self.folder)
            terminate.assert_not_called()

    def test_native_environment_is_isolated_and_uses_existing_proxy(self):
        result = subprocess.CompletedProcess([], 0, b'{"aliases":[]}', b'')
        def directory(path):
            Path(path).mkdir(parents=True, exist_ok=True)
            return Path(path)
        with patch.object(service, 'install_client', return_value=(Path('official.exe'), 'v0.0.16')), \
             patch.object(service, 'private_directory', side_effect=directory), \
             patch.object(service, 'write_json'), \
             patch.dict(os.environ, {'OPENAI_API_KEY': 'unrelated-key', 'OPENAI_ADMIN_KEY': 'unrelated-admin'}), \
             patch.object(service.urllib.request, 'getproxies', return_value={'https': 'http://127.0.0.1:7897'}), \
             patch.object(service.subprocess, 'run', return_value=result) as run:
            service.native(self.folder, ['list'])
        env = run.call_args.kwargs['env']
        self.assertEqual(env['TUNNEL_CLIENT_STATE_DIR'], str(self.folder / 'native-state'))
        self.assertEqual(env['CONTROL_PLANE_HTTP_PROXY'], 'http://127.0.0.1:7897')
        self.assertIn('127.0.0.1', env['NO_PROXY'])
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertNotIn('OPENAI_ADMIN_KEY', env)
        self.assertNotIn(FIXTURE_KEY, str(run.call_args))

    def test_observation_timeout_does_not_stop_or_start_another_daemon(self):
        with patch.object(service, 'install_client', return_value=(Path('official.exe'), 'v0.0.16')), \
             patch.object(service.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fixture', 1)), \
             patch.object(service, 'private_directory', side_effect=lambda path: Path(path)), \
             patch.object(service, 'terminate') as terminate:
            with self.assertRaises(service.SecureError): service.native(self.folder, ['list'])
            terminate.assert_not_called()

    def test_existing_runtime_is_reused_even_during_network_backoff(self):
        self.alias_record()
        payload = dict(alias=self.cfg['alias'], tunnel_id=FIXTURE_ID, process_running=True,
                       healthy=True, ready=True)
        with patch('companion_mcp.get_installation_status', return_value={'database_open': True}), \
             patch.object(service, 'ensure_gateway', return_value=True), \
             patch.object(service, 'verify_local', return_value={}), \
             patch.object(service, 'status', return_value={'tunnel_connected': False}), \
             patch.object(service, 'native', return_value=payload) as native:
            result = service.start(self.folder)
        self.assertTrue(result['gateway_reused'])
        self.assertEqual([call.args[1][0] for call in native.call_args_list], ['status'])

    def test_connect_uses_file_reference_and_only_scoped_http_gateway(self):
        with patch('companion_mcp.get_installation_status', return_value={'database_open': True}), \
             patch.object(service, 'ensure_gateway', return_value=False), \
             patch.object(service, 'verify_local', return_value={}), \
             patch.object(service, 'status', return_value={}), \
             patch.object(service, 'native', return_value={}) as native:
            service.start(self.folder)
        args = native.call_args.args[1]
        self.assertEqual(args[0], 'connect')
        self.assertEqual(args[args.index('--tunnel-id')+1], FIXTURE_ID)
        self.assertTrue(args[args.index('--runtime-api-key')+1].startswith('file:'))
        self.assertIn('127.0.0.1:8774/', args[args.index('--mcp-server-url')+1])
        self.assertNotIn(FIXTURE_KEY, ' '.join(args))
        self.assertNotIn('--mcp-command', args)

    def test_reset_invalidates_old_address_even_if_native_stop_fails(self):
        store = service.CapabilityStore(self.folder / 'gateway')
        before = store.key()
        with patch.object(service, '_stop', side_effect=service.SecureError('fixture')):
            with self.assertRaises(service.SecureError): service.reset_address(self.folder)
        self.assertNotEqual(before, store.key())

    def test_poll_success_requires_fresh_read_and_recent_success(self):
        now = time.time()
        stamp = lambda value: dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat()
        details = dict(last_success=stamp(now-5), consecutive_failures=0, deadline_seconds=65,
                       current_poll_age_seconds=4)
        component = dict(status='ok', state='polling', details=details)
        health = dict(snapshot_at=stamp(now), components={'control-plane': component})
        self.assertTrue(service.poll_observation(health, now)['connected'])
        health['snapshot_at'] = stamp(now-30)
        self.assertFalse(service.poll_observation(health, now)['connected'])
        health['snapshot_at'] = stamp(now)
        details['last_success'] = stamp(now-600)
        self.assertFalse(service.poll_observation(health, now)['connected'])
        details.update(last_success=stamp(now-5), consecutive_failures=1, http_status=403)
        self.assertFalse(service.poll_observation(health, now)['connected'])

    def test_health_never_fetches_a_remote_or_redirect_target(self):
        for url in ('https://example.com/health', 'http://example.com/health', 'http://user@127.0.0.1:1/'):
            with self.assertRaises(service.SecureError): service.local_health(url)


class OfficialInstallerTests(unittest.TestCase):
    def test_checksum_mismatch_never_extracts_or_executes(self):
        with tempfile.TemporaryDirectory() as folder:
            sums = ('0'*64 + '  tunnel-client-v0.0.16-windows-amd64.zip\n').encode()
            with patch.object(installer.platform, 'machine', return_value='AMD64'), \
                 patch.object(installer, 'fetch', side_effect=[(sums, 'https://github.com'), (b'bad', 'https://github.com')]), \
                 patch.object(installer, 'extract_verified') as extract:
                with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                    installer.install(Path(folder), version='v0.0.16')
                extract.assert_not_called()

    def test_archive_rejected_before_any_member_is_extracted(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('safe.txt', 'safe')
            archive.writestr('../escape.txt', 'unsafe')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, 'Unsafe member'):
                installer.extract_verified(stream.getvalue(), Path(folder))
            self.assertFalse((Path(folder) / 'safe.txt').exists())

    def test_tampered_cached_binary_is_not_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / 'tunnel-client.exe').write_bytes(b'tampered')
            (folder / 'installed.json').write_text(json.dumps(dict(version='v0.0.16',
                executable='tunnel-client.exe', executable_sha256=hashlib.sha256(b'original').hexdigest())))
            with self.assertRaisesRegex(RuntimeError, 'invalid'): installer.installed(folder)


class ChatAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        write_json(self.folder / 'gateway/gateway.json', {'run_id': 'current', 'profile': 'interaction'})
        self.calls = [dict(call_id='c'*32, tool='get_installation_status', run_id='current',
                           profile='interaction', completed=True),
                      dict(call_id='d'*32, tool='doll_get_status', run_id='current',
                           profile='interaction', completed=True)]
        self.write_audit()

    def write_audit(self):
        (self.folder / 'gateway/calls.jsonl').write_text('\n'.join(json.dumps(value) for value in self.calls))

    def tearDown(self):
        self.temp.cleanup()

    def test_correct_status_ids_do_not_claim_interaction_or_idle_wake(self):
        proof = correlate(self.folder, 'c'*32, 'd'*32)
        self.assertTrue(proof['status_calls_correlated'])
        self.assertFalse(proof['interaction_feedback_verified'])
        self.assertFalse(proof['idle_wake_verified'])

    def test_failed_or_previous_run_cannot_be_accepted(self):
        for changes in ({'completed': False}, {'run_id': 'previous'}, {'execution_may_continue': True}):
            original = self.calls[0].copy()
            self.calls[0].update(changes)
            self.write_audit()
            with self.assertRaises(ValueError): correlate(self.folder, 'c'*32, 'd'*32)
            self.calls[0] = original
        self.assertFalse((self.folder / 'chat-status-acceptance-private.json').exists())

    def test_sdk_call_id_does_not_replace_chat_evidence(self):
        write_json(self.folder / 'local-calls-private.json', dict(status_calls={
            'get_installation_status': {'verification': {'call_id': 'c'*32}}}))
        with self.assertRaisesRegex(ValueError, 'SDK'): correlate(self.folder, 'c'*32, 'd'*32)


if __name__ == '__main__':
    unittest.main()
