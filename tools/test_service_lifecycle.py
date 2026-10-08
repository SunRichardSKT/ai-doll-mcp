"""Real child-process lease, exclusive socket and opt-in startup checks."""
import os
import io
import logging
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from http.server import BaseHTTPRequestHandler
from unittest.mock import patch

from service_lifecycle import ExclusiveLoopbackServer, ServiceLease, ServiceAlreadyRunning
from configure_startup import configure, startup_command, NAME, KEY
from run_background import LogStream


class LifecycleTests(unittest.TestCase):
    def test_background_log_does_not_recurse_through_stderr(self):
        captured = io.StringIO()
        logger = logging.getLogger('ai-doll-background')
        original_handlers, original_propagate, original_level = logger.handlers[:], logger.propagate, logger.level
        handler = logging.StreamHandler(captured)
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)
        stream = LogStream(logger)
        root = logging.getLogger()
        root_handler = logging.StreamHandler(stream)
        root.addHandler(root_handler)
        try:
            logger.info('direct message')
            root.warning('MCP library message')
            stream.flush()
            self.assertEqual(captured.getvalue().count('direct message'), 1)
            self.assertEqual(captured.getvalue().count('MCP library message'), 1)
            stream.write('partial')
            stream.flush()
            self.assertIn('partial', captured.getvalue())
        finally:
            root.removeHandler(root_handler)
            logger.handlers, logger.propagate, logger.level = original_handlers, original_propagate, original_level

    def test_stale_lock_file_is_not_a_running_service(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder)/'lease'
            path.write_text('old pid 123')
            with ServiceLease(path):
                with self.assertRaises(ServiceAlreadyRunning):
                    with ServiceLease(path):
                        pass
            with ServiceLease(path):
                pass

    def test_os_releases_lease_after_process_termination(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder)/'lease'
            ready = pathlib.Path(folder)/'ready'
            code = ('from service_lifecycle import ServiceLease;import pathlib,time,sys;'
                    'lease=ServiceLease(sys.argv[1]);lease.__enter__();'
                    "pathlib.Path(sys.argv[2]).write_text('ready');time.sleep(30)")
            child = subprocess.Popen([sys.executable, '-c', code, str(path), str(ready)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            try:
                deadline = time.monotonic() + 5
                while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertTrue(ready.exists())
                with self.assertRaises(ServiceAlreadyRunning):
                    with ServiceLease(path):
                        pass
            finally:
                child.terminate()
                child.communicate(timeout=5)
            with ServiceLease(path):
                pass

    def test_listener_is_exclusive(self):
        server = ExclusiveLoopbackServer(('127.0.0.1', 0), BaseHTTPRequestHandler)
        try:
            with self.assertRaises(OSError):
                ExclusiveLoopbackServer(('127.0.0.1', server.server_port), BaseHTTPRequestHandler)
        finally:
            server.server_close()

    @unittest.skipUnless(os.name == 'nt', 'Windows startup')
    def test_startup_dry_run_does_not_edit_registry(self):
        import winreg
        with patch.object(winreg, 'CreateKeyEx', side_effect=AssertionError('dry run wrote registry')):
            before = configure('status')
            preview = configure('install', dry_run=True)
            after = configure('status')
        self.assertEqual(before, after)
        self.assertEqual(preview['enabled'], before['enabled'])
        self.assertIn('pythonw.exe', preview['command'])
        self.assertIn('run_background.py', preview['command'])

    def test_startup_command_quotes_paths_and_rejects_missing_runtime(self):
        with tempfile.TemporaryDirectory(prefix='AI Doll startup ') as folder:
            root = pathlib.Path(folder)
            (root/'tools').mkdir()
            (root/'tools/run_background.py').write_text('pass')
            (root/'pythonw.exe').write_text('fixture')
            command = startup_command(root/'python.exe', root)
            self.assertEqual(command, subprocess.list2cmdline([
                str((root/'pythonw.exe').resolve()), str((root/'tools/run_background.py').resolve())]))
            self.assertTrue(command.startswith('"'))
            with self.assertRaises(ValueError):
                startup_command(root/'missing/python.exe', root)


if __name__ == '__main__':
    unittest.main()
