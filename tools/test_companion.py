"""Deterministic tests for archive/session boundaries, recovery and overflow."""
import tempfile
import pathlib
import threading
import unittest
import sqlite3
from companion import Companion


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.tmp.name)/'test.sqlite3'
        self.c = Companion(self.path, None, threading.Lock())

    def tearDown(self):
        self.c.db.close()
        self.tmp.cleanup()

    def batch(self, seq=1, phase='start', at=1000, boot='one', body='头顶', touch='one-1'):
        return {'device_id': 'test', 'boot_id': boot, 'uptime_ms': 10000,
                'next_cursor': seq, 'latest_seq': seq, 'oldest_seq': 1, 'gap': False,
                'events': [{'seq': seq, 'phase': phase, 'uptime_ms': at, 'touch_id': touch,
                            'channel': 0, 'body_part': body, 'source': 'simulation',
                            'peak_raw': 2000, 'duration_ms': 1000}]}

    def test_dedup_duration_label_and_restart(self):
        b = self.batch()
        self.c.ingest(b, received=100)
        self.c.ingest(b, received=101)
        self.c.ingest(self.batch(2, 'end', 2000, body='改名'), received=101)
        rows = self.c.history()['touches']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['body_part'], '头顶')
        self.assertEqual(rows[0]['duration_ms'], 1000)
        self.c.db.close(); self.c = Companion(self.path, None, threading.Lock())
        self.assertEqual(len(self.c.history()['touches']), 1)

    def test_session_occurrence_boundary_and_timeout(self):
        with self.c.db:
            self.c.db.execute("INSERT INTO sessions VALUES('s','chat',95,NULL,95,30,NULL)")
        self.c.ingest(self.batch(at=1000), received=100)  # occurs at 91, old buffered touch
        self.c.ingest(self.batch(2, at=6000, touch='one-2'), received=101)  # occurs at 96
        self.assertEqual(len(self.c.history(session_id='s')['touches']), 1)
        self.c.expire(127)
        self.c.ingest(self.batch(3, at=38000, touch='one-3'), received=128)
        self.assertEqual(len(self.c.history(session_id='s')['touches']), 1)

    def test_reboot_new_sequences_and_gap(self):
        self.c.ingest(self.batch(), received=100)
        self.c.ingest(self.batch(boot='two', touch='two-1'), received=200)
        gap = self.batch(150, boot='two', touch='two-150')
        gap.update(gap=True, oldest_seq=23)
        self.c.ingest(gap, received=201)
        self.assertEqual(len(self.c.history()['touches']), 3)
        self.assertTrue(self.c.history()['notices'])

    def test_validation_and_date_filter(self):
        self.c.ingest(self.batch(), received=100)
        self.assertEqual(len(self.c.history(date='1970-01-01')['touches']), 1)
        self.assertEqual(len(self.c.history(date='1970-01-02')['touches']), 0)
        with self.assertRaises(ValueError):
            self.c.history(limit=0)
        with self.assertRaises(ValueError):
            self.c.history(date='invalid')

    def test_mixed_types_faults_cursors_and_output_not_touch(self):
        b=self.batch();self.c.ingest(b,received=100)
        def typed(seq,kind,value,phase='sample',direction='input'):
            batch=self.batch(seq,phase,at=seq*1000)
            batch['events'][0].update(sensor_type=kind,direction=direction,value=value,
                                     unit='degC' if kind=='temperature' else 'percent',quality='ok' if value is not None else 'adc_out_of_range')
            batch['events'][0].pop('touch_id')
            return batch
        self.c.ingest(typed(2,'temperature',32.5),received=101)
        self.c.ingest(typed(3,'vibration',60,'output','output'),received=102)
        self.c.ingest(typed(4,'temperature',None),received=103)
        self.assertEqual(len(self.c.history()['touches']),1)
        records=self.c.device_history()['events'];self.assertEqual(len(records),4)
        self.assertEqual(records[0]['sensor_type'],'pressure')
        self.assertIsNone(records[-1]['value'])
        self.assertEqual(len(self.c.device_history(sensor_type='temperature')['events']),2)
        self.assertEqual(len(self.c.device_history(direction='output')['events']),1)
        first=self.c.device_history(limit=2);self.assertTrue(first['has_more'])
        second=self.c.device_history(after=first['next_cursor']);self.assertEqual(len(second['events']),2)
        self.c.ingest(typed(3,'vibration',60,'output','output'),received=104)
        self.assertEqual(len(self.c.device_history()['events']),4)
        with self.assertRaises(ValueError):self.c.device_history(sensor_type='unknown type')

    def test_mixed_session_ownership_release_and_idle(self):
        with self.c.db:self.c.db.execute("INSERT INTO sessions VALUES('s','chat',95,98,96,30,'user')")
        self.c.ingest(self.batch(at=6000),received=100) # occurs at 96
        end=self.batch(2,'end',10000);self.c.ingest(end,received=101) # occurs at 100 after session ended
        self.assertEqual(len(self.c.device_history(session_id='s')['events']),2)
        temp=self.batch(3,'sample',11000);temp['events'][0].update(sensor_type='temperature',value=25,unit='degC')
        self.c.ingest(temp,received=102)
        self.assertEqual(len(self.c.device_history(session_id='s')['events']),2)
        with self.c.db:self.c.db.execute("INSERT INTO sessions VALUES('t','chat',105,NULL,105,30,NULL)")
        temp=self.batch(4,'sample',20000);temp['events'][0].update(sensor_type='temperature',value=26,unit='degC')
        self.c.ingest(temp,received=110)
        self.assertEqual(len(self.c.device_history(session_id='t')['events']),1)
        self.assertEqual(self.c.db.execute("SELECT last_activity FROM sessions WHERE id='t'").fetchone()[0],105)

    def test_existing_database_migration_keeps_rows_and_session(self):
        old=pathlib.Path(self.tmp.name)/'legacy.sqlite3'
        db=sqlite3.connect(old)
        db.executescript('''CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,
          device TEXT,boot TEXT,seq INTEGER,at REAL,payload TEXT,UNIQUE(device,boot,seq));
          CREATE TABLE touches(id INTEGER PRIMARY KEY AUTOINCREMENT,device TEXT,touch_id TEXT,
          channel INTEGER,body_part TEXT,source TEXT,started REAL,ended REAL,duration_ms INTEGER,
          peak_raw INTEGER,session_id TEXT,UNIQUE(device,touch_id));''')
        import json
        db.execute('INSERT INTO events(device,boot,seq,at,payload) VALUES(?,?,?,?,?)',
                   ('legacy','boot',1,100,json.dumps(dict(touch_id='old',body_part='old label',phase='start'))))
        db.execute('INSERT INTO touches(device,touch_id,session_id) VALUES(?,?,?)',('legacy','old','old-session'))
        db.commit();db.close()
        migrated=Companion(old,None,threading.Lock())
        try:
            self.assertEqual(len(migrated.history()['touches']),1)
            self.assertEqual(len(migrated.device_history(session_id='old-session')['events']),1)
            self.assertEqual(migrated.device_history()['events'][0]['body_part'],'old label')
        finally:migrated.db.close()


if __name__ == '__main__':
    unittest.main()
