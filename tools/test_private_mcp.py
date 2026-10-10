"""Real SDK protocol against explicit fixtures; never report this as Chat acceptance."""
from contextlib import asynccontextmanager
import asyncio
import json
import logging
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

from companion import Companion
from remote_mcp import create_private_remote, CapabilityStore, ConnectionDiagnostics
from chat_mcp_gateway import PROFILES
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import httpx



class DeadlineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'history.sqlite3'
        self.c = Companion(self.path,None,threading.Lock())
        self.c.sync = Mock()
        self.c.ingest(self.batch([]),received=100)

    def tearDown(self):
        self.c.db.close(); self.temp.cleanup()

    def batch(self,events):
        last = events[-1]['seq'] if events else 0
        return dict(device_id='fixture',boot_id='boot',uptime_ms=0,next_cursor=last,
                    latest_seq=last,oldest_seq=1,gap=False,events=events)

    def event(self,seq,uptime,phase='start',touch=None):
        return dict(seq=seq,uptime_ms=uptime,phase=phase,touch_id=touch or str(seq),
                    channel=0,body_part='left hand',source='simulation',peak_raw=1800,duration_ms=1000,
                    sensor_type='pressure',direction='input',unit='adc_raw',quality='ok')

    def test_deadline_not_extended_dedup_closed_delivery_and_restart(self):
        with patch('companion.utcnow',return_value=100): s=self.c.start('chat-A',duration_sec=60)
        self.c.ingest(self.batch([self.event(1,1000)]),received=101)
        with patch('companion.utcnow',return_value=110):
            again=self.c.start('chat-A',duration_sec=3600)
            self.assertEqual(again['id'],s['id']); self.assertEqual(again['deadline'],160)
            with self.assertRaises(ValueError):self.c.start('chat-B',duration_sec=60)
            with self.assertRaises(ValueError):self.c.call('get_interaction_device_events',dict(session_id=s['id'],chat_id='chat-B'))
            with self.assertRaises(ValueError):self.c.end(s['id'],chat_id='chat-B')
            page=self.c.call('get_interaction_device_events',dict(session_id=s['id'],after=0))
        self.assertEqual(len(page['events']),1)
        self.c.ingest(self.batch([self.event(1,1000)]),received=111)
        with patch('companion.utcnow',return_value=112):
            self.assertEqual(self.c.call('get_interaction_device_events',dict(session_id=s['id'],after=page['next_cursor']))['events'],[])
        self.c.db.close(); self.c=Companion(self.path,None,threading.Lock())
        self.assertEqual(self.c.last_sync,111)
        with patch('companion.utcnow',return_value=160):
            self.assertIsNone(self.c.active())
            closed=self.c.call('get_interaction_device_events',dict(session_id=s['id'],after=0))
        self.assertTrue(closed['session_closed']);self.assertEqual(closed['events'],[])
        self.assertEqual(closed['session']['reason'],'duration_expired')
        self.assertEqual(closed['session']['ended'],160)
        self.c.ingest(self.batch([self.event(2,61000,'end','1'),self.event(3,62000)]),received=162)
        old=self.c.device_history(session_id=s['id'])['events']
        self.assertEqual([e['phase'] for e in old],['start','end'])
        self.assertIsNone(self.c.device_history()['events'][-1]['session_id'])
        self.assertEqual(self.c.history()['touches'][0]['duration_ms'],1000)

    def test_offline_queries_never_sync_and_source_survives(self):
        self.c.ingest(self.batch([self.event(1,1000)]),received=101)
        self.c.error='Device offline'
        self.c.sync=Mock(side_effect=AssertionError('A read queried the device'))
        for name in ('query_touch_history','query_device_history','summarize_interactions','get_history_statistics'):
            data=self.c.call(name,{})
            self.assertEqual(data['history_source'],'computer_sqlite')
            self.assertEqual(data['collector_error'],'Device offline')
            self.assertEqual(data['last_sync'],101)
        self.c.sync.assert_not_called()
        self.c.set_setting('cached_get_channel_config',json.dumps(dict(data={'channels':[{'id':0,'type':'pressure','body_part':'left hand'}]},saved_at=100)))
        cached=self.c.call('get_cached_channel_config',{})
        self.assertEqual(cached['configuration_saved_at'],100)
        self.assertEqual(cached['channels'][0]['type'],'pressure')

    def test_validation_legacy_and_idle_precedence(self):
        for bad in (True,0,-1,3601,1.5,'60'):
            with self.assertRaises(ValueError):self.c.start('c',duration_sec=bad)
        with patch('companion.utcnow',return_value=100):
            s=self.c.start('legacy')
            self.assertIsNone(s['deadline'])
            self.c.end(s['id'])
            new=self.c.start('c',idle_timeout_sec=30,duration_sec=60)
        with patch('companion.utcnow',return_value=160):self.assertIsNone(self.c.active())
        row=self.c.db.execute('SELECT * FROM sessions WHERE id=?',(new['id'],)).fetchone()
        self.assertEqual(row['reason'],'idle_timeout');self.assertEqual(row['ended'],130)


class PrivateMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_lan_host_keeps_capability_and_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            gateway,app,store=create_private_remote(folder,port=8775,profile='history',listen_host='192.168.1.20')
            self.assertIn('192.168.1.20:8775',gateway.settings.transport_security.allowed_hosts)
            async with gateway.session_manager.run():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://192.168.1.20:8775') as http:
                    self.assertEqual((await http.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/list'})).status_code,404)
                    async with streamable_http_client(store.local_url('192.168.1.20',8775),http_client=http) as (read,write,_):
                        async with ClientSession(read,write) as client:
                            await client.initialize()
                            tools=await client.list_tools()
                            self.assertEqual({t.name for t in tools.tools},set(PROFILES['history']))
                    bad=await http.post('/'+store.key()+'/mcp',headers={'Host':'foreign.example'},json={})
                    self.assertEqual(bad.status_code,421)

    def test_lan_requires_specific_private_address(self):
        with tempfile.TemporaryDirectory() as folder:
            for host in ('0.0.0.0','8.8.8.8','224.0.0.1','169.254.1.2','example.com'):
                with self.assertRaises(ValueError): create_private_remote(folder,listen_host=host)

    async def asyncSetUp(self):
        self.previous_logging = logging.root.manager.disable
        logging.disable(logging.CRITICAL)

    async def asyncTearDown(self):
        logging.disable(self.previous_logging)

    @asynccontextmanager
    async def connect(self,folder,profile='interaction'):
        gateway,app,store=create_private_remote(folder,'https://fixture.example',profile=profile)
        async with gateway.session_manager.run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://fixture.example') as http:
                async with streamable_http_client(store.url('https://fixture.example'),http_client=http) as (read,write,_):
                    async with ClientSession(read,write) as client:
                        await client.initialize()
                        yield client,http,store

    async def test_profiles_actual_call_ids_and_secret_free_audit(self):
        for profile in PROFILES:
            with tempfile.TemporaryDirectory() as folder,patch('companion_mcp.call',return_value={'device_id':'fixture'}):
                async with self.connect(folder,profile) as (client,http,store):
                    tools=(await client.list_tools()).tools
                    self.assertEqual({t.name for t in tools},set(PROFILES[profile]))
                    self.assertTrue(all(t.meta['securitySchemes']==[{'type':'noauth'}] for t in tools))
                    if profile=='history':self.assertTrue(all(t.annotations.readOnlyHint for t in tools))
                    results=[(await client.call_tool(name,{})).structuredContent for name in ('get_installation_status','doll_get_status')]
                    self.assertTrue((await client.call_tool('set_vibration',{'channel':0,'intensity':100})).isError)
                    logs=[json.loads(line) for line in Path(folder,'calls.jsonl').read_text().splitlines()]
                    self.assertEqual({r['verification']['call_id'] for r in results},{l['call_id'] for l in logs})
                    self.assertNotIn(store.key(),Path(folder,'calls.jsonl').read_text())
                    self.assertNotIn(store.key(),Path(folder,'gateway.json').read_text())

    async def test_exact_route_rotation_restart_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder,patch('companion_mcp.call',return_value={}):
            async with self.connect(folder) as (client,http,store):
                key=store.key();old='/'+key+'/mcp'
                for path in ('/mcp','/','/companion','/connection','/bridge/mcp','/register','/health',
                             '/wrong/mcp',old+'/',old+'?x=1','/%'+format(ord(key[0]),'02x')+key[1:]+'/mcp'):
                    self.assertEqual((await http.post(path,json={})).status_code,404,path)
                self.assertEqual(CapabilityStore(folder).key(),key)
                CapabilityStore(folder).reset()
                self.assertNotEqual(store.key(),key)
                self.assertEqual((await http.post(old,json={})).status_code,404)
                current='/'+store.key()+'/mcp'
                response=await http.post(current,json={'jsonrpc':'2.0','id':1,'method':'tools/list'},
                                        headers={'accept':'application/json, text/event-stream'})
                self.assertEqual(response.status_code,200)
                store.path.write_text('broken',encoding='utf-8')
                self.assertEqual((await http.post(current,json={})).status_code,404)

    async def test_transport_diagnostics_distinguish_discovery_and_rejection_without_secrets(self):
        sentinel = 'PRIVATE-PAYLOAD-HEADER-SENTINEL'
        with tempfile.TemporaryDirectory() as folder:
            async with self.connect(folder) as (client, http, store):
                await client.list_tools()
                path = '/' + store.key() + '/mcp'
                rejected = await http.post(path, json={'jsonrpc':'2.0', 'id':2,
                    'method':'tools/call', 'params':{'name':sentinel, 'arguments':{'secret':sentinel}}},
                    headers={'host':sentinel, 'authorization':'Bearer '+sentinel,
                             'accept':'application/json, text/event-stream'})
                self.assertEqual(rejected.status_code, 421)
                self.assertEqual((await http.get('/wrong-secret/mcp?secret='+sentinel)).status_code, 404)
                self.assertEqual((await http.post(path, json={},
                    headers={'origin':'https://'+sentinel})).status_code, 403)
                raw = Path(folder, 'connection-diagnostics.jsonl').read_text()
                self.assertNotIn(store.key(), raw)
                for secret in (sentinel, 'wrong-secret', 'fixture.example', 'Bearer'):
                    self.assertNotIn(secret, raw)
                entries = [json.loads(line) for line in raw.splitlines()]
                self.assertTrue(any(x['rpc_method']=='initialize' and x['status']==200 for x in entries))
                self.assertTrue(any(x['rpc_method']=='tools/list' and x['status']==200 for x in entries))
                received = {x['request_id'] for x in entries if x['stage']=='received'}
                responses = {x['request_id'] for x in entries if x['stage']=='response'}
                self.assertEqual(received, responses)
                self.assertTrue(any(x['host_kind']=='other' and x['status']==421 for x in entries))
                self.assertTrue(any(not x['private_path_matched'] and x['status']==404 for x in entries))
                self.assertTrue(any(x['origin_present'] and x['status']==403 for x in entries))

    async def test_private_get_returns_prompt_405_after_path_host_and_origin_validation(self):
        with tempfile.TemporaryDirectory() as folder, patch('companion_mcp.call', return_value={'device_id':'fixture'}):
            async with self.connect(folder) as (client, http, store):
                path = '/'+store.key()+'/mcp'
                for accept in ('text/event-stream', '*/*'):
                    response = await asyncio.wait_for(http.get(path, headers={'accept':accept}), timeout=1)
                    self.assertEqual(response.status_code, 405)
                    self.assertEqual(response.headers['allow'], 'POST')
                    self.assertEqual(response.headers['cache-control'], 'no-store')
                self.assertEqual((await http.get('/wrong/mcp', headers={'host':'untrusted.example'})).status_code, 404)
                self.assertEqual((await http.get(path, headers={'host':'untrusted.example'})).status_code, 421)
                self.assertEqual((await http.get(path, headers={'origin':'https://untrusted.example'})).status_code, 403)
                self.assertEqual({tool.name for tool in (await client.list_tools()).tools}, set(PROFILES['interaction']))
                result = await client.call_tool('doll_get_status', {})
                self.assertFalse(result.isError)
                self.assertEqual(result.structuredContent['device_id'], 'fixture')
                self.assertTrue(result.structuredContent['verification']['call_id'])

    async def test_diagnostic_probe_hint_is_allowlisted_and_does_not_bypass_validation(self):
        sentinel = 'PRIVATE-ARBITRARY-PROBE-HEADER-SENTINEL'
        with tempfile.TemporaryDirectory() as folder:
            async with self.connect(folder) as (_, http, store):
                path = '/'+store.key()+'/mcp'
                for offered, expected in (('health','health'), ('verification','verification'),
                                          (sentinel,'unmarked')):
                    response = await http.get(path, headers={'x-ai-doll-probe':offered,
                                                             'host':'untrusted.example'})
                    self.assertEqual(response.status_code, 421)
                    entries = [json.loads(line) for line in Path(folder,'connection-diagnostics.jsonl').read_text().splitlines()]
                    self.assertEqual(entries[-1]['probe_kind'], expected)
                    self.assertEqual(entries[-1]['stage'], 'response')
                raw = Path(folder,'connection-diagnostics.jsonl').read_text()
                self.assertNotIn(sentinel, raw)
                self.assertNotIn(store.key(), raw)

    async def test_deployment_probe_marks_actual_sdk_discovery_and_verification_requests(self):
        from deploy_mcp import probe_url
        client_factory = httpx.AsyncClient
        with tempfile.TemporaryDirectory() as folder, patch('companion_mcp.call', return_value={'device_id':'fixture'}):
            gateway, app, store = create_private_remote(folder, 'https://fixture.example', profile='status')

            def asgi_client(*args, **kwargs):
                # Keep probe_url's real default headers and SDK handshake; only
                # replace network I/O with this explicit in-process fixture.
                kwargs['transport'] = httpx.ASGITransport(app=app)
                return client_factory(*args, **kwargs)

            async with gateway.session_manager.run():
                with patch('httpx.AsyncClient', side_effect=asgi_client):
                    consumed = 0
                    for calls, kind in ((False, 'health'), (True, 'verification')):
                        result = await probe_url(store.url('https://fixture.example'), 'status', calls=calls)
                        self.assertTrue(result['protocol_connected'])
                        self.assertEqual(result['tool_count'], 2)
                        self.assertFalse(result['ordinary_chat_verified'])
                        entries = [json.loads(line) for line in app.path.read_text().splitlines()]
                        current = entries[consumed:]
                        consumed = len(entries)
                        self.assertTrue(current)
                        self.assertTrue(all(entry['probe_kind']==kind for entry in current))
                        methods = [entry['rpc_method'] for entry in current if entry['stage']=='response']
                        self.assertIn('initialize', methods)
                        self.assertIn('tools/list', methods)
                        self.assertEqual(methods.count('tools/call'), 2 if calls else 0)
                        if calls:
                            self.assertTrue(all(value['verification']['call_id']
                                for value in result['status_calls'].values()))

    async def test_diagnostic_arrival_is_visible_while_body_hangs_and_cancellation_is_correlated(self):
        sentinel = 'PRIVATE-INCOMPLETE-BODY-SENTINEL'
        with tempfile.TemporaryDirectory() as folder:
            store = CapabilityStore(folder)
            waiting = asyncio.Event()
            blocked = asyncio.Event()
            messages = iter([{'type':'http.request', 'body':sentinel.encode(), 'more_body':True}])

            async def receive():
                first = next(messages, None)
                if first is not None:
                    return first
                waiting.set()
                await blocked.wait()
                return {'type':'http.disconnect'}

            async def send(message):
                self.fail('An incomplete body must not have produced a response')

            async def read_body(scope, receive, send):
                while (await receive()).get('more_body', False):
                    pass

            diagnostics = ConnectionDiagnostics(read_body, store, 'https://fixture.example')
            scope = {'type':'http', 'method':'POST', 'path':'/'+store.key()+'/mcp',
                     'raw_path':('/'+store.key()+'/mcp').encode(), 'query_string':b'',
                     'headers':[(b'host', b'fixture.example'), (b'accept', b'application/json')]}
            task = asyncio.create_task(diagnostics(scope, receive, send))
            try:
                await asyncio.wait_for(waiting.wait(), timeout=1)
                entries = [json.loads(line) for line in diagnostics.path.read_text().splitlines()]
                self.assertEqual([entry['stage'] for entry in entries], ['received'])
                self.assertIsNone(entries[0]['status'])
                self.assertFalse(task.done())
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            raw = diagnostics.path.read_text()
            entries = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual([entry['stage'] for entry in entries], ['received', 'unanswered'])
            self.assertEqual(entries[-1]['outcome'], 'cancelled')
            self.assertEqual(len({entry['request_id'] for entry in entries}), 1)
            self.assertNotIn(sentinel, raw)
            self.assertNotIn(store.key(), raw)

    async def test_diagnostic_unanswered_exception_and_return_have_finite_outcomes(self):
        sentinel = 'PRIVATE-EXCEPTION-AND-REQUEST-SENTINEL'
        for fails, outcome in ((True, 'exception'), (False, 'returned_without_response')):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as folder:
                store = CapabilityStore(folder)

                async def receive():
                    return {'type':'http.request', 'body':json.dumps({'jsonrpc':'2.0',
                        'id':1, 'method':'initialize', 'params':{'private':sentinel}}).encode(),
                        'more_body':False}

                async def send(message):
                    self.fail('The fixture must not send a response')

                async def no_response(scope, receive, send):
                    await receive()
                    if fails:
                        raise RuntimeError(sentinel)

                diagnostics = ConnectionDiagnostics(no_response, store, 'https://fixture.example')
                scope = {'type':'http', 'method':'POST', 'path':'/'+store.key()+'/mcp',
                         'raw_path':('/'+store.key()+'/mcp').encode(), 'query_string':b'',
                         'headers':[(b'host', b'fixture.example'), (b'accept', b'application/json')]}
                if fails:
                    with self.assertRaisesRegex(RuntimeError, sentinel):
                        await diagnostics(scope, receive, send)
                else:
                    await diagnostics(scope, receive, send)
                raw = diagnostics.path.read_text()
                entries = [json.loads(line) for line in raw.splitlines()]
                self.assertEqual([entry['stage'] for entry in entries], ['received', 'unanswered'])
                self.assertEqual(entries[-1]['outcome'], outcome)
                self.assertEqual(entries[-1]['rpc_method'], 'initialize')
                self.assertEqual(len({entry['request_id'] for entry in entries}), 1)
                self.assertTrue(all(entry['status'] is None for entry in entries))
                self.assertNotIn(sentinel, raw)
                self.assertNotIn(store.key(), raw)

    async def test_diagnostic_rotation_and_io_failure_preserve_mcp(self):
        with tempfile.TemporaryDirectory() as folder:
            gateway, app, store = create_private_remote(folder, 'https://fixture.example')
            app.max_bytes = 512
            async with gateway.session_manager.run():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                             base_url='https://fixture.example') as http:
                    for _ in range(10):
                        self.assertEqual((await http.get('/missing')).status_code, 404)
                    previous = Path(folder, 'connection-diagnostics.previous.jsonl')
                    self.assertTrue(previous.exists())
                    self.assertLess(previous.stat().st_size, 1024)
                    self.assertLess(app.path.stat().st_size, 1024)
                    app.path = Path(folder)  # An unwritable log destination must not break MCP.
                    app.max_bytes = 1000000
                    response = await http.post('/'+store.key()+'/mcp',
                        json={'jsonrpc':'2.0','id':1,'method':'tools/list'},
                        headers={'accept':'application/json, text/event-stream'})
                    self.assertEqual(response.status_code, 200)


if __name__=='__main__':unittest.main()
