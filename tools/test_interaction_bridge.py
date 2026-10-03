"""Deterministic delivery tests: archive atomicity, targeting, leases and webhooks."""
import base64
import hashlib
import hmac
import json
import pathlib
import site
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
if (ROOT/'.tools/mcp-test-sdk').exists():
    sys.path.insert(0,str(ROOT/'.tools/mcp-test-sdk'));site.addsitedir(str(ROOT/'.tools/mcp-test-sdk'))
from companion import Companion
from mcp_events_adapter import MCPEventsAdapter,PROTOCOL
from webhook_delivery import WebhookSender,decode_secret,signed_headers,validate_url


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.tmp.name)/'archive.sqlite3'
        self.c=Companion(self.path,None,threading.Lock());self.now=time.time()
        with self.c.db:self.c.db.execute("INSERT INTO sessions VALUES('s','chat',?,NULL,?,300,NULL)",(self.now-1,self.now-1))
        self.c.device=lambda name,args:dict(device_id='doll')
        self.seq=0

    def tearDown(self):
        self.c.db.close();self.tmp.cleanup()

    def subscribe(self,**kwargs):
        return self.c.bridge.subscribe('local-owner','chat','s','doll',now=self.now,**kwargs)

    def event(self,when=.1,kind='pressure',phase='start',channel=0,value=2400,source='simulation'):
        self.seq+=1
        event=dict(seq=self.seq,uptime_ms=1000+int(when*1000),phase=phase,channel=channel,body_part='测试部位',source=source,
                   sensor_type=kind,direction='output' if kind=='vibration' else 'input',unit='degC' if kind=='temperature' else 'adc_raw',
                   quality='ok' if value is not None else 'adc_out_of_range',value=value,peak_raw=2400,duration_ms=100,touch_id='t'+str(self.seq))
        if phase=='end':event['touch_id']='t1'
        batch=dict(device_id='doll',boot_id='boot',uptime_ms=event['uptime_ms'],next_cursor=self.seq,latest_seq=self.seq,oldest_seq=1,gap=False,events=[event])
        self.c.ingest(batch,received=self.now+when)
        return batch

    def count(self):return self.c.db.execute('SELECT COUNT(*) FROM bridge_outbox').fetchone()[0]
    def claim(self,sub,when=2):return self.c.bridge.claim('local-owner',sub['id'],now=self.now+when)

    def test_ordinary_archive_does_not_notify(self):
        self.event();self.assertEqual(self.count(),0);self.assertEqual(len(self.c.history()['touches']),1)

    def test_merge_starts_ignore_release_and_dedupe(self):
        sub=self.subscribe();batch=self.event();self.event(.2,channel=1);self.event(.3,phase='end')
        self.c.ingest(batch,received=self.now+.4)
        self.assertEqual(self.count(),1);self.assertIsNone(self.claim(sub,.3))
        d=self.claim(sub);self.assertEqual(len(d['payload']['data']['events']),2)
        self.assertEqual({e['channel'] for e in d['payload']['data']['events']},{0,1})

    def test_no_output_feedback_loop_or_default_temperature(self):
        self.subscribe();self.event(kind='vibration',phase='output');self.event(.2,kind='temperature',phase='sample',value=32)
        self.assertEqual(self.count(),0)

    def test_temperature_baselines_are_per_channel_and_faults_skip(self):
        sub=self.subscribe(policy=dict(temperature_enabled=True,merge_ms=0,cooldown_ms=0))
        self.event(kind='temperature',phase='sample',value=25)
        self.event(.2,kind='temperature',phase='sample',value=25.3)
        self.event(.3,kind='temperature',phase='sample',value=25.3,channel=1)
        self.event(.4,kind='temperature',phase='sample',value=None)
        self.assertEqual(self.count(),2)

    def test_stale_and_disallowed_simulation_skip(self):
        self.subscribe(policy=dict(allow_simulation=False));self.event()
        self.assertEqual(self.count(),0)
        self.c.bridge.unsubscribe('local-owner',self.c.db.execute('SELECT id FROM bridge_subscriptions').fetchone()[0])
        self.subscribe();batch=self.event(when=1,source='sensor')
        self.assertEqual(self.count(),1)
        batch['events'][0]['seq']=99;batch['events'][0]['touch_id']='stale';batch.update(next_cursor=99,latest_seq=99)
        self.c.ingest(batch,received=self.now+60);self.assertEqual(self.count(),1)

    def test_atomic_archive_and_outbox_rollback(self):
        self.subscribe()
        with patch.object(self.c.bridge,'enqueue',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):self.event()
        self.assertEqual(self.count(),0);self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM boots').fetchone()[0],0)

    def test_target_exclusivity_session_binding_and_cancel(self):
        sub=self.subscribe()
        renewed=self.subscribe();self.assertEqual(sub['id'],renewed['id'])
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM bridge_subscriptions').fetchone()[0],1)
        with self.assertRaises(ValueError):self.c.bridge.subscribe('local-owner','other','s','doll',now=self.now)
        self.event();self.c.bridge.unsubscribe('local-owner',sub['id'])
        self.assertIsNone(self.claim(sub));self.assertEqual(self.c.db.execute('SELECT state FROM bridge_outbox').fetchone()[0],'cancelled')
        with self.assertRaises(ValueError):self.c.bridge.subscribe('local-owner','chat','missing','doll',now=self.now)

    def test_lease_single_inflight_retry_and_idempotent_ack(self):
        sub=self.subscribe(policy=dict(merge_ms=0,cooldown_ms=0));self.event();self.event(.5,channel=1)
        first=self.claim(sub);self.assertIsNone(self.claim(sub))
        retry=self.claim(sub,18);self.assertEqual(first['event_id'],retry['event_id']);self.assertNotEqual(first['lease'],retry['lease'])
        with self.assertRaises(ValueError):self.c.bridge.acknowledge('local-owner',sub['id'],first['event_id'],first['lease'],now=self.now+18)
        ack=self.c.bridge.acknowledge('local-owner',sub['id'],retry['event_id'],retry['lease'],reply='测试回复',source='demo',now=self.now+18)
        self.assertFalse(ack['duplicate'])
        ack=self.c.bridge.acknowledge('local-owner',sub['id'],retry['event_id'],retry['lease'],now=self.now+18)
        self.assertTrue(ack['duplicate']);self.assertIsNotNone(self.claim(sub,18))
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM bridge_replies').fetchone()[0],1)

    def test_long_generation_lease_renewal_and_wrong_owner(self):
        sub=self.subscribe();self.event();d=self.claim(sub)
        for at in [10,20,30,40]:self.c.bridge.renew('local-owner',sub['id'],d['event_id'],d['lease'],now=self.now+at)
        with self.assertRaises(ValueError):self.c.bridge.acknowledge('other',sub['id'],d['event_id'],d['lease'],now=self.now+41)
        self.c.bridge.acknowledge('local-owner',sub['id'],d['event_id'],d['lease'],now=self.now+41)

    def test_restarts_preserve_pending_without_replay(self):
        sub=self.subscribe();batch=self.event();self.c.db.close();self.c=Companion(self.path,None,threading.Lock())
        self.c.ingest(batch,received=self.now+.2);self.assertEqual(self.count(),1)
        self.assertEqual(self.claim(sub)['subscription_id'],sub['id'])

    def test_expired_session_and_subscription_stop_delivery(self):
        sub=self.subscribe(ttl_sec=1);self.event();self.assertIsNone(self.claim(sub,2))
        self.assertEqual(self.c.db.execute('SELECT state FROM bridge_outbox').fetchone()[0],'expired')

    def test_webhook_retries_preserve_ids_and_stop_410(self):
        sub=self.subscribe(transport='webhook',callback='https://callback.example/x',secret='unused')
        self.event();d=self.c.bridge.claim(transport='webhook',now=self.now+2)
        self.c.bridge.finish_webhook(d,503,now=self.now+2)
        self.assertIsNone(self.c.bridge.claim(transport='webhook',now=self.now+2.5))
        retry=self.c.bridge.claim(transport='webhook',now=self.now+3)
        self.assertEqual(d['payload'],retry['payload']);self.assertEqual(d['event_id'],retry['event_id'])
        self.c.bridge.finish_webhook(retry,410,now=self.now+3)
        self.assertFalse(self.c.db.execute('SELECT active FROM bridge_subscriptions').fetchone()[0])

    def test_policy_validation(self):
        for policy in [dict(max_age_sec=0),dict(cooldown_ms=True),dict(temperature_delta_c=float('nan')),dict(unknown=True)]:
            with self.assertRaises(ValueError):self.c.bridge.save_preferences(policy,{})
        self.assertEqual(self.c.bridge.preferences()['feedback']['max_characters'],160)

    def test_native_event_subscription_verification_and_protocol(self):
        class FakeSender:
            verified=0
            def verify(self,url,secret,sid):self.verified+=1
        sender=FakeSender();adapter=MCPEventsAdapter(self.c,lambda:[],sender)
        def rpc(method,params={}):
            params=dict(params,_meta={'io.modelcontextprotocol/protocolVersion':PROTOCOL})
            return adapter.rpc(dict(jsonrpc='2.0',id=1,method=method,params=params))
        self.assertIn('events',rpc('server/discover')['result']['capabilities'])
        self.assertIn('error',adapter.rpc(dict(jsonrpc='2.0',id=2,method='events/list')))
        self.assertEqual(rpc('events/list')['result']['events'][0]['name'],'doll.interaction')
        args=dict(device_id='doll',session_id='s');delivery=dict(mode='webhook',url='https://callback.example/hook',secret='whsec_'+base64.b64encode(b'a'*32).decode())
        params=dict(name='doll.interaction',arguments=args,delivery=delivery)
        sub=rpc('events/subscribe',params);self.assertNotIn('error',sub)
        again=rpc('events/subscribe',params);self.assertEqual(sub['result']['id'],again['result']['id'])
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM bridge_subscriptions').fetchone()[0],1)
        self.assertEqual(sender.verified,2)
        self.now=time.time() # Verification/storage may take time; this is a NEW event, not buffered history.
        self.event();self.assertEqual(self.count(),1)
        state=self.c.bridge.state();self.assertNotIn('secret',state['subscriptions'][0]);self.assertNotIn('callback',state['subscriptions'][0])
        self.assertNotIn('error',rpc('events/unsubscribe',params));self.assertNotIn('error',rpc('events/unsubscribe',params))
        with patch.object(sender,'verify',side_effect=ValueError('challenge mismatch')):
            self.assertEqual(rpc('events/subscribe',params)['error']['code'],-32015)
        self.assertEqual(self.c.db.execute('SELECT active FROM bridge_subscriptions').fetchone()[0],0)


class WebhookTests(unittest.TestCase):
    def test_private_callback_dns_and_url_rejection(self):
        for url in ['http://example.com/x','https://127.0.0.1/x','https://[::1]/x','https://169.254.169.254/x',
                    'https://user:pass@example.com/x','https://example.com:444/x','https://example.com/#fragment','https://localhost/x',
                    'https://224.0.0.1/x','https://[ff02::1]/x']:
            with self.assertRaises(ValueError):validate_url(url,False)
        with patch('socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.1',443))]):
            with self.assertRaises(ValueError):validate_url('https://callback.example/x')

    def test_standard_webhooks_signature_exact_body(self):
        secret='whsec_'+base64.b64encode(b'x'*32).decode();body=b'{"hello":"world"}'
        headers=signed_headers(secret,'evt_123',body,'sub_1',timestamp=100)
        expected=base64.b64encode(hmac.new(b'x'*32,b'evt_123.100.'+body,hashlib.sha256).digest()).decode()
        self.assertEqual(headers['webhook-signature'],'v1,'+expected)
        self.assertEqual(headers['X-MCP-Subscription-Id'],'sub_1')
        for bad in ['x','whsec_x','whsec_'+base64.b64encode(b'x'*23).decode()]:
            with self.assertRaises(ValueError):decode_secret(bad)

    def test_verification_challenge_must_match(self):
        sender=WebhookSender()
        with patch.object(sender,'send',return_value=(200,{'challenge':'wrong'})):
            with self.assertRaises(ValueError):sender.verify('https://example.com/x','irrelevant','sub')


if __name__=='__main__':unittest.main()
