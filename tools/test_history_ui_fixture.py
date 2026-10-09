"""Disposable HTTP archive for browser tests; never opens owner history or USB."""
import pathlib
import sys
import tempfile
import threading
import time
from companion import Companion
from service_lifecycle import ExclusiveLoopbackServer
import device_setup_server as web

ROOT=pathlib.Path(__file__).resolve().parents[1]


def main():
    folder=(ROOT/'build/test-history-ui').resolve();folder.mkdir(parents=True,exist_ok=True)
    assert folder.is_relative_to(ROOT.resolve())
    with tempfile.TemporaryDirectory(dir=folder) as temp:
        web.COMPANION=Companion(pathlib.Path(temp)/'fixture.sqlite3',None,threading.Lock())
        web.COMPANION_TOKEN='isolated-browser-fixture-token';web.CONNECTION=dict(transport='usb',serial_port='TEST-FIXTURE')
        now=time.time()
        with web.COMPANION.db:
            for seq in range(1,608):
                kind='pressure' if seq<=2 else 'temperature'
                payload=dict(seq=seq,uptime_ms=seq*100,phase='start' if seq==1 else 'end' if seq==2 else 'sample',
                    channel=0,body_part='TEST-HISTORY-PRESSURE' if seq<=2 else '=fixture_formula' if seq==3 else 'TEST-HISTORY-TEMPERATURE',
                    source='simulation',sensor_type=kind,direction='input',value=2000 if kind=='pressure' else 25,
                    unit='adc_raw' if kind=='pressure' else 'degC',peak_raw=2000,duration_ms=1000,
                    time_quality='unknown' if seq==607 else 'device_clock',received_at=now)
                if kind=='pressure':payload['touch_id']='test-fixture-touch'
                web.COMPANION.archive_event('TEST-ONLY','test-boot',payload,None if seq==607 else now-10,now)
        class Handler(web.Handler):
            def allowed(self):
                authority='127.0.0.1:'+str(self.server.server_port)
                return self.headers.get('Host')==authority and self.headers.get('Origin','') in ('','http://'+authority)
        server=ExclusiveLoopbackServer(('127.0.0.1',0),Handler)
        print('http://127.0.0.1:'+str(server.server_port),flush=True)
        try:server.serve_forever()
        finally:server.server_close();web.COMPANION.db.close()


if __name__=='__main__':main()
