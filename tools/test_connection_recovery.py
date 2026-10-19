"""Fast authenticated search, USB recovery, persistence and replay boundaries."""
import json
from pathlib import Path
import tempfile
import threading
import socket
import struct
import ctypes
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import device_discovery as discovery
import device_transport as transport

DEVICE='AI-Doll-'+'a1'*10
TOKEN='fixture-pair-token-0123456789abcdef'
CONFIG={'device_id':DEVICE,'mcp_token':TOKEN,'state':{'ip':'10.0.0.2'}}
FOUND={'device_host':'10.0.0.2','device_id':DEVICE,'firmware':'doll-lab-2.9.0','verified':True}


def response(nonce):
    data=dict(protocol=discovery.PROTOCOL,nonce=nonce,device_id=DEVICE,port=80,firmware='doll-lab-2.9.0')
    data['proof']=discovery.signature(TOKEN,nonce,DEVICE,data['firmware'])
    return json.dumps(data).encode()


class SearchTests(unittest.TestCase):
    def test_native_windows_table_uses_real_prefixes_and_buffer_resize(self):
        raw=struct.pack('=I',2)+b''.join(
            socket.inet_aton(ip)+struct.pack('=I',index)+socket.inet_aton(mask)+struct.pack('=IIHH',1,65535,0,0)
            for index,ip,mask in [(1,'10.1.2.3','255.255.240.0'),(2,'192.168.1.5','255.255.255.0')])
        def fetch(buffer,size,order):
            size._obj.value=len(raw)
            if buffer is None:return 122
            ctypes.memmove(buffer,raw,len(raw));return 0
        self.assertEqual(discovery._windows_ipv4_rows(fetch),[
            {'IPAddress':'10.1.2.3','PrefixLength':20},{'IPAddress':'192.168.1.5','PrefixLength':24}])

    def test_native_windows_table_rejects_truncated_buffers(self):
        def fetch(buffer,size,order):
            size._obj.value=4
            if buffer is None:return 122
            ctypes.memmove(buffer,struct.pack('=I',100),4);return 0
        with self.assertRaises(OSError):discovery._windows_ipv4_rows(fetch)

    def test_cached_host_is_reauthenticated_without_enumerating_adapters(self):
        sock=Mock();nonce='12'*16
        sock.recvfrom.return_value=(response(nonce),('10.0.0.2',28768))
        with patch.object(discovery.socket,'socket',return_value=sock), \
             patch.object(discovery.select,'select',return_value=([sock],[],[])), \
             patch.object(discovery.secrets,'token_hex',return_value=nonce), \
             patch.object(discovery,'cached_interface_bindings') as adapters:
            found=discovery.discover_paired_device(CONFIG)
        adapters.assert_not_called();sock.close.assert_called_once()
        self.assertTrue(found['verified']);self.assertEqual(found['method'],'cached-address')
        wire,address=sock.sendto.call_args.args
        self.assertEqual(address,('10.0.0.2',28768));self.assertNotIn(TOKEN.encode(),wire)

    def test_adapter_cache_expires_and_tolerates_enumeration_failure(self):
        rows=[('10.0.0.3','10.0.0.255')]
        with patch.object(discovery,'_bindings_cache',(0,[])), \
             patch.object(discovery.time,'monotonic',return_value=100) as clock, \
             patch.object(discovery,'interface_bindings',return_value=rows) as enumerate_:
            self.assertEqual(discovery.cached_interface_bindings(),rows)
            self.assertEqual(discovery.cached_interface_bindings(),rows)
            enumerate_.assert_called_once()
            clock.return_value=116;enumerate_.return_value=[]
            self.assertEqual(discovery.cached_interface_bindings(),rows)
            self.assertEqual(enumerate_.call_count,2)

    def test_removed_adapters_invalidate_cache(self):
        sock=Mock();sock.bind.side_effect=OSError('adapter removed')
        with patch.object(discovery,'_bindings_cache',(100,[('10.0.0.3','10.0.0.255')])), \
             patch.object(discovery,'cached_interface_bindings',return_value=[('10.0.0.3','10.0.0.255')]), \
             patch.object(discovery.socket,'socket',return_value=sock):
            self.assertIsNone(discovery.discover_paired_device(dict(CONFIG,state={})))
            self.assertEqual(discovery._bindings_cache,(0,[]))

    def test_actual_udp_retry_recovers_a_dropped_first_packet(self):
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sock.bind(('127.0.0.1',0));sock.settimeout(2);errors=[]
        def respond():
            try:
                sock.recvfrom(4096)  # Deliberately discard the first challenge.
                raw,source=sock.recvfrom(4096)
                sock.sendto(response(json.loads(raw)['nonce']),source)
            except Exception as exc:errors.append(exc)
        worker=threading.Thread(target=respond);worker.start()
        try:
            found=discovery.discover_paired_device(CONFIG,timeout=1,
                bindings=[('127.0.0.1','127.0.0.1')],port=sock.getsockname()[1])
            self.assertIsNotNone(found);self.assertTrue(found['verified'])
        finally:worker.join(3);sock.close()
        self.assertFalse(errors)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg=self.root/'pair.json';self.saved=self.root/'connection.json'
        self.cfg.write_text(json.dumps(CONFIG),encoding='utf-8')
        transport.save_connection(self.saved,'usb',port='COM99')

    def link(self,env=None):
        return transport.create_device_link({} if env is None else env,self.cfg,self.saved)

    def test_failed_saved_usb_recovers_same_device_and_persists_wifi(self):
        link,info=self.link();self.assertIsInstance(link,transport.RecoveringSerialLink)
        with patch.object(transport.SerialLink,'exchange',side_effect=OSError('USB removed')), \
             patch.object(transport,'discover_paired_device',return_value=FOUND), \
             patch.object(transport.WifiLink,'_exchange_once',return_value={'device_id':DEVICE,'ok':True}):
            self.assertTrue(link.exchange({'cmd':'status'})['ok'])
        self.assertEqual(link.host,FOUND['device_host']);self.assertEqual(info['transport'],'wifi')
        self.assertIsNone(info['serial_port'])
        self.assertEqual(json.loads(self.saved.read_text())['device_host'],FOUND['device_host'])
        self.assertNotIn(TOKEN,self.saved.read_text())

    def test_explicit_usb_override_is_not_switched(self):
        link,_=self.link({'DOLL_TRANSPORT':'usb'})
        self.assertNotIsInstance(link,transport.RecoveringSerialLink)

    def test_saved_wifi_is_discovered_before_first_http_request(self):
        transport.save_connection(self.saved,'wifi','10.0.0.99')
        link,info=self.link()
        def request(command):
            self.assertEqual(link.host,FOUND['device_host'])
            return {'device_id':DEVICE}
        with patch.object(link,'discovery',return_value=FOUND) as find, \
             patch.object(link,'_exchange_once',side_effect=request) as http:
            link.exchange({'cmd':'status'});link.exchange({'cmd':'status'})
        find.assert_called_once();self.assertEqual(http.call_count,2)
        self.assertEqual(info['device_host'],FOUND['device_host'])

    def test_no_pairing_means_no_automatic_transport_switch(self):
        self.cfg.write_text('{}')
        link,_=self.link();self.assertNotIsInstance(link,transport.RecoveringSerialLink)

    def test_bad_optional_pairing_does_not_block_usb(self):
        for raw in ['bad-json','[]']:
            self.cfg.write_text(raw)
            link,info=self.link({'DOLL_TRANSPORT':'usb'})
            self.assertEqual(info['transport'],'usb')
            self.assertNotIsInstance(link,transport.RecoveringSerialLink)

    def test_outputs_configuration_and_ack_are_never_replayed(self):
        for cmd in [{'cmd':'ack_events'},{'cmd':'wifi'},
                    {'cmd':'rpc','request':{'method':'tools/call','params':{'name':'set_vibration'}}},
                    {'cmd':'rpc','request':{'method':'tools/call','params':{'name':'set_channel_config'}}}]:
            with self.subTest(cmd=cmd):
                link,_=self.link()
                with patch.object(transport.SerialLink,'exchange',side_effect=OSError('lost')) as call, \
                     patch.object(transport,'discover_paired_device') as find:
                    with self.assertRaises(OSError):link.exchange(cmd)
                call.assert_called_once();find.assert_not_called()
                self.assertEqual(json.loads(self.saved.read_text())['transport'],'usb')

    def test_wrong_http_identity_does_not_switch_or_save(self):
        link,info=self.link();before=self.saved.read_bytes()
        with patch.object(transport.SerialLink,'exchange',side_effect=OSError('lost')), \
             patch.object(transport,'discover_paired_device',return_value=FOUND), \
             patch.object(transport.WifiLink,'_exchange_once',return_value={'device_id':'other'}):
            with self.assertRaises(OSError):link.exchange({'cmd':'status'})
        self.assertIsNone(link.host);self.assertEqual(self.saved.read_bytes(),before)
        self.assertEqual(info['transport'],'usb')

    def test_save_failure_preserves_usb_and_existing_pairing(self):
        link,info=self.link();before=self.saved.read_bytes();pair=self.cfg.read_bytes()
        with patch.object(transport.SerialLink,'exchange',side_effect=OSError('lost')), \
             patch.object(transport,'discover_paired_device',return_value=FOUND), \
             patch.object(transport.WifiLink,'_exchange_once',return_value={'device_id':DEVICE}), \
             patch.object(transport,'save_connection',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):link.exchange({'cmd':'status'})
        self.assertIsNone(link.host);self.assertEqual(info['transport'],'usb')
        self.assertEqual(self.saved.read_bytes(),before);self.assertEqual(self.cfg.read_bytes(),pair)

    def test_offline_backoff_limits_serial_and_discovery_work(self):
        link,_=self.link()
        with patch.object(transport.SerialLink,'exchange',side_effect=OSError('offline')) as call, \
             patch.object(transport,'discover_paired_device',return_value=None) as find, \
             patch.object(transport.time,'monotonic',return_value=100) as clock:
            for _ in range(3):
                with self.assertRaises((OSError,transport.DeviceConnectionError)):link.exchange({'cmd':'status'})
            self.assertEqual(call.call_count,1);self.assertEqual(find.call_count,1)
            clock.return_value=103
            with self.assertRaises(OSError):link.exchange({'cmd':'status'})
            self.assertEqual(link.retry_after,107)

    def test_runtime_metadata_follows_transport_recovery(self):
        import device_setup_server as server
        connection={'transport':'usb'};companion=SimpleNamespace(runtime_info={'transport':'usb'})
        def recover(command):connection['transport']='wifi';return {'ok':True}
        with patch.object(server,'CONNECTION',connection),patch.object(server,'COMPANION',companion), \
             patch.object(server,'DEVICE_LINK',SimpleNamespace(exchange=recover)):
            self.assertTrue(server.exchange({'cmd':'status'})['ok'])
        self.assertEqual(companion.runtime_info['transport'],'wifi')
        self.assertEqual(companion.runtime_info['device_endpoint'],'authenticated LAN HTTP MCP')


if __name__=='__main__':unittest.main()
