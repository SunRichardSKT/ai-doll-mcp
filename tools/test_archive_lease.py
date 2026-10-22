"""Native firmware lease policy and real SQLite collector ownership boundaries.

The C++ test compiles the production policy header. The Python device is an
explicit protocol double; these checks do not claim physical-board acceptance.
"""
import json
import pathlib
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from companion import Companion
from test_offline_archive import batch, stored, event

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEASE = 'ab'*16


class NativeLeaseTests(unittest.TestCase):
    def test_production_policy_owner_cursor_expiry_and_restart(self):
        compiler = shutil.which('g++')
        self.assertIsNotNone(compiler, 'Native firmware policy check requires a C++ compiler')
        source = r'''
#include <assert.h>
#include <string.h>
#include "archive_lease.h"
int main(){
 ArchiveLeaseState s;
 const char *a="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", *b="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
 assert(!s.active(0));
 assert(s.acquire("bad owner","phone",a,1)==2);
 assert(s.acquire("phone-a","invalid",a,1)==2);
 assert(s.acquire("phone-a","phone","short",1)==2);
 assert(s.acquire("phone-a","phone",a,100)==0);
 assert(s.expires==90100 && !strcmp(s.id,a));
 assert(!s.record("",99,200) && !s.canAck(a,99,200));
 assert(s.record(a,24,200) && s.canAck(a,24,200));
 assert(!s.canAck(a,25,200) && !s.canAck(a,0,200));
 assert(s.acquire("phone-b","phone",b,200)==1);
 assert(s.acquire("phone-a","computer",b,200)==1);
 assert(s.acquire("phone-a","phone",b,30000)==0);
 assert(!strcmp(s.id,a) && s.delivered==24 && s.expires==120000);
 assert(!s.renew(b,30001) && !s.release(b,30001));
 assert(s.renew(a,40000) && s.expires==130000);
 assert(s.release(a,50000) && !s.active(50000));
 assert(s.release(a,50000));
 assert(s.acquire("phone-b","phone",b,60000)==0);
 assert(s.delivered==0 && !s.canAck(b,24,60000));
 assert(!s.record(a,100,60000) && !s.canAck(a,24,60000));
 assert(s.active(149999) && !s.active(150000));
 assert(!s.renew(b,150001));
 assert(s.acquire("computer-a","computer",a,150001)==0);
 ArchiveLeaseState restarted;
 assert(!restarted.active(0) && !restarted.canAck(a,1,0));
}
'''
        with tempfile.TemporaryDirectory(prefix='ai-doll-lease-') as folder:
            directory = pathlib.Path(folder)
            shutil.copyfile(ROOT/'firmware/src/archive_lease.h', directory/'archive_lease.h')
            (directory/'lease.cpp').write_text(source, encoding='utf-8')
            executable = directory/'lease.exe'
            built = subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                                    str(directory/'lease.cpp'), '-o', str(executable)],
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stderr)
            result = subprocess.run([str(executable)], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)


class LeaseDevice:
    def __init__(self, archive_path):
        self.archive_path = archive_path
        self.boot = 'current-boot'
        self.supported = True
        self.owner = None
        self.lease = None
        self.requests = []
        self.pending = [stored(1, event(1, 9000, touch='new-1'), self.boot)]
        self.drop_ack = False
        self.expired = False

    @staticmethod
    def rpc(data=None, error=None):
        if error:
            return {'jsonrpc': '2.0', 'id': 1, 'error': {'code': -32602, 'message': error}}
        return {'jsonrpc': '2.0', 'id': 1, 'result': {'isError': False,
                'content': [{'type': 'text', 'text': json.dumps(data)}]}}

    def exchange(self, command):
        self.requests.append(command)
        if command['cmd'] == 'status':
            return {'device_id': 'test-device', 'boot_id': self.boot,
                    'archive_lease_supported': self.supported}
        if command['cmd'] == 'rpc':
            name = command['request']['params']['name']
            args = command['request']['params']['arguments']
            if name == 'doll_get_status':
                return self.rpc({'device_id': 'test-device', 'boot_id': self.boot})
            if name == 'get_touch_events':
                return self.rpc(batch([], boot=self.boot))
            if name == 'acquire_archive_lease':
                if self.owner and self.owner != args['collector_id']:
                    return self.rpc(error='Archive occupied by another collector')
                self.owner, self.lease = args['collector_id'], LEASE
                self.expired = False
            elif name == 'renew_archive_lease':
                if self.expired or args['lease_id'] != self.lease:
                    self.owner, self.lease = None, None
                    return self.rpc(error='Archive lease expired')
            elif name == 'release_archive_lease':
                if args['lease_id'] != self.lease:
                    return self.rpc(error='Archive lease belongs to another collector')
                self.owner, self.lease = None, None
                return self.rpc({'released': True})
            return self.rpc({'lease_id': self.lease, 'boot_id': self.boot, 'expires_in_sec': 90})
        if command['cmd'] == 'events':
            if self.supported and command.get('archive_lease_id') != self.lease:
                raise AssertionError('Persistent read did not carry its lease')
            return batch(self.pending, boot=self.boot)
        if command['cmd'] == 'ack_events':
            if self.supported and command.get('archive_lease_id') != self.lease:
                raise AssertionError('ACK did not carry its lease')
            db = sqlite3.connect(self.archive_path)
            try:
                if db.execute('SELECT COUNT(*) FROM events').fetchone()[0] != 1:
                    raise AssertionError('ACK preceded a committed archive')
            finally:
                db.close()
            self.pending = []
            if self.drop_ack:
                self.drop_ack = False
                raise OSError('ACK accepted but its response was lost')
            return {'ok': True}
        return {'ok': True}

    def names(self):
        return [r['request']['params']['name'] for r in self.requests if r['cmd'] == 'rpc']


class CollectorLeaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.temp.name)/'archive.sqlite3'
        self.device = LeaseDevice(self.path)
        self.collector = Companion(self.path, self.device.exchange, threading.Lock())

    def tearDown(self):
        self.collector.db.close()
        self.temp.cleanup()

    def test_commit_then_ack_and_renew_only_after_30_seconds(self):
        self.collector.sync()
        self.assertEqual(self.device.names(), ['acquire_archive_lease'])
        self.collector.sync()
        self.assertEqual(self.device.names(), ['acquire_archive_lease'])
        with patch('companion.time.monotonic', return_value=self.collector.archive_lease_renew_at+1):
            self.collector.sync()
        self.assertEqual(self.device.names(), ['acquire_archive_lease', 'renew_archive_lease'])
        self.assertEqual(len(self.collector.device_history()['events']), 1)

    def test_explicit_stop_releases_lease(self):
        self.collector.sync()
        self.collector.stop.set()
        self.collector.collect()
        self.assertIsNone(self.device.owner)
        self.assertEqual(self.device.names()[-1], 'release_archive_lease')

    def test_same_installation_recovers_after_process_restart(self):
        self.collector.sync()
        owner = self.collector.archive_collector_id
        self.collector.db.close()
        self.collector = Companion(self.path, self.device.exchange, threading.Lock())
        self.collector.sync()
        self.assertEqual(self.collector.archive_collector_id, owner)
        self.assertEqual(self.device.names().count('acquire_archive_lease'), 2)

    def test_device_restart_acquires_new_boot_lease_without_reusing_old_ack(self):
        self.collector.sync()
        self.device.boot, self.device.owner, self.device.lease = 'next-boot', None, None
        self.collector.sync()
        self.assertEqual(self.collector.archive_lease_boot, 'next-boot')
        self.assertEqual(self.device.names().count('acquire_archive_lease'), 2)

    def test_expired_renewal_clears_local_credential_then_reacquires(self):
        self.collector.sync()
        self.device.expired = True
        with patch('companion.time.monotonic', return_value=self.collector.archive_lease_renew_at+1):
            with self.assertRaises(ValueError):
                self.collector.sync()
        self.assertIsNone(self.collector.archive_lease_id)
        self.collector.sync()
        self.assertEqual(self.device.names().count('acquire_archive_lease'), 2)

    def test_other_collector_cannot_consume_but_can_read_status(self):
        self.device.owner, self.device.lease = 'phone-installation', LEASE
        with self.assertRaises(ValueError):
            self.collector.sync()
        self.assertFalse(any(r['cmd'] == 'ack_events' for r in self.device.requests))
        self.assertEqual(len(self.device.pending), 1)
        self.assertEqual(self.collector.device('doll_get_status', {})['device_id'], 'test-device')

    def test_ack_response_loss_does_not_duplicate_committed_history(self):
        self.device.drop_ack = True
        with self.assertRaises(OSError):
            self.collector.sync()
        self.collector.sync()
        self.assertEqual(len(self.collector.device_history()['events']), 1)

    def test_failed_transaction_does_not_acknowledge(self):
        with patch.object(self.collector, 'ingest', side_effect=OSError('disk write failed')):
            with self.assertRaises(OSError):
                self.collector.sync()
        self.assertFalse(any(r['cmd'] == 'ack_events' for r in self.device.requests))
        self.assertEqual(len(self.device.pending), 1)

    def test_old_firmware_copies_without_ack_and_reads_live_ram_separately(self):
        self.device.supported = False
        self.collector.sync()
        self.assertEqual(self.device.names(), ['get_touch_events'])
        self.assertFalse(any(r['cmd'] == 'ack_events' for r in self.device.requests))
        self.assertEqual(self.collector.archive_metadata()['archive_mode'], 'legacy_copy_only')
        self.assertEqual(len(self.device.pending), 1)
        self.assertTrue(all('archive_lease_id' not in r for r in self.device.requests))


if __name__ == '__main__':
    unittest.main()
