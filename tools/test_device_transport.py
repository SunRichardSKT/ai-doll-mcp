"""Network transport behavior, reconnect archives and strict USB independence."""
import json
import pathlib
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from companion import Companion
from device_transport import WifiLink, DeviceConnectionError, create_device_link, lan_address

TOKEN = 'test-device-token-0123456789abcdef'


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.mode = 'ok'
        self.frames = []
        self.boot = 'boot-one'
        self.device = 'test-device'
        self.events = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.frames.append((self.path, req, dict(self.headers)))
                if owner.mode == 'redirect':
                    self.send_response(302)
                    self.send_header('Location', '/stolen-token')
                    self.end_headers()
                    return
                if owner.mode == 'offline' or self.headers.get('Authorization') != 'Bearer '+TOKEN:
                    self.send_response(503 if owner.mode == 'offline' else 401)
                    self.end_headers()
                    return
                if req['method'].startswith('notifications/'):
                    self.send_response(202)
                    self.end_headers()
                    return
                result = {}
                if req['method'] == 'initialize':
                    result = {'protocolVersion':'2025-11-25','capabilities':{},'serverInfo':{'name':'fixture','version':'1'}}
                elif req['method'] == 'tools/call':
                    args = req['params']['arguments']
                    if req['params']['name'] == 'doll_get_status':
                        data = {'device_id':owner.device, 'firmware':'doll-lab-2.2.0'}
                    elif req['params']['name'] == 'get_touch_events':
                        after = args.get('after', 0) if args.get('boot_id') == owner.boot else 0
                        selected = [e for e in owner.events if e['seq'] > after]
                        data = {'device_id':owner.device,'boot_id':owner.boot,'uptime_ms':10000,
                                'next_cursor':max([after]+[e['seq'] for e in selected]),
                                'latest_seq':max([0]+[e['seq'] for e in owner.events]),
                                'oldest_seq':1,'gap':False,'events':selected}
                    else:
                        data = {'ok':True}
                    result = {'content':[{'type':'text','text':json.dumps(data)}],'isError':False}
                reply = {'jsonrpc':'2.0','id':req['id'] + (1 if owner.mode=='bad-id' else 0),'result':result}
                wire = b'invalid-json' if owner.mode == 'bad-json' else json.dumps(reply).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(wire)))
                self.end_headers()
                self.wfile.write(wire)

        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.host = '127.0.0.1:'+str(self.server.server_port)
        self.config = {'mcp_token':TOKEN,'device_id':self.device}
        self.link = WifiLink(self.host,self.config,timeout=.5,discovery=lambda config:None)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def test_status_handshake_token_and_no_proxy(self):
        self.assertEqual(self.link.exchange({'cmd':'status'})['device_id'],self.device)
        self.assertEqual([f[1]['method'] for f in self.frames],
                         ['initialize','notifications/initialized','tools/call'])
        for _, _, headers in self.frames:
            self.assertEqual(headers['Authorization'],'Bearer '+TOKEN)
            self.assertEqual(headers['Mcp-Protocol-Version'],'2025-11-25')
        self.link.exchange({'cmd':'status'})
        self.assertEqual(sum(f[1]['method']=='initialize' for f in self.frames),1)

    def test_events_and_rpc_keep_collector_shape(self):
        batch = self.link.exchange({'cmd':'events','boot_id':self.boot,'after':7})
        self.assertEqual(batch['next_cursor'],7)
        self.assertEqual(self.frames[-1][1]['params']['name'],'get_touch_events')
        result = self.link.exchange({'cmd':'rpc','request':{'jsonrpc':'2.0','id':99,
                                     'method':'tools/call','params':{'name':'doll_set_led','arguments':{'on':True}}}})
        self.assertEqual(result['id'],99)
        self.assertFalse(result['result']['isError'])

    def test_reconnect_and_archive_dedup(self):
        event = {'seq':1,'phase':'start','uptime_ms':1000,'touch_id':'one-1','channel':0,
                 'body_part':'head','source':'simulation','peak_raw':3200,'duration_ms':0}
        self.events.append(event)
        c = Companion(self.root/'history.sqlite3',self.link.exchange,threading.Lock())
        try:
            c.sync()
            self.assertEqual(len(c.history()['touches']),1)
            self.mode = 'offline'
            with self.assertRaises(DeviceConnectionError):
                c.sync()
            self.assertEqual(len(c.history()['touches']),1)
            self.mode = 'ok'
            self.events.append(dict(event,seq=2,phase='end',uptime_ms=2000,duration_ms=1000))
            c.sync()
            c.sync()
            self.assertEqual(len(c.history()['touches']),1)
            self.assertEqual(c.history()['touches'][0]['duration_ms'],1000)
            self.assertEqual(sum(f[1]['method']=='initialize' for f in self.frames),2)
        finally:
            c.db.close()

    def test_lost_command_is_not_replayed(self):
        self.link.exchange({'cmd':'status'})
        self.mode = 'offline'
        request = {'cmd':'rpc','request':{'id':5,'method':'tools/call',
                   'params':{'name':'set_vibration','arguments':{'channel':10,'intensity':30}}}}
        with self.assertRaises(DeviceConnectionError):
            self.link.exchange(request)
        self.assertEqual(sum(f[1].get('params',{}).get('name')=='set_vibration' for f in self.frames),1)

    def test_error_bodies_and_tokens_are_not_exposed(self):
        link = WifiLink(self.host,{'mcp_token':'wrong-private-token-0123456789'})
        with self.assertRaises(DeviceConnectionError) as error:
            link.exchange({'cmd':'status'})
        self.assertIn('401',str(error.exception))
        self.assertNotIn('wrong-private',str(error.exception))

    def test_no_redirect_or_invalid_reply(self):
        for mode in ('redirect','bad-id','bad-json'):
            with self.subTest(mode=mode):
                self.mode = mode
                with self.assertRaises(DeviceConnectionError):
                    self.link.exchange({'cmd':'status'})
        self.assertTrue(all(f[0]=='/mcp' for f in self.frames))

    def test_paired_device_identity(self):
        self.device = 'other-device'
        with self.assertRaises(DeviceConnectionError):
            self.link.exchange({'cmd':'events'})

    def test_host_and_token_validation(self):
        for host in ('8.8.8.8','0.0.0.0','224.0.0.1','example.com','10.0.0.1/other',
                     'user:password@10.0.0.1','10.0.0.1?token=x','http://10.0.0.1','10.0.0.1\n'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                lan_address(host)
        self.assertEqual(lan_address('192.168.1.10'),'192.168.1.10')
        with self.assertRaises(ValueError):
            WifiLink(self.host,{'mcp_token':'invalid\nheader-0123456789'})

    def test_wifi_selection_saved_and_never_opens_serial(self):
        config = self.root/'device-private.json'
        config.write_text(json.dumps(self.config),encoding='utf-8')
        saved = self.root/'connection-private.json'
        with patch('device_transport.SerialLink',side_effect=AssertionError('USB must not be selected')):
            link, info = create_device_link({'DOLL_DEVICE_HOST':self.host},config,saved)
            self.assertIsInstance(link,WifiLink)
            self.assertEqual(info['transport'],'wifi')
            self.assertIsNone(info['serial_port'])
            self.assertNotIn(TOKEN,json.dumps(info))
            restored, info = create_device_link({},config,saved)
            self.assertIsInstance(restored,WifiLink)
            restored.exchange({'cmd':'status'})

    def test_wifi_configuration_never_falls_back_to_usb(self):
        with patch('device_transport.SerialLink',side_effect=AssertionError('No fallback')):
            with self.assertRaises(ValueError):
                create_device_link({'DOLL_TRANSPORT':'wifi','DOLL_DEVICE_HOST':self.host},
                                   self.root/'missing.json',self.root/'connection-private.json')

    def test_usb_remains_selectable(self):
        saved = self.root/'connection-private.json'
        link, info = create_device_link({'DOLL_TRANSPORT':'usb','DOLL_SERIAL_PORT':'COM99'},
                                       self.root/'missing.json',saved)
        self.assertEqual(link.port,'COM99')
        self.assertIsNone(link.connection)
        self.assertEqual(info['transport'],'usb')


if __name__ == '__main__':
    unittest.main()
