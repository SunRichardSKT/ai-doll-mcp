"""Protect physical flashing from unintended web requests and duplicate clicks."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import urllib.error
import urllib.request

import flash_server as ui
import flash_esp32


class FlashPageTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.patch=patch.object(flash_esp32,'ROOT',self.root);self.patch.start()
        self.page=ui.Flasher()
        self.server=ui.ExclusiveLoopbackServer(('127.0.0.1',0),ui.make_handler(self.page))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2)
        self.patch.stop();self.folder.cleanup()

    def request(self, data, headers=None):
        request=urllib.request.Request(self.url+'/api/start',data=json.dumps(data).encode(),
            headers=headers or {'X-CSRF-Token':self.page.csrf,'Content-Type':'application/json'})
        try:
            with self.opener.open(request,timeout=2) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as error:
            with error:return error.code,json.loads(error.read())

    def test_cross_origin_and_missing_token_never_write(self):
        with patch.object(ui,'flash') as run:
            self.assertEqual(self.request({}, {'Content-Type':'application/json'})[0],403)
            self.assertEqual(self.request({}, {'X-CSRF-Token':self.page.csrf,'Origin':'https://external.example'})[0],403)
            run.assert_not_called()

    def test_factory_requires_explicit_confirmation(self):
        with patch.object(ui,'flash') as run:
            code,reply=self.request({'factory':True})
            self.assertEqual(code,400);self.assertIn('确认',reply['error']);run.assert_not_called()

    def test_request_types_are_strict(self):
        for data in ([], {'factory':'false'},{'port':123},{'images':'untrusted.bin'}):
            self.assertEqual(self.request(data)[0],400)

    def test_repeated_click_does_not_start_a_second_write(self):
        hold=threading.Event();done=threading.Event()
        def fake(args,job):
            hold.wait(3);done.set()
        with patch.object(ui,'flash',side_effect=fake) as run:
            self.assertEqual(self.request({'port':'COM4','factory':False})[0],202)
            self.assertEqual(self.request({'port':'COM4','factory':False})[0],409)
            hold.set();self.assertTrue(done.wait(2));self.assertEqual(run.call_count,1)


if __name__=='__main__':unittest.main()
