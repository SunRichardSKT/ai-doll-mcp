"""A stalled device must not queue a late output or block archived history."""
import json
import pathlib
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from companion import Companion


class ContentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sent = []
        self.connection_lock = threading.Lock()
        self.c = Companion(pathlib.Path(self.tmp.name) / 'history.sqlite3',
                           self.exchange, self.connection_lock)

    def tearDown(self):
        self.c.db.close()
        self.tmp.cleanup()

    def exchange(self, command):
        self.sent.append(command)
        if command['cmd'] == 'events':
            return {'device_id': 'fixture', 'boot_id': 'boot', 'uptime_ms': 1000,
                    'next_cursor': 0, 'latest_seq': 0, 'oldest_seq': 1,
                    'gap': False, 'events': []}
        return {'result': {'content': [{'type': 'text', 'text': json.dumps(
            {'device_id': 'fixture', 'wifi_connected': True})}]}}

    def while_busy(self, lock, action):
        outcome = {}
        done = threading.Event()

        def run():
            try:
                outcome['result'] = action()
            except Exception as exc:
                outcome['error'] = exc
            finally:
                done.set()

        lock.acquire()
        worker = threading.Thread(target=run, daemon=True)
        started = time.monotonic()
        worker.start()
        try:
            returned_while_busy = done.wait(3)
            elapsed = time.monotonic() - started
            sent_while_busy = list(self.sent)
        finally:
            lock.release()
            worker.join(3)
        self.assertFalse(worker.is_alive(), 'Request thread did not finish')
        self.assertTrue(returned_while_busy, 'Request waits indefinitely behind the stalled connection')
        self.assertLess(elapsed, 3)
        self.assertEqual(sent_while_busy, [])
        return outcome

    def test_busy_output_is_not_delivered_after_waiting(self):
        result = self.while_busy(self.connection_lock, lambda: self.c.call(
            'set_vibration', {'channel': 10, 'intensity': 30}))
        self.assertIsInstance(result.get('error'), TimeoutError)
        self.assertEqual(self.sent, [], 'A timed-out motor command must never be sent later')

    def test_installation_returns_a_busy_diagnostic(self):
        result = self.while_busy(self.connection_lock, self.c.installation_status)
        self.assertNotIn('error', result)
        status = result['result']
        self.assertIsNone(status['device'])
        self.assertIn('busy', status['device_error'].lower())
        self.assertTrue(status['database_open'])
        self.assertEqual(self.sent, [])

    def test_archived_history_remains_available_during_sync_contention(self):
        self.c.ingest({'device_id': 'fixture', 'boot_id': 'boot', 'uptime_ms': 2000,
                      'next_cursor': 1, 'latest_seq': 1, 'oldest_seq': 1, 'gap': False,
                      'events': [{'seq': 1, 'phase': 'start', 'uptime_ms': 1000,
                                  'touch_id': 'one', 'channel': 0, 'body_part': 'head',
                                  'source': 'simulation', 'peak_raw': 1800, 'duration_ms': 0}]})
        result = self.while_busy(self.c.sync_lock, lambda: self.c.call('query_touch_history', {}))
        self.assertNotIn('error', result)
        self.assertEqual(len(result['result']['touches']), 1)
        self.assertIn('busy', result['result']['collector_error'].lower())

    def test_busy_start_does_not_create_a_session(self):
        result = self.while_busy(self.c.sync_lock, lambda: self.c.start('chat', 60))
        self.assertIsInstance(result.get('error'), TimeoutError)
        self.assertIsNone(self.c.active())
        self.assertEqual(self.sent, [])

    def test_busy_sync_does_not_prevent_ending_the_current_session(self):
        with self.c.db:
            now = time.time()
            self.c.db.execute("INSERT INTO sessions VALUES('session','chat',?,NULL,?,60,NULL)", (now, now))
        result = self.while_busy(self.c.sync_lock, lambda: self.c.end('session'))
        self.assertNotIn('error', result)
        self.assertEqual(result['result']['reason'], 'user')
        self.assertIsNone(self.c.active())
        self.assertEqual(self.sent, [])

    def test_connection_lock_released_after_an_exchange_error(self):
        def offline(_):
            raise OSError('fixture offline')
        self.c.exchange = offline
        with self.assertRaises(OSError):
            self.c.device('doll_get_status', {})
        self.assertTrue(self.connection_lock.acquire(blocking=False))
        self.connection_lock.release()
        self.c.exchange = self.exchange
        self.assertEqual(self.c.device('doll_get_status', {})['device_id'], 'fixture')

    @contextmanager
    def http_fixture(self):
        import device_setup_server as service
        with patch.multiple(service, COMPANION=self.c, COMPANION_TOKEN='fixture-token',
                            exchange=self.exchange, WORK=pathlib.Path(self.tmp.name)):
            server = ThreadingHTTPServer(('127.0.0.1', 0), service.Handler)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                yield service, 'http://127.0.0.1:' + str(server.server_port)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(3)

    @staticmethod
    def http_error(request):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=4) as response:
                return {'status': response.status, 'body': json.load(response)}
        except urllib.error.HTTPError as exc:
            with exc:
                return {'status': exc.code, 'body': json.load(exc)}

    def test_http_busy_output_returns_503_without_late_write(self):
        with self.http_fixture() as (_, base):
            request = urllib.request.Request(base + '/companion/tool', data=json.dumps({
                'name': 'set_vibration', 'arguments': {'channel': 10, 'intensity': 30}}).encode(),
                headers={'Host': '127.0.0.1:8768', 'Authorization': 'Bearer fixture-token',
                         'Content-Type': 'application/json'})
            result = self.while_busy(self.connection_lock, lambda: self.http_error(request))
        self.assertNotIn('error', result)
        self.assertEqual(result['result']['status'], 503)
        self.assertEqual(result['result']['body']['code'], 'device_busy')
        self.assertEqual(self.sent, [])

    def test_http_busy_status_returns_503(self):
        with self.http_fixture() as (service, base):
            request = urllib.request.Request(base + '/status', headers={
                'Host': '127.0.0.1:8768', 'X-CSRF-Token': service.CSRF})
            result = self.while_busy(self.connection_lock, lambda: self.http_error(request))
        self.assertNotIn('error', result)
        self.assertEqual(result['result']['status'], 503)
        self.assertEqual(result['result']['body']['code'], 'device_busy')
        self.assertEqual(self.sent, [])


if __name__ == '__main__':
    unittest.main()
