"""Correlate USB responses without ever replaying a timed-out command."""
import json
import unittest
from unittest.mock import patch

from device_lab import SerialLink


class FakeSerial:
    def __init__(self,responder):
        self.responder=responder;self.sent=b'';self.received=b'';self.requests=[];self.closed=False
    def reset_input_buffer(self):self.received=b''
    def write(self,chunk):
        self.sent+=chunk
        if self.sent.endswith(b'\n'):
            request=json.loads(self.sent);self.requests.append(request);self.sent=b''
            self.received=self.responder(request)
    def flush(self):pass
    @property
    def in_waiting(self):return len(self.received)
    def read(self,count):
        result=self.received[:min(count,17)];self.received=self.received[len(result):];return result
    def close(self):self.closed=True


def frame(data):return json.dumps(data).encode()+b'\n'


class SerialTests(unittest.TestCase):
    def link(self,responder):
        link=SerialLink();serial=FakeSerial(responder);link.connection=serial;return link,serial
    def test_late_response_and_unsolicited_frames_cannot_be_mistaken_for_event_page(self):
        def respond(request):
            return (frame({'serial_request_id':'previous','ok':True})+frame({'event':'boot'})+
                    frame([])+b'invalid-json\n'+frame({'serial_request_id':request['serial_request_id'],'events':[]}))
        link,serial=self.link(respond)
        with patch('device_lab.time.sleep'):
            result=link.exchange({'cmd':'events'})
        self.assertEqual(result,{'events':[]});self.assertTrue(link.require_request_id)
        self.assertEqual(len(serial.requests),1)

    def test_legacy_without_echo_remains_readable(self):
        link,_=self.link(lambda request:frame({'firmware':'legacy'}))
        with patch('device_lab.time.sleep'):
            self.assertEqual(link.exchange({'cmd':'status'})['firmware'],'legacy')
        self.assertFalse(link.require_request_id)

    def test_after_negotiation_untagged_stale_reply_is_ignored(self):
        link,_=self.link(lambda request:frame({'ok':'wrong'})+frame({'ok':True,'serial_request_id':request['serial_request_id']}))
        link.require_request_id=True
        with patch('device_lab.time.sleep'):
            self.assertIs(link.exchange({'cmd':'ack_events'})['ok'],True)

    def test_timed_out_output_is_sent_once_and_connection_closed(self):
        link,serial=self.link(lambda request:frame({'serial_request_id':'wrong','ok':True}))
        request={'cmd':'rpc','request':{'method':'tools/call','params':{'name':'set_vibration'}}}
        with patch('device_lab.time.sleep'),self.assertRaises(TimeoutError):
            link.exchange(request,timeout=.02)
        self.assertEqual(len(serial.requests),1);self.assertTrue(serial.closed)
        self.assertIsNone(link.connection);self.assertNotIn('serial_request_id',request)

    def test_serial_ids_are_unique_and_do_not_change_inner_rpc_id(self):
        link,serial=self.link(lambda request:frame({'serial_request_id':request['serial_request_id'],'id':99}))
        with patch('device_lab.time.sleep'):
            for _ in range(2):self.assertEqual(link.exchange({'cmd':'rpc','request':{'id':99}})['id'],99)
        self.assertNotEqual(serial.requests[0]['serial_request_id'],serial.requests[1]['serial_request_id'])
        self.assertEqual(serial.requests[0]['request']['id'],99)

    def test_read_timeout_reopens_once_but_mutations_are_never_retried(self):
        link=SerialLink()
        with patch.object(link,'_exchange_once',side_effect=[TimeoutError(),{'events':[]}]) as exchange,patch('device_lab.time.sleep'):
            self.assertEqual(link.exchange({'cmd':'events'}),{'events':[]})
            self.assertEqual(exchange.call_count,2)
        for cmd in ('ack_events','sync_time','reboot','rpc'):
            with patch.object(link,'_exchange_once',side_effect=TimeoutError()) as exchange,self.assertRaises(TimeoutError):
                link.exchange({'cmd':cmd})
            self.assertEqual(exchange.call_count,1)

    def test_full_usb_packet_request_gets_short_final_packet(self):
        link,serial=self.link(lambda request:frame({'serial_request_id':request['serial_request_id'],'events':[]}))
        # A 128-byte request otherwise ends on a full CDC packet.
        chunks=[];original=serial.write
        def write(chunk):chunks.append(chunk);original(chunk)
        serial.write=write
        with patch('device_lab.time.sleep'):
            link.exchange({'cmd':'events','boot_id':'x'*32,'after':128})
        self.assertNotEqual(len(chunks[-1]),64)


if __name__=='__main__':unittest.main()
