"""Protocol tests only. These do not claim an Operit/WeChat model was invoked."""
import datetime as dt
import json
import tempfile
import time
import unittest
from pathlib import Path
import httpx
from host_event_forwarder import Forwarder, envelope, request_payload, validate_config


def event():
    return dict(eventId='evt_'+'a'*32, timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        data=dict(session_id='session-1', device_id='fixture-doll', events=[dict(channel=0,
            body_part='头', source='simulation', sensor_type='pressure', direction='input', phase='start',
            value=3200, unit='adc_raw', quality='ok')], persona='', feedback={'tone':'温柔自然'}))


class ForwarderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = dict(kind='generic', target_id='existing-chat', url='http://127.0.0.1:8780/doll/events', token='fixture-token')
        self.requests, self.local_requests = [], []
        self.status = 202
        self.receipt = None
        self.renew_status = 200

        def host(request):
            self.requests.append(request)
            body = json.loads(request.content)
            receipt = self.receipt or dict(accepted=True, event_id=body.get('event_id'), target_id=body.get('target_id'))
            return httpx.Response(self.status, json=receipt)

        def local(request):
            self.local_requests.append(request)
            return httpx.Response(self.renew_status if request.url.path == '/bridge/renew' else 200, json={'renewed':True})
        self.host = host
        self.local = local
        self.worker = self.make_worker()

    def make_worker(self):
        return Forwarder(self.config, Path(self.directory.name),
            local=httpx.Client(base_url='http://127.0.0.1:8768', transport=httpx.MockTransport(self.local)),
            remote=httpx.Client(transport=httpx.MockTransport(self.host)))

    def tearDown(self):
        self.close(self.worker)
        self.directory.cleanup()

    @staticmethod
    def close(worker):
        worker.local.close(); worker.remote.close(); worker.db.close()

    def message(self, value=None):
        self.worker.session = dict(id='session-1', deadline=time.time()+60)
        self.worker.sub = dict(id='sub-1')
        return dict(subscription_id='sub-1', event=value or event(), lease='lease-1')

    def test_accepted_event_is_durable_and_ack_has_no_fake_model_reply(self):
        message = self.message()
        self.worker.handle(message)
        ack = next(r for r in self.local_requests if r.url.path == '/bridge/ack')
        self.assertNotIn('reply', json.loads(ack.content))
        self.assertFalse(self.worker.state['model_reply_verified'])
        self.assertFalse(self.worker.state['channel_delivery_verified'])
        self.close(self.worker); self.worker = self.make_worker()
        self.worker.handle(self.message(message['event']))
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(json.loads(self.requests[0].content)['event']['data']['events'][0]['source'], 'simulation')

    def test_failed_ack_retry_reuses_host_receipt(self):
        message = self.message()
        self.worker.accept(message['event'])  # Host accepted, collector ACK lost.
        self.worker.handle(message)
        self.assertEqual(len(self.requests), 1)

    def test_bad_receipt_or_redirect_cannot_ack(self):
        self.receipt = dict(accepted=True, event_id='wrong', target_id='existing-chat')
        with self.assertRaises(RuntimeError): self.worker.handle(self.message())
        self.assertFalse(any(r.url.path=='/bridge/ack' for r in self.local_requests))
        self.status = 302
        with self.assertRaises(RuntimeError): self.worker.accept(event())
        self.assertEqual(self.worker.db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 0)

    def test_transient_host_failure_retries_same_id(self):
        value = event(); self.status = 502
        with self.assertRaises(RuntimeError): self.worker.accept(value)
        self.status = 202; self.worker.accept(value)
        self.assertEqual(self.requests[0].headers['Idempotency-Key'], self.requests[1].headers['Idempotency-Key'])

    def test_lost_lease_and_wrong_chat_do_not_send(self):
        self.renew_status = 400
        with self.assertRaises(RuntimeError): self.worker.handle(self.message())
        message = self.message(); message['event']['data']['session_id']='other-chat'
        with self.assertRaises(ValueError): self.worker.handle(message)
        self.assertEqual(self.requests, [])

    def test_expired_session_and_old_event_do_not_send(self):
        value=event(); value['timestamp']=dt.datetime.fromtimestamp(time.time()-40,dt.timezone.utc).isoformat()
        with self.assertRaises(ValueError): self.worker.accept(value)
        self.worker.session=dict(deadline=time.time()-1)
        with self.assertRaises(ValueError): self.worker.accept(event())
        self.assertEqual(self.requests, [])

    def test_outputs_and_offline_records_are_rejected(self):
        for field, value in [('direction','output'),('source','offline'),('delivery_quality','offline_replay')]:
            data=event(); data['data']['events'][0][field]=value
            with self.assertRaises(ValueError): envelope(data,'chat')

    def test_openclaw_keeps_existing_route_and_model(self):
        config=dict(self.config, kind='openclaw', url='https://gateway.example.com/hooks/agent',
            agent_id='main', session_key='agent:main:wechat:dm:fixture', channel='openclaw-weixin', recipient='fixture-peer')
        validate_config(config)
        body=request_payload(config,event(),time.time()+5)
        self.assertEqual(body['sessionMode'],'persistent')
        self.assertEqual(body['sessionKey'],config['session_key'])
        self.assertEqual(body['to'],'fixture-peer')
        self.assertNotIn('model',body)
        self.assertNotIn('thinking',body)
        self.worker.config=config; self.receipt=dict(ok=True,runId='fixture-run'); self.status=200
        self.worker.accept(event())
        self.assertFalse(self.worker.state['channel_delivery_verified'])

    def test_unsafe_and_incomplete_destinations_fail(self):
        for url in ['http://example.com/hooks/agent','https://user:pass@example.com/hooks/agent',
                    'https://example.com/hooks/agent?token=x','http://0.0.0.0:8780']:
            with self.assertRaises(ValueError): validate_config(dict(self.config,url=url))
        with self.assertRaises(ValueError): validate_config(dict(self.config,kind='openclaw',url='https://example.com/hooks/agent'))

    def test_destination_change_does_not_inherit_receipt(self):
        value=event(); self.worker.accept(value)
        self.worker.config=dict(self.config,target_id='another-existing-chat')
        self.worker.accept(value)
        self.assertEqual(len(self.requests),2)

    def test_complete_stream_loop_owns_session_and_cleans_up(self):
        self.message()
        delivery=json.dumps(dict(subscription_id='sub-1',event=event(),lease='lease-1'))
        reads=0
        def collector(request):
            nonlocal reads
            self.local_requests.append(request)
            if request.url.path=='/bridge/events':
                return httpx.Response(200,headers={'Content-Type':'text/event-stream'},
                    content=('event: interaction\ndata: '+delivery+'\n\n').encode())
            if request.url.path=='/bridge/subscriptions': return httpx.Response(200,json={'id':'sub-1'})
            if request.url.path=='/companion/tool':
                body=json.loads(request.content)
                if body['name']=='start_interaction':
                    self.assertEqual(body['arguments']['duration_sec'],60)
                    self.assertEqual(body['arguments']['chat_id'],'existing-chat')
                    return httpx.Response(200,json={'id':'session-1','deadline':time.time()+60})
                if body['name']=='doll_get_status': return httpx.Response(200,json={'device_id':'fixture-doll'})
                if body['name']=='get_interaction_status':
                    reads+=1
                    return httpx.Response(200,json={'active_session':{'id':'session-1'} if reads==1 else None})
            return httpx.Response(200,json={'ok':True})
        self.worker.local.close()
        self.worker.local=httpx.Client(base_url='http://127.0.0.1:8768',transport=httpx.MockTransport(collector))
        self.worker.run(60)
        self.assertEqual(len(self.requests),1)
        self.assertEqual(self.worker.state['state'],'ended')
        self.assertTrue(any(r.url.path=='/bridge/unsubscribe' for r in self.local_requests))
        ends=[json.loads(r.content) for r in self.local_requests if r.url.path=='/companion/tool' and json.loads(r.content)['name']=='end_interaction']
        self.assertEqual(ends[0]['arguments'],{'session_id':'session-1','chat_id':'existing-chat'})

    def test_busy_other_chat_cannot_be_taken_over(self):
        self.worker.local.close()
        self.worker.local=httpx.Client(base_url='http://127.0.0.1:8768',transport=httpx.MockTransport(
            lambda _:httpx.Response(400,json={'error':'Another chat owns the session'})))
        with self.assertRaises(RuntimeError): self.worker.run(60)
        self.assertIsNone(self.worker.session)
        self.assertEqual(self.requests,[])


if __name__ == '__main__': unittest.main()
