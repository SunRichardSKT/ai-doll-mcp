"""Destructive history operations only touch disposable archives."""
import csv
import datetime as dt
import io
import json
import pathlib
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from companion import Companion
from history_management import validate_filters

NOW=dt.datetime(2026,10,9,12,tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp()


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.tmp.name)/'archive.sqlite3'
        self.c=Companion(self.path,None,threading.Lock());self.h=self.c.history_manager;self.seq=0
    def tearDown(self):self.c.db.close();self.tmp.cleanup()
    def add(self,at=NOW,kind='pressure',phase='start',touch=None,body='头',session=None,received=NOW,device='d',boot='b',value=2000):
        self.seq+=1
        e=dict(seq=self.seq,uptime_ms=self.seq*100,phase=phase,channel=0,body_part=body,source='simulation',
               sensor_type=kind,direction='output' if kind=='vibration' else 'input',value=value,unit='adc_raw',peak_raw=2000,
               duration_ms=1000,time_quality='unknown' if at is None else 'device_clock',received_at=received)
        if kind=='pressure':e['touch_id']=touch or boot+'-'+str(self.seq)
        with self.c.lock,self.c.db:
            self.c.archive_event(device,boot,e,at,received)
            if session:self.c.db.execute('UPDATE events SET session_id=? WHERE seq=?',(session,self.seq))
        return self.seq
    def erase(self,filters=None,all_records=False):
        p=self.h.preview_delete(filters,all_records);return self.h.delete(p['preview_token'],True)
    def count(self,table='events'):return self.c.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
    def ended_session(self):
        with self.c.db:self.c.db.execute("INSERT INTO sessions VALUES('s','chat',?, ?, ?,300,'user')",(NOW-10,NOW+10,NOW))

    def test_export_boundaries_unknown_and_fixed_upper_id(self):
        start=dt.datetime(2026,10,9,tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp()
        for at in [start-1,start,start+86399,start+86400,None]:self.add(at,kind='temperature')
        f=dict(start_date='2026-10-09',end_date='2026-10-09',time_scope='known')
        one=self.h.export(f,limit=1);self.assertEqual(one['records'][0]['seq'],2);self.assertTrue(one['has_more'])
        self.add(start+10,kind='temperature')
        two=self.h.export(f,after=one['next_cursor'],max_id=one['max_id'])
        self.assertEqual([e['seq'] for e in two['records']],[3])
        alltime=self.h.export(dict(f,time_scope='all'));self.assertEqual(alltime['count'],4)
        self.assertIsNone(next(e for e in alltime['records'] if e['seq']==5)['at'])
    def test_csv_quotes_unicode_and_formula_injection(self):
        label=' \t=HYPERLINK("bad")\n你好';self.add(kind='temperature',body=label,value=-2.5)
        row=list(csv.DictReader(io.StringIO(self.h.export(format='csv')['content'])))[0]
        self.assertEqual(row['body_part'],"'"+label);self.assertEqual(row['value'],'-2.5')
        self.assertEqual(json.loads(row['payload_json'])['body_part'],label)
    def test_export_never_includes_persona_or_pairing_settings(self):
        self.c.set_setting('persona','private-persona');self.c.set_setting('token','private-token');self.add()
        text=json.dumps(self.h.export());self.assertNotIn('private-persona',text);self.assertNotIn('private-token',text)
    def test_invalid_filters_and_limits(self):
        for f in [[],{'what':'bad'},{'start_date':'2026-02-30'},{'start_date':'2026-10-10','end_date':'2026-10-09'},
                  {'time_scope':'unknown','start_date':'2026-10-09'},{'direction':'bad'},{'sensor_type':"bad'"},{'device':5}]:
            with self.subTest(f=f),self.assertRaises((ValueError,TypeError)):validate_filters(f)
        for args in [dict(after=True),dict(limit=501),dict(max_id=True),dict(format='xlsx'),dict(max_id=2**64)]:
            with self.assertRaises(ValueError):self.h.export(**args)
    def test_all_history_requires_scope_and_confirmation(self):
        self.add()
        with self.assertRaises(ValueError):self.h.preview_delete()
        p=self.h.preview_delete(all_records=True)
        with self.assertRaises(ValueError):self.h.delete(p['preview_token'])
        self.assertEqual(self.count(),1)
        self.assertTrue(self.h.delete(p['preview_token'],True)['deleted']);self.assertEqual(self.count(),0)
        with self.assertRaises(ValueError):self.h.delete(p['preview_token'],True)
    def test_expired_preview_does_not_delete(self):
        self.add();p=self.h.preview_delete(all_records=True)
        with patch('history_management.time.time',return_value=p['expires_at']+1),self.assertRaises(ValueError):self.h.delete(p['preview_token'],True)
        self.assertEqual(self.count(),1)
    def test_new_unrelated_events_survive_preview_confirmation(self):
        self.add(kind='temperature');p=self.h.preview_delete(all_records=True);self.add(kind='temperature')
        self.h.delete(p['preview_token'],True);self.assertEqual(self.count(),1)
    def test_pressure_closure_crosses_dates_and_snapshot_upper_bound(self):
        self.add(NOW-86400,touch='t',body='旧名');p=self.h.preview_delete({'body_part':'旧名'})
        self.add(NOW,touch='t',phase='end',body='新名')
        with self.assertRaises(ValueError):self.h.delete(p['preview_token'],True)
        p=self.h.preview_delete({'body_part':'旧名'});self.assertEqual(p['counts']['expanded_events'],1)
        self.h.delete(p['preview_token'],True);self.assertEqual(self.count(),0);self.assertEqual(self.count('touches'),0)
    def test_modified_payload_invalidates_preview(self):
        self.add();p=self.h.preview_delete(all_records=True)
        with self.c.db:self.c.db.execute("UPDATE events SET payload=json_set(payload,'$.body_part','changed')")
        with self.assertRaises(ValueError):self.h.delete(p['preview_token'],True)
        self.assertEqual(self.count(),1)
    def test_active_session_protected(self):
        with self.c.db:self.c.db.execute("INSERT INTO sessions VALUES('s','chat',?,NULL,?,300,NULL)",(NOW-1,NOW))
        self.add(session='s')
        with self.assertRaises(ValueError):self.h.preview_delete(all_records=True)
        self.assertEqual(self.count(),1)
    def test_delete_derived_deliveries_replies_empty_session_and_preserve_preferences(self):
        self.ended_session();self.add(session='s');self.c.set_setting('persona','keep')
        with self.c.db:
            self.c.db.execute("INSERT INTO bridge_subscriptions(id,owner,target_id,session_id,device_id,transport,created,expires,active,policy,feedback) VALUES('sub','owner','chat','s','d','stream',?,?,0,'{}','{}')",(NOW,NOW+30))
            self.c.db.execute("INSERT INTO bridge_outbox(event_id,subscription_id,payload,created,ready,expires,state) VALUES('e','sub','secret-derived',?,?,?,'delivered')",(NOW,NOW,NOW+30))
            self.c.db.execute("INSERT INTO bridge_replies(event_id,subscription_id,text,source,created) VALUES('e','sub','private reply','model',?)",(NOW,))
        p=self.h.preview_delete(all_records=True);self.assertEqual(p['counts']['related_replies'],1)
        self.h.delete(p['preview_token'],True)
        for t in ['events','touches','bridge_outbox','bridge_replies','sessions','bridge_subscriptions']:self.assertEqual(self.count(t),0,t)
        self.assertEqual(self.c.setting('persona'),'keep')
    def test_deletion_rollback_includes_tombstones_and_touches(self):
        self.add();p=self.h.preview_delete(all_records=True)
        self.c.db.execute("CREATE TRIGGER fail_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'forced failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.h.delete(p['preview_token'],True)
        self.assertEqual(self.count(),1);self.assertEqual(self.count('touches'),1);self.assertEqual(self.count('deleted_events'),0)
    def test_ram_or_flash_replay_and_late_release_do_not_resurrect(self):
        seq=self.add(touch='t');record=json.loads(self.c.db.execute('SELECT payload FROM events').fetchone()[0])
        self.erase(all_records=True)
        with self.c.db:self.c.archive_event('d','b',record,NOW,NOW+1)
        self.add(NOW+2,touch='t',phase='end')
        self.assertEqual(self.count(),0);self.assertEqual(self.count('touches'),0)
        self.add(NOW+3,touch='new');self.assertEqual(self.count(),1)
    def test_dedup_identifiers_survive_service_restart(self):
        self.add(touch='t');self.erase(all_records=True);self.c.db.close()
        self.c=Companion(self.path,None,threading.Lock());self.h=self.c.history_manager
        self.add(touch='t',phase='end');self.assertEqual(self.count(),0)
    def test_retention_default_disabled_and_enabling_requires_confirmation(self):
        self.add(NOW-100*86400);self.h.maintain(NOW);self.assertEqual(self.count(),1)
        with self.assertRaises(ValueError):self.h.set_retention(True,90)
        for days in [True,0,3651]:
            with self.assertRaises(ValueError):self.h.set_retention(False,days)
    def test_retention_cutoff_unknown_receipt_and_recent_pressure_phase(self):
        self.add(NOW-91*86400,touch='t');self.add(NOW-1,touch='t',phase='end')
        self.add(NOW-91*86400,kind='temperature');self.add(NOW-90*86400,kind='temperature')
        self.add(None,kind='temperature',received=NOW-91*86400);self.add(None,kind='temperature',received=NOW)
        self.h.set_retention(True,90,False,True);self.h.maintain(NOW)
        self.assertEqual(self.count(),5)
        self.h.set_retention(True,90,True,True);self.h.maintain(NOW)
        self.assertEqual(self.count(),4);self.assertEqual(self.count('touches'),1)
    def test_retention_never_deletes_active_session_and_runs_hourly(self):
        with self.c.db:self.c.db.execute("INSERT INTO sessions VALUES('s','chat',?,NULL,?,300,NULL)",(NOW-1,NOW))
        self.add(NOW-100*86400,kind='temperature',session='s');self.add(NOW-100*86400,kind='temperature')
        self.h.set_retention(True,90,False,True);self.h.maintain(NOW);self.assertEqual(self.count(),1)
        self.add(NOW-100*86400,kind='temperature');self.h.maintain(NOW+1);self.assertEqual(self.count(),2)
        self.h.maintain(NOW+3601);self.assertEqual(self.count(),1)
    def test_retention_preview_read_only_and_no_unknown_without_receipt(self):
        self.add(None,kind='temperature')
        with self.c.db:self.c.db.execute("UPDATE events SET payload=json_remove(payload,'$.received_at')")
        with patch('history_management.time.time',return_value=NOW):p=self.h.preview_retention(1,True)
        self.assertEqual(p['counts']['events'],0);self.assertEqual(self.count(),1)
    def test_statistics_full_scope_and_pressure_start_based_duration(self):
        self.add(touch='t');self.add(NOW+1,touch='t',phase='end');self.add(kind='temperature');self.add(kind='vibration',phase='output');self.add(None,kind='temperature')
        s=self.h.statistics();self.assertEqual(s['events'],5);self.assertEqual(s['pressure_starts'],1)
        self.assertEqual(s['completed'],1);self.assertEqual(s['duration_ms'],1000);self.assertEqual(s['unknown_time_events'],1)
        self.assertEqual(sum(x['events'] for x in s['daily']),4)
        s=self.h.statistics({'sensor_type':'temperature','time_scope':'known'});self.assertEqual(s['events'],1);self.assertEqual(s['pressure_starts'],0)
    def test_literal_sql_filter_does_not_expand_scope(self):
        self.add(body="' OR 1=1 --");self.add(body='other')
        self.assertEqual(self.h.export({'body_part':"' OR 1=1 --"})['count'],1)
    def test_preview_does_not_leave_open_transaction(self):
        self.add();self.h.preview_delete(all_records=True);self.assertFalse(self.c.db.in_transaction)

    def test_unknown_completed_pressure_counts_duration_without_fabricating_date(self):
        self.add(None,touch='t');self.add(None,touch='t',phase='end')
        s=self.h.statistics({'time_scope':'unknown'})
        self.assertEqual(s['completed'],1);self.assertEqual(s['duration_ms'],1000);self.assertEqual(s['daily'],[])
        self.assertIsNone(self.c.db.execute('SELECT ended FROM touches').fetchone()[0])

    def test_same_touch_id_on_another_device_is_not_deleted(self):
        self.add(touch='same',device='one');self.add(touch='same',device='two')
        self.erase({'device':'one'})
        self.assertEqual(self.count(),1);self.assertEqual(self.c.db.execute('SELECT device FROM events').fetchone()[0],'two')


if __name__=='__main__':unittest.main()
