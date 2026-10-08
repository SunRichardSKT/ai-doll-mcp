"""Independent durable cursors, cross-boot time quality and commit-before-ACK."""
import datetime
import json
import pathlib
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from companion import Companion

EPOCH='ab'*16
NOW=1760000000.0


def event(seq=1,at=1000,phase='start',touch='old-1',clock=None):
    result=dict(seq=seq,uptime_ms=at,phase=phase,touch_id=touch,channel=0,
                body_part='头顶',source='simulation',peak_raw=2000,raw=0 if phase=='end' else 2000,
                duration_ms=1500 if phase=='end' else 0,sensor_type='pressure',direction='input',quality='ok')
    result.update(time_quality='device_clock' if clock is not None else 'unknown',device_time_ms=clock)
    return result


def batch(persistent=(),live=(),boot='new',uptime=10000,epoch=EPOCH,lost=0,corrupt=0,failures=0,more=False):
    persistent=list(persistent);live=list(live)
    return dict(device_id='test-device',boot_id=boot,uptime_ms=uptime,events=live,
                latest_seq=max([0]+[e['seq'] for e in live]),next_cursor=max([0]+[e['seq'] for e in live]),
                oldest_seq=1,gap=False,persistent_events=persistent,
                storage_cursor=persistent[-1]['storage_id'] if persistent else 0,storage_has_more=more,
                event_storage=dict(available=True,storage_epoch=epoch,lost_records=lost,corrupt_records=corrupt,
                    write_failures_since_boot=failures,clock_synced=True,device_time_ms=round(time.time()*1000)))


def stored(ident,record=None,boot='old'):
    return dict(storage_id=ident,boot_id=boot,event=record or event(seq=ident,touch='old-'+str(ident)))


class OfflineArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=pathlib.Path(self.tmp.name)/'archive.sqlite3'
        self.c=Companion(self.path,None,threading.Lock())

    def tearDown(self):
        self.c.db.close();self.tmp.cleanup()

    def test_old_unanchored_boot_keeps_unknown_time_and_no_session(self):
        with self.c.db:self.c.db.execute("INSERT INTO sessions VALUES('s','chat',?,NULL,?,60,NULL)",(NOW-1,NOW-1))
        self.c.ingest(batch([stored(1)]),NOW)
        raw=self.c.device_history()['events'][0]
        self.assertIsNone(raw['at']);self.assertEqual(raw['time_quality'],'unknown')
        self.assertIsNone(raw['session_id']);self.assertEqual(raw['delivery_quality'],'offline_replay')
        self.assertIsNone(self.c.history()['touches'][0]['started'])
        day=datetime.datetime.fromtimestamp(NOW,datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
        self.assertFalse(self.c.device_history(date=day)['events'])

    def test_known_old_boot_anchor_is_estimate_not_new_received_time(self):
        with self.c.db:self.c.db.execute('INSERT INTO boots VALUES(?,?,?,?)',('test-device','old',NOW-100,0))
        self.c.ingest(batch([stored(1,event(at=1000))]),NOW)
        row=self.c.device_history()['events'][0]
        self.assertEqual(row['at'],NOW-99)
        self.assertEqual(row['time_quality'],'estimated_from_boot_anchor')

    def test_valid_device_clock_survives_reboot_and_completed_duration(self):
        start=event(clock=round((NOW-30)*1000))
        end=event(2,2500,'end',clock=round((NOW-28.5)*1000))
        self.c.ingest(batch([stored(1,start),stored(2,end)]),NOW)
        touch=self.c.history()['touches'][0]
        self.assertEqual(touch['duration_ms'],1500)
        self.assertEqual(touch['started'],NOW-30)
        self.assertEqual(touch['ended'],NOW-28.5)
        self.assertTrue(all(e['time_quality']=='device_clock' for e in self.c.device_history()['events']))

    def test_later_ram_sequences_do_not_skip_earlier_persistent_pages(self):
        self.c.ingest(batch([stored(i,boot='new') for i in range(1,25)],
                       [event(100,touch='later')],more=True),NOW)
        self.c.ingest(batch([stored(i,boot='new') for i in range(25,49)]),NOW+1)
        sequences={r['seq'] for r in self.c.db.execute('SELECT seq FROM events')}
        self.assertEqual(sequences,set(range(1,49))|{100})

    def test_persistent_and_ram_duplicate_and_restart_deduplicate(self):
        item=event(1,9000,touch='new-1')
        incoming=batch([stored(1,item,'new')],[item])
        self.c.ingest(incoming,NOW)
        self.c.db.close();self.c=Companion(self.path,None,threading.Lock())
        self.c.ingest(incoming,NOW+1)
        self.assertEqual(len(self.c.device_history()['events']),1)
        self.assertEqual(len(self.c.history()['touches']),1)

    def test_accepted_cursor_prevents_resurrection_after_history_deletion(self):
        incoming=batch([stored(1)])
        self.c.ingest(incoming,NOW)
        with self.c.db:self.c.db.execute('DELETE FROM events');self.c.db.execute('DELETE FROM touches')
        self.c.ingest(incoming,NOW+1)
        self.assertFalse(self.c.device_history()['events'])

    def test_new_storage_epoch_can_restart_counter(self):
        self.c.ingest(batch([stored(1)]),NOW)
        self.c.ingest(batch([stored(1,event(touch='other'),boot='different')],epoch='cd'*16),NOW+1)
        self.assertEqual(len(self.c.device_history()['events']),2)
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM storage_cursors').fetchone()[0],2)

    def test_loss_notices_are_reported_once_and_failures_reset_per_boot(self):
        incoming=batch(lost=3,corrupt=1,failures=2)
        self.c.ingest(incoming,NOW);self.c.ingest(incoming,NOW+1)
        self.assertEqual(len(self.c.device_history()['notices']),3)
        self.c.ingest(batch(boot='next',lost=3,corrupt=1,failures=1),NOW+2)
        self.assertEqual(len(self.c.device_history()['notices']),4)

    def test_invalid_cursor_epoch_order_and_clock_roll_back(self):
        cases=[batch([stored(1)],epoch='invalid'),batch([stored(2),stored(1)]),
               batch([stored(True)]),batch([stored(1,event(clock=1))])]
        mismatch=batch([stored(1)]);mismatch['storage_cursor']=99;cases.append(mismatch)
        for incoming in cases:
            with self.subTest(incoming=incoming),self.assertRaises(ValueError):
                self.c.ingest(incoming,NOW)
            self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)
            self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM storage_cursors').fetchone()[0],0)

    def test_database_commit_precedes_ack_and_lost_ack_is_safe(self):
        calls=[];first=True
        incoming=batch([stored(1,event(1,9000,touch='new-1'),'new')])
        def exchange(command):
            nonlocal first
            calls.append(command['cmd'])
            if command['cmd']=='events':return incoming
            if command['cmd']=='ack_events':
                # Independent database connection proves the transaction is committed.
                import sqlite3
                other=sqlite3.connect(self.path)
                try:
                    self.assertEqual(other.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)
                finally:other.close()
                if first:first=False;raise OSError('ACK reply lost')
                return {'ok':True}
            return {'ok':True}
        self.c.exchange=exchange
        with self.assertRaises(OSError):self.c.sync()
        self.c.sync()
        self.assertEqual(calls.count('ack_events'),2)
        self.assertEqual(len(self.c.device_history()['events']),1)

    def test_failed_transaction_never_acknowledges(self):
        calls=[]
        def exchange(command):
            calls.append(command['cmd']);return batch([stored(1,event(at=9000),'new')])
        self.c.exchange=exchange
        with patch.object(self.c.bridge,'enqueue',side_effect=RuntimeError('archive failed')):
            with self.assertRaises(RuntimeError):self.c.sync()
        self.assertEqual(calls,['events'])
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)

    def test_recent_current_boot_can_notify_but_replayed_event_cannot(self):
        now=time.time()
        with self.c.db:self.c.db.execute("INSERT INTO sessions VALUES('s','chat',?,NULL,?,60,NULL)",(now-10,now-10))
        sub=self.c.bridge.subscribe('local-owner',target_id='chat',session_id='s',device_id='test-device',
                                  ttl_sec=60,policy=dict(merge_ms=0,cooldown_ms=0))
        with self.c.db:self.c.db.execute('UPDATE bridge_subscriptions SET created=? WHERE id=?',(now-1,sub['id']))
        recent=event(1,9500,touch='new-1',clock=round((now-.5)*1000))
        self.c.ingest(batch([stored(1,recent,'new')]),now)
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM bridge_outbox').fetchone()[0],1)
        older=event(2,4000,touch='new-2',clock=round((now-6)*1000))
        self.c.ingest(batch([stored(2,older,'new')]),now)
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM bridge_outbox').fetchone()[0],1)
        self.assertEqual(self.c.active()['last_activity'],recent['device_time_ms']/1000)

    def test_current_boot_selection_is_not_replaced_by_unknown_old_boot(self):
        self.c.ingest(batch([stored(1)]),NOW)
        seen=[]
        def exchange(command):
            seen.append(command);return batch()
        self.c.exchange=exchange;self.c.last_clock_sync=time.monotonic()
        self.c.sync()
        self.assertEqual(seen[0]['boot_id'],'new')

    def test_clock_resets_are_synchronized_even_inside_rate_limit(self):
        incoming=batch();incoming['event_storage']['clock_synced']=False
        calls=[]
        def exchange(command):
            calls.append(command['cmd'])
            return incoming if command['cmd']=='events' else {'ok':True}
        self.c.exchange=exchange;self.c.last_clock_sync=time.monotonic()
        self.c.sync()
        self.assertEqual(calls,['events','sync_time'])

    def test_user_can_end_interaction_while_device_is_offline(self):
        now=time.time()
        with self.c.db:self.c.db.execute("INSERT INTO sessions VALUES('s','chat',?,NULL,?,60,NULL)",(now,now))
        self.c.exchange=lambda command:(_ for _ in ()).throw(OSError('device offline'))
        ended=self.c.end('s')
        self.assertEqual(ended['reason'],'user');self.assertIsNotNone(ended['ended'])
        self.assertIsNone(self.c.active())

    def test_small_clock_lag_does_not_lose_first_post_boundary_event(self):
        now=time.time()
        with self.c.db:
            self.c.db.execute("INSERT INTO sessions VALUES('s','chat',?,NULL,?,60,NULL)",(now,now))
            self.c.db.execute("INSERT INTO session_boundaries VALUES('s','test-device','new',5)")
        new=event(6,9900,touch='new-6',clock=round((now-.02)*1000))
        self.c.ingest(batch([stored(6,new,'new')]),now+.1)
        raw=self.c.device_history()['events'][0]
        self.assertEqual(raw['session_id'],'s');self.assertEqual(raw['session_time_quality'],'sequence_boundary')
        self.assertEqual(raw['at'],new['device_time_ms']/1000)
        old=event(5,9800,touch='new-5',clock=round((now+.01)*1000))
        self.c.ingest(batch(live=[old]),now+.2)
        self.assertIsNone(self.c.device_history()['events'][1]['session_id'])

    def test_unknown_old_boot_and_large_clock_lag_cannot_use_sequence_fallback(self):
        now=time.time()
        with self.c.db:
            self.c.db.execute("INSERT INTO sessions VALUES('s','chat',?,NULL,?,60,NULL)",(now,now))
            self.c.db.execute("INSERT INTO session_boundaries VALUES('s','test-device','new',0)")
        for ident,boot,clock in [(1,'old',None),(2,'new',round((now-3)*1000))]:
            self.c.ingest(batch([stored(ident,event(ident,9900,touch=boot+'-'+str(ident),clock=clock),boot)]),now+.1)
        self.assertTrue(all(e['session_id'] is None for e in self.c.device_history()['events']))

    def test_failed_flash_fallback_cannot_notify_delayed_ram_events(self):
        now=time.time()
        with self.c.db:self.c.db.execute("INSERT INTO sessions VALUES('s','chat',?,NULL,?,60,NULL)",(now-20,now-20))
        sub=self.c.bridge.subscribe('local-owner',target_id='chat',session_id='s',device_id='test-device',ttl_sec=60,
                                   policy=dict(merge_ms=0,cooldown_ms=0))
        with self.c.db:self.c.db.execute('UPDATE bridge_subscriptions SET created=? WHERE id=?',(now-20,sub['id']))
        incoming=batch(live=[event(1,4000,touch='new-1',clock=round((now-6)*1000))])
        incoming['event_storage']['available']=False
        self.c.ingest(incoming,now)
        self.assertEqual(self.c.device_history()['events'][0]['delivery_quality'],'offline_replay')
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM bridge_outbox').fetchone()[0],0)
        self.assertEqual(self.c.active()['last_activity'],now-20)


if __name__=='__main__':unittest.main()
