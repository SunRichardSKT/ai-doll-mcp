"""Direct device upload: durable history, real HTTP and existing-chat dispatch."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from direct_server import DirectServer, DirectHTTPServer, handler_for, OWNER


def packet(seq=0, phase='start', source='simulation', uptime=10000, old=False):
    now = round(time.time()*1000)
    event = dict(seq=seq, uptime_ms=uptime if not old else uptime-10000,
                 phase=phase, touch_id='boot-touch', channel=0, body_part='头', source=source,
                 raw=2500 if phase=='start' else 0, peak_raw=2500, duration_ms=500,
                 sensor_type='pressure', direction='input', quality='ok', unit='adc_raw',
                 time_quality='device_clock', device_time_ms=now if not old else now-10000)
    batch = dict(device_id='AI-Doll-test', boot_id='ab'*16, uptime_ms=uptime,
                 events=[], persistent_events=[], next_cursor=seq, latest_seq=seq,
                 oldest_seq=1, gap=False, storage_cursor=seq, storage_has_more=False,
                 event_storage=dict(available=True,storage_epoch='cd'*16,lost_records=0,
                     corrupt_records=0,write_failures_since_boot=0,clock_synced=True))
    if seq:
        batch['persistent_events']=[dict(storage_id=seq,boot_id=batch['boot_id'],event=event)]
    status = dict(device_id=batch['device_id'],boot_id=batch['boot_id'],firmware='test',
                  event_storage=batch['event_storage'],sensor_mode='simulation',wifi_connected=True,
                  physical_outputs_enabled=False)
    snapshot = dict(status=status,channels={'channels':[dict(channel=0,name='头',type='pressure',enabled=True,driver='simulation',options={})]},
                    capabilities={},values={},operating_mode={})
    return dict(protocol=1,batch=batch,snapshot=snapshot,command_results=[])


class DirectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = DirectServer(self.tmp.name)
        self.pair = self.app.pair('我的娃娃')
        self.key = self.pair['device_token']
        self.device = self.app.resolve(self.pair['id'])
        self.device.c.experience.update_preferences({'proactive_enabled':True})

    def tearDown(self):
        self.app.close();self.tmp.cleanup()

    def receive(self, body=None):
        return self.app.receive(self.key,body or packet())

    def test_device_token_separate_from_admin_and_binds_identity(self):
        with self.assertRaises(PermissionError):self.app.receive(self.app.admin_token,packet())
        self.receive()
        wrong=packet();wrong['batch']['device_id']='other';wrong['snapshot']['status']['device_id']='other'
        with self.assertRaises(PermissionError):self.receive(wrong)
        with self.app.db:self.app.db.execute('UPDATE devices SET revoked=1')
        with self.assertRaises(PermissionError):self.receive()

    def test_commit_before_ack_dedup_and_restart_history(self):
        reply=self.receive(packet(1));self.assertEqual(reply['storage_cursor'],1)
        self.receive(packet(1))
        self.assertEqual(len(self.device.c.device_history()['events']),1)
        token=self.app.admin_token;self.app.close()
        self.app=DirectServer(self.tmp.name);self.assertEqual(token,self.app.admin_token)
        self.device=self.app.resolve(self.pair['id']);self.receive(packet(1))
        self.assertEqual(len(self.device.c.device_history()['events']),1)
        self.assertEqual(self.device.c.device_history()['history_source'],'server_sqlite')

    def test_invalid_page_rollback_no_ack(self):
        bad=packet(1);bad['batch']['storage_cursor']=2
        with self.assertRaises(ValueError):self.receive(bad)
        self.assertFalse(self.device.c.device_history()['events'])

    def test_idle_frontend_claims_new_event_without_user_message(self):
        self.receive()
        c=self.device.c
        session=c.start('existing-chat',duration_sec=60)
        sub=c.bridge.subscribe(OWNER,'existing-chat',session['id'],'AI-Doll-test')
        self.receive(packet(1))
        delivery=c.bridge.claim(OWNER,sub['id'],now=time.time()+.4)
        self.assertIsNotNone(delivery)
        event=delivery['payload'];self.assertEqual(event['data']['events'][0]['body_part'],'头')
        self.assertEqual(event['data']['events'][0]['source'],'simulation')
        c.bridge.acknowledge(OWNER,sub['id'],event['eventId'],delivery['lease'],reply='模型回调测试替身',source='demo')
        self.receive(packet(1))
        self.assertIsNone(c.bridge.claim(OWNER,sub['id'],now=time.time()+.4))

    def test_offline_history_and_no_late_commands(self):
        self.receive(packet(1));self.device.c.last_sync=time.time()-20
        self.assertEqual(len(self.device.c.call('query_device_history',{})['events']),1)
        with self.assertRaises(ConnectionError):self.device.queue('simulate_channel_input',{'channel':0,'value':1000})

    def test_old_events_archive_without_wakeup(self):
        self.receive();session=self.device.c.start('chat')
        sub=self.device.c.bridge.subscribe(OWNER,'chat',session['id'],'AI-Doll-test')
        self.receive(packet(1,old=True))
        self.assertEqual(len(self.device.c.device_history()['events']),1)
        self.assertIsNone(self.device.c.bridge.claim(OWNER,sub['id'],now=time.time()+.4))

    def test_command_dispatch_once_result_and_expiry(self):
        self.receive();job=self.device.queue('set_channel_config',{'channels':[]})
        reply=self.receive();self.assertEqual(reply['commands'][0]['id'],job['id'])
        self.assertFalse(self.receive()['commands'])
        result=packet();result['command_results']=[dict(id=job['id'],rpc={'result':{'ok':True}})]
        self.assertEqual(self.receive(result)['acknowledged_commands'],[job['id']])
        self.assertEqual(self.device.command(job['id'])['state'],'completed')
        expired=self.device.queue('doll_simulate_press',{'channel':0,'value':1000},ttl=-1)
        self.assertFalse(self.receive()['commands'])
        self.assertEqual(self.device.command(expired['id'])['state'],'expired')

    def test_device_archives_are_isolated(self):
        self.receive(packet(1));other=self.app.pair('other')
        self.assertFalse(self.app.resolve(other['id']).c.device_history()['events'])

    def test_snapshot_read_does_not_wait_for_remote_command(self):
        self.receive();answers=[]
        thread=threading.Thread(target=lambda:answers.append(self.device.c.device('doll_set_led',{'on':True})))
        thread.start()
        deadline=time.time()+2
        while time.time()<deadline:
            with self.device.c.lock:
                row=self.device.c.db.execute("SELECT id FROM remote_commands WHERE state='pending'").fetchone()
            if row:break
            time.sleep(.02)
        started=time.monotonic();self.assertEqual(self.device.c.device('doll_get_status',{})['device_id'],'AI-Doll-test')
        self.assertLess(time.monotonic()-started,.5)
        command=self.receive()['commands'][0]
        incoming=packet();incoming['command_results']=[dict(id=command['id'],rpc={'result':{'content':[{'type':'text','text':'{"on":true}'}]}})]
        self.receive(incoming);thread.join(2);self.assertFalse(thread.is_alive());self.assertEqual(answers,[{'on':True}])


class HTTPTests(DirectTests):
    def setUp(self):
        super().setUp()
        self.http=DirectHTTPServer(('127.0.0.1',0),handler_for(self.app))
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.http.server_port)
        self.base='/d/'+self.pair['id']

    def tearDown(self):
        self.app.stop.set();self.http.shutdown();self.http.server_close();self.thread.join();super().tearDown()

    def request(self,path,data=None,token=None,origin=None):
        headers={}
        if token:headers['Authorization']='Bearer '+token
        if origin:headers['Origin']=origin
        if data is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(self.url+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=4) as response:
                return response.status,response.headers,response.read()
        except urllib.error.HTTPError as error:return error.code,error.headers,error.read()

    def test_http_auth_origin_upload_and_remote_ui(self):
        self.assertEqual(self.request('/api/devices')[0],401)
        self.assertEqual(self.request('/api/devices',token=self.app.admin_token,origin='https://evil.example')[0],401)
        self.assertEqual(self.request('/api/device/exchange',packet(1),self.key)[0],200)
        code,_,body=self.request(self.base+'/companion',token=self.app.admin_token)
        self.assertEqual(code,200);self.assertIn(('const deviceBase="'+self.base+'"').encode(),body)
        self.assertNotIn(b'fetch(path,{',body)
        self.assertEqual(self.request(self.base+'/connection',token=self.app.admin_token)[0],200)

    def test_second_listener_is_rejected(self):
        with self.assertRaises(OSError):
            DirectHTTPServer(self.http.server_address, handler_for(self.app))

    def test_browser_connection_cookie_is_httponly(self):
        code,headers,_=self.request('/api/connect',{'token':self.app.admin_token},origin=self.url)
        self.assertEqual(code,200);self.assertIn('HttpOnly',headers['Set-Cookie'])

    def test_real_sse_event_without_polling_tool(self):
        self.receive();session=self.device.c.start('http-chat')
        sub=self.device.c.bridge.subscribe(OWNER,'http-chat',session['id'],'AI-Doll-test')
        self.receive(packet(1))
        req=urllib.request.Request(self.url+self.base+'/bridge/events?subscription_id='+sub['id'],headers={'Authorization':'Bearer '+self.app.admin_token})
        with urllib.request.urlopen(req,timeout=4) as response:
            deadline=time.monotonic()+3;frames=b''
            while time.monotonic()<deadline:
                frames+=response.readline()
                if b'event: interaction' in frames and frames.endswith(b'\n\n'):break
            self.assertIn(b'"source": "simulation"',frames)
            self.assertIn(b'"eventId"',frames)


if __name__=='__main__':unittest.main()
