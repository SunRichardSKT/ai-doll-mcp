"""Pairing export identity and the actual served offline QR resource."""
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from direct_server import DirectServer, handler_for
from test_direct_server import packet


class PairingExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='AI Doll pairing ')
        self.app = DirectServer(self.temp.name, public_url='https://doll.example.net')
        self.app.mcp_info = dict(enabled=True, profile='interaction', port=8782)
        self.pair = self.app.pair('我的娃娃')

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def test_export_tracks_installation_and_pairing_without_admin_or_upload_credentials(self):
        exported = self.app.operit_connection(self.pair['id'])
        self.assertEqual(exported['schema'], 1)
        self.assertEqual(exported['server_instance_id'], self.app.server_instance_id)
        self.assertEqual(exported['pairing_id'], self.pair['id'])
        self.assertIsNone(exported['expected_device_id'])
        wire = json.dumps(exported)
        self.assertNotIn(self.app.admin_token, wire)
        self.assertNotIn(self.pair['device_token'], wire)
        self.app.receive(self.pair['device_token'], packet())
        self.assertEqual(self.app.operit_connection(self.pair['id'])['expected_device_id'], packet()['batch']['device_id'])

    def test_instance_survives_restart_url_change_and_admin_rotation(self):
        ident = self.app.server_instance_id
        self.app.close()
        config = Path(self.temp.name)/'server-private.json'
        value = json.loads(config.read_text(encoding='utf-8'))
        value['admin_token'] = 'replacement_admin_for_isolated_test'
        config.write_text(json.dumps(value), encoding='utf-8')
        self.app = DirectServer(self.temp.name, public_url='https://changed.example.net')
        self.app.mcp_info = dict(enabled=True, profile='interaction', port=8782)
        exported = self.app.operit_connection(self.pair['id'])
        self.assertEqual(exported['server_instance_id'], ident)
        self.assertEqual(exported['pairing_id'], self.pair['id'])
        self.assertTrue(exported['mcp_url'].startswith('https://changed.example.net/'))

    def test_http_export_requires_management_access_but_script_is_public_and_offline(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.app))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = 'http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(base+'/pairing.js', timeout=3) as response:
                script = response.read()
                self.assertIn(b'QrCode', script)
                self.assertIn(b'AIDollPairing', script)
                self.assertNotIn(b'cdn.jsdelivr', script)
            path = base+'/d/'+self.pair['id']+'/operit-connection.json'
            with self.assertRaises(urllib.error.HTTPError) as failure:
                urllib.request.urlopen(path, timeout=3)
            self.assertEqual(failure.exception.code, 401)
            failure.exception.close()
            request = urllib.request.Request(path, headers={'Authorization':'Bearer '+self.app.admin_token})
            with urllib.request.urlopen(request, timeout=3) as response:
                exported = json.load(response)
            self.assertEqual(exported['server_instance_id'], self.app.server_instance_id)
            revoke = urllib.request.Request(base+'/api/revoke', method='POST',
                data=json.dumps({'id':self.pair['id']}).encode(),
                headers={'Authorization':'Bearer '+self.app.admin_token, 'Content-Type':'application/json'})
            with urllib.request.urlopen(revoke, timeout=3) as response:
                self.assertEqual(response.status, 200)
            with self.assertRaises(urllib.error.HTTPError) as revoked:
                urllib.request.urlopen(request, timeout=3)
            revoked.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(3)


if __name__ == '__main__':
    unittest.main()
