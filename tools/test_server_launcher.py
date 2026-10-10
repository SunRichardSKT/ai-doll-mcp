"""Real child-process tests for duplicate launches, ownership and restart persistence."""
import concurrent.futures
import json
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import patch

import start_direct_server as launcher
from owned_processes import alive, terminate


class ServerLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='AI Doll server ')
        self.folder = Path(self.temp.name)
        self.patches = [patch.object(launcher, 'FOLDER', self.folder),
                        patch.object(launcher, 'lan_ip', return_value='192.168.1.10')]
        for item in self.patches: item.start()
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0)); self.port = probe.getsockname()[1]

    def tearDown(self):
        owner = self.folder / 'process-private.json'
        if owner.exists(): terminate(json.loads(owner.read_text()))
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()

    def test_rapid_duplicate_launch_and_restart_keep_installation(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: launcher.ensure(self.port), range(2)))
        self.assertEqual(results[0]['browser_url'], results[1]['browser_url'])
        owner = json.loads((self.folder/'process-private.json').read_text())
        token = json.loads((self.folder/'server-private.json').read_text())['admin_token']
        before = launcher.status(results[0]['local_url'], token)
        launcher.ensure(self.port)
        self.assertEqual(owner, json.loads((self.folder/'process-private.json').read_text()))
        self.assertFalse(launcher.ensure(self.port, stop=True)['running'])
        deadline = time.monotonic()+5
        while alive(owner) and time.monotonic()<deadline: time.sleep(.05)
        self.assertFalse(alive(owner))
        restarted = launcher.ensure(self.port)
        after = launcher.status(restarted['local_url'], token)
        self.assertEqual(before['installation_id'], after['installation_id'])
        self.assertEqual(before['server_url'], after['server_url'])

    def test_unrelated_listener_is_preserved(self):
        with socket.socket() as listener, patch.object(launcher, 'status', side_effect=OSError('not our server')):
            listener.bind(('127.0.0.1', self.port)); listener.listen()
            with self.assertRaisesRegex(ValueError, 'occupied'):
                launcher.ensure(self.port)
            self.assertFalse(launcher.ensure(self.port, stop=True)['running'])
            with socket.socket() as probe:
                self.assertEqual(probe.connect_ex(('127.0.0.1', self.port)), 0)
        self.assertFalse((self.folder/'process-private.json').exists())


if __name__ == '__main__': unittest.main()
