"""Setup writes are explicit, retryable and limited to local owner operations."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error

from direct_server import DirectServer,DirectHTTPServer,handler_for
from direct_setup import configure_device


class Reply:
    def __init__(self,value):self.raw=json.dumps(value).encode();self.pos=0
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,*args):return self.raw


class DirectSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=DirectServer(self.temp.name,'http://192.168.1.10:8781')
        self.frames=[]
    def tearDown(self):self.app.close();self.temp.cleanup()
    def reply(self,request,**kwargs):
        self.frames.append(request)
        if request.full_url.endswith('/api/setup'):return Reply({'token':'device-fixture-token-000000000000'})
        if request.full_url.endswith('/api/status'):return Reply(dict(device_id='AI-Doll-fixture',firmware='doll-lab-2.8.1',wifi_connected=True))
        return Reply({'ok':True})
    def test_pair_saves_device_and_repeat_reuses_binding(self):
        with patch('direct_setup.urllib.request.build_opener') as make:
            make.return_value.open.side_effect=self.reply
            one=configure_device(self.app,{'host':'192.168.1.50'})
            two=configure_device(self.app,{'host':'192.168.1.50'})
        self.assertEqual(one['id'],two['id'])
        self.assertEqual(len(self.app.list_devices()),1)
        upload=json.loads(self.frames[-1].data)
        self.assertTrue(upload['enabled']);self.assertTrue(upload['local_http'])
        self.assertEqual(upload['root_ca'],'')
        self.assertNotIn('device_token',one)
    def test_invalid_address_never_reads_or_writes_device(self):
        with patch('direct_setup.urllib.request.build_opener') as make:
            for host in ('127.0.0.1','0.0.0.0','8.8.8.8','http://192.168.1.50','file:///secret',''):
                with self.assertRaises(ValueError):configure_device(self.app,{'host':host})
            make.assert_not_called()
        self.assertEqual(len(self.app.list_devices()),0)
    def test_offline_device_does_not_create_binding(self):
        with patch('direct_setup.urllib.request.build_opener') as make:
            make.return_value.open.side_effect=OSError('offline')
            with self.assertRaisesRegex(ValueError,'同一局域网'):configure_device(self.app,{'host':'192.168.1.50'})
        self.assertEqual(len(self.app.list_devices()),0)
    def test_unconfirmed_write_preserves_retry_binding(self):
        def fail_write(request,**kwargs):
            if request.data:raise TimeoutError('lost response')
            return self.reply(request,**kwargs)
        with patch('direct_setup.urllib.request.build_opener') as make:
            make.return_value.open.side_effect=fail_write
            with self.assertRaises(ValueError):configure_device(self.app,{'host':'192.168.1.50'})
            make.return_value.open.side_effect=self.reply
            result=configure_device(self.app,{'host':'192.168.1.50'})
        self.assertEqual(len(self.app.list_devices()),1)
        self.assertEqual(self.app.list_devices()[0]['id'],result['id'])
    def test_cloud_server_does_not_expose_local_pairing(self):
        server=DirectHTTPServer(('127.0.0.1',0),handler_for(self.app))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            request=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/local-pair',data=b'{}',
                headers={'Authorization':'Bearer '+self.app.admin_token,'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
            self.assertEqual(error.exception.code,403)
        finally:server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
