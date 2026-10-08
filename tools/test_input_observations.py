"""Factual pressure patterns, live quiet-hour suppression and safe installation checks."""
import datetime as dt
import json
import pathlib
import tempfile
import threading
import unittest
from unittest.mock import patch
from companion import Companion
from input_observations import pressure_observations
from interaction_bridge import validated_policy, validated_feedback, quiet_status


def event(ident, phase, at, touch='a', channel=0, **extra):
    return dict(id=ident, phase=phase, at=at, touch_id=touch, channel=channel,
                device='doll', boot='boot', body_part='头', source='simulation',
                sensor_type='pressure', direction='input', quality='ok', **extra)


class ObservationTests(unittest.TestCase):
    def summarize(self, events, focus=None):
        return pressure_observations(events, validated_policy({}), focus)['observations']

    def test_repeated_taps_and_duration_are_based_on_releases(self):
        values=[event(1,'start',0),event(2,'end',.2,duration_ms=200),
                event(3,'start',.4,touch='b'),event(4,'end',.6,touch='b',duration_ms=200)]
        pattern=self.summarize(values)[0]
        self.assertEqual(pattern['kind'],'repeated_short_presses');self.assertEqual(pattern['count'],2)
        self.assertEqual(pattern['event_ids'],[1,2,3,4])
        self.assertEqual(pattern['observation_id'],self.summarize(values)[0]['observation_id'])
        self.assertEqual(self.summarize(values,{99}),[])

    def test_open_start_is_unknown_not_an_inferred_hold(self):
        self.assertEqual(self.summarize([event(1,'start',0)]),[])
        pattern=self.summarize([event(2,'end',10,duration_ms=1900)])[0]
        self.assertEqual(pattern['kind'],'completed_long_press');self.assertFalse(pattern['start_in_scope'])
        self.assertEqual(self.summarize([event(2,'end',10,duration_ms=True)]),[])

    def test_source_boot_and_device_boundaries_do_not_merge(self):
        values=[event(1,'start',0),event(2,'end',.1,duration_ms=100),
                event(3,'start',.2,touch='b'),event(4,'end',.3,touch='b',duration_ms=100)]
        for field,replacement in [('source','sensor'),('boot','new-boot'),('device','other')]:
            mixed=[dict(e) for e in values]
            for e in mixed[2:]:e[field]=replacement
            self.assertEqual(self.summarize(mixed),[])

    def test_gap_unknown_intervening_touch_and_invalid_samples(self):
        values=[event(1,'start',0),event(2,'end',.1,duration_ms=100),
                event(3,'start',.4,touch='b'),event(4,'end',.5,touch='b',duration_ms=100)]
        for field,replacement in [('direction','output'),('quality','stale'),('sensor_type','temperature')]:
            changed=[dict(e,**{field:replacement}) for e in values]
            self.assertEqual(self.summarize(changed),[])
        self.assertEqual(self.summarize(values+[event(5,'start',.3,touch='unknown')]),[])
        far=[dict(e,at=e['at']+2 if e['id']>2 else e['at']) for e in values]
        self.assertEqual(self.summarize(far),[])

    def test_multi_point_is_nearby_starts_not_a_claimed_hug(self):
        pattern=self.summarize([event(1,'start',0),event(2,'start',.2,channel=1)])[0]
        self.assertEqual(pattern['kind'],'near_simultaneous_press_starts')
        self.assertEqual(pattern['channels'],[0,1]);self.assertFalse(pattern['sustained_overlap_confirmed'])
        self.assertEqual(self.summarize([event(1,'start',0),event(2,'start',.4,channel=1)]),[])

    def test_millisecond_boundaries_at_epoch_timestamp(self):
        base=1791518400.123
        taps=[event(1,'start',base),event(2,'end',base+.6,duration_ms=600),
              event(3,'start',base+1.2,touch='b'),event(4,'end',base+1.8,touch='b',duration_ms=600)]
        self.assertEqual(self.summarize(taps)[0]['count'],2)
        nearby=self.summarize([event(1,'start',base),event(2,'start',base+.3,channel=1)])
        self.assertEqual(nearby[0]['span_ms'],300)

    def test_nearby_sliding_windows_and_dense_cluster_deduplication(self):
        values=[event(1,'start',0),event(2,'start',.25,channel=1),event(3,'start',.5,channel=2)]
        self.assertEqual([o['event_ids'] for o in self.summarize(values)],[[1,2],[2,3]])
        self.assertEqual(self.summarize(values,{3})[0]['event_ids'],[2,3])
        values[-1]['at']=.3
        self.assertEqual([o['event_ids'] for o in self.summarize(values)],[[1,2,3]])


class QuietTests(unittest.TestCase):
    def test_cross_midnight_exact_boundaries_and_all_day(self):
        policy=validated_policy(dict(quiet_hours=dict(enabled=True)))
        def active(local):
            stamp=dt.datetime.fromisoformat('2026-10-09T'+local+'+08:00').timestamp()
            return quiet_status(policy,stamp)['active']
        self.assertFalse(active('22:59:59'));self.assertTrue(active('23:00:00'))
        self.assertTrue(active('06:59:59'));self.assertFalse(active('07:00:00'))
        policy=validated_policy(dict(quiet_hours=dict(enabled=True,start='00:00',end='00:00')))
        self.assertTrue(quiet_status(policy,0)['active'])

    def test_timezone_and_repeated_dst_hour(self):
        policy=validated_policy(dict(quiet_hours=dict(enabled=True,timezone='America/New_York')))
        for stamp in ['2026-11-01T05:30:00+00:00','2026-11-01T06:30:00+00:00']:
            self.assertTrue(quiet_status(policy,dt.datetime.fromisoformat(stamp).timestamp())['active'])
        same=dt.datetime.fromisoformat('2026-10-09T15:00:00+00:00').timestamp()
        self.assertTrue(quiet_status(validated_policy(dict(quiet_hours=dict(enabled=True))),same)['active'])
        self.assertFalse(quiet_status(policy,same)['active'])

    def test_invalid_policy_and_feedback(self):
        for value in [dict(quiet_hours={'enabled':1}),dict(quiet_hours={'start':'24:00'}),
                      dict(quiet_hours={'timezone':'Unknown/Nowhere'}),dict(quiet_hours={'unknown':True}),
                      dict(long_press_ms=500,tap_max_ms=600),dict(tap_gap_ms=False),dict(notify_pressure_patterns=1)]:
            with self.assertRaises(ValueError):validated_policy(value)
        for value in [dict(avoid_phrases=['']),dict(avoid_phrases='bad'),dict(preferred_address=1)]:
            with self.assertRaises(ValueError):validated_feedback(value)
        self.assertEqual(validated_feedback({})['preferred_address'],'')


class ObservationBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.temp.name)/'archive.db'
        self.c=Companion(self.path,None,threading.Lock());self.c.sync=lambda:None
        self.now=dt.datetime.fromisoformat('2026-10-09T12:00:00+08:00').timestamp();self.seq=0
        with self.c.db:self.c.db.execute("INSERT INTO sessions VALUES('s','chat',?,NULL,?,300,NULL)",(self.now-.1,self.now))

    def tearDown(self):self.c.db.close();self.temp.cleanup()

    def sub(self,**kwargs):
        return self.c.bridge.subscribe('local-owner','chat','s','doll',now=self.now,**kwargs)

    def ingest(self,when,phase='start',touch='a',channel=0,duration_ms=0,quality='ok',source='simulation'):
        self.seq+=1;uptime=1000+round(when*1000)
        value=dict(seq=self.seq,phase=phase,uptime_ms=uptime,touch_id=touch,channel=channel,
                   body_part='头' if channel==0 else '私密通道名',source=source,sensor_type='pressure',
                   direction='input',unit='adc_raw',quality=quality,peak_raw=2000,value=2000,duration_ms=duration_ms)
        batch=dict(device_id='doll',boot_id='boot',uptime_ms=uptime,next_cursor=self.seq,latest_seq=self.seq,oldest_seq=1,gap=False,events=[value])
        self.c.ingest(batch,received=self.now+when);return batch

    def test_completed_patterns_notify_and_retries_keep_same_summary(self):
        sub=self.sub(policy=dict(merge_ms=0,cooldown_ms=0));self.ingest(.1);self.ingest(2,'end',duration_ms=1900)
        first=self.c.bridge.claim('local-owner',sub['id'],now=self.now+3)
        self.c.bridge.acknowledge('local-owner',sub['id'],first['event_id'],first['lease'],now=self.now+3)
        long=self.c.bridge.claim('local-owner',sub['id'],now=self.now+3)
        summary=long['payload']['data']['summary'];self.assertEqual(summary['observations'][0]['kind'],'completed_long_press')
        retry=self.c.bridge.claim('local-owner',sub['id'],now=self.now+19)
        self.assertEqual(summary,retry['payload']['data']['summary'])

    def test_tap_release_summary_and_raw_history(self):
        self.sub(policy=dict(merge_ms=0,cooldown_ms=0))
        for args in [(.1,'start','a',0),(.3,'end','a',200),(.45,'start','b',0),(.65,'end','b',200)]:
            self.ingest(args[0],args[1],args[2],duration_ms=args[3])
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM bridge_outbox').fetchone()[0],3)
        result=self.c.call('summarize_interactions',dict(session_id='s'))
        self.assertEqual(len(result['events']),4);self.assertEqual(result['summary']['observations'][0]['count'],2)
        self.assertEqual(self.c.call('summarize_interactions',dict(session_id='s',limit=1))['summary']['observations'],[])

    def test_filtered_subscriptions_do_not_expose_other_channels(self):
        sub=self.sub(arguments=dict(channels=[0]))
        self.ingest(.1);self.ingest(.2,channel=1)
        payload=self.c.bridge.claim('local-owner',sub['id'],now=self.now+2)['payload']
        self.assertNotIn('私密通道名',json.dumps(payload,ensure_ascii=False))
        self.assertEqual(payload['data']['summary']['pressure_event_count'],1)

    def test_invalid_pressure_is_archived_without_triggering_feedback(self):
        self.sub();self.ingest(.1,quality='stale');self.ingest(.2,touch='b',source='external')
        self.assertEqual(len(self.c.history()['touches']),2)
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM bridge_outbox').fetchone()[0],0)

    def test_quiet_records_history_without_replaying_later(self):
        self.sub(policy=dict(quiet_hours=dict(enabled=True,start='00:00',end='00:00')))
        self.ingest(.1);self.assertEqual(len(self.c.history()['touches']),1)
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM bridge_outbox').fetchone()[0],0)
        with patch('interaction_bridge.time.time',return_value=self.now+1):self.c.bridge.save_preferences({}, {})
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM bridge_outbox').fetchone()[0],0)

    def test_live_quiet_change_cancels_pending_and_inflight_leases(self):
        sub=self.sub(policy=dict(merge_ms=0,cooldown_ms=0));self.ingest(.1)
        delivery=self.c.bridge.claim('local-owner',sub['id'],now=self.now+.2);self.ingest(.3,touch='b')
        with patch('interaction_bridge.time.time',return_value=self.now+.4):
            self.c.bridge.save_preferences(dict(quiet_hours=dict(enabled=True,start='11:00',end='13:00')), {})
        self.assertEqual({r[0] for r in self.c.db.execute('SELECT state FROM bridge_outbox')},{'suppressed'})
        with self.assertRaises(ValueError):self.c.bridge.acknowledge('local-owner',sub['id'],delivery['event_id'],delivery['lease'],now=self.now+.5)
        self.assertIsNone(self.c.bridge.claim('local-owner',sub['id'],now=self.now+3601))

    def test_selfcheck_does_not_claim_host_support_or_change_settings(self):
        self.c.device=lambda name,args:dict(device_id='doll',firmware='doll-lab-2.3.0',wifi_connected=True,sensor_mode='simulation',physical_outputs_enabled=False)
        before=list(self.c.db.execute('SELECT * FROM settings'))
        result=self.c.call('get_installation_status',dict(client_kind='stdio'))
        self.assertEqual(result['host_event_support'],'not_verified');self.assertEqual(result['client_registration'],'not_inspected')
        self.assertTrue(result['database_open']);self.assertEqual(result['device']['device_id'],'doll')
        self.assertEqual(list(self.c.db.execute('SELECT * FROM settings')),before)
        self.c.device=lambda *args:(_ for _ in ()).throw(ValueError('secret-device-response'))
        result=self.c.call('get_installation_status',{})
        self.assertNotIn('secret-device-response',json.dumps(result));self.assertIsNone(result['device'])


if __name__=='__main__':unittest.main()
