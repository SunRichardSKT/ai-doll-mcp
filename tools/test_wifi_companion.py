"""Real Wi-Fi collector test while the available USB serial port is held idle."""
import json
import pathlib
import re
import sys
import time
import urllib.request
from device_lab import CONFIG, WORK
from device_transport import WifiLink
import serial

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BASE = 'http://127.0.0.1:8768'


def main():
    page = OPENER.open(BASE+'/companion',timeout=5).read().decode()
    csrf = re.search(r"const csrf='([^']+)'",page).group(1)
    def api(path, data=None):
        request = urllib.request.Request(BASE+path, headers={'X-CSRF-Token':csrf,
                         'Content-Type':'application/json'},
                         data=None if data is None else json.dumps(data).encode())
        with OPENER.open(request,timeout=10) as response:
            return json.load(response)
    def tool(name, arguments=None):
        return api('/companion/tool',{'name':name,'arguments':arguments or {}})
    def wait_for(callback):
        until = time.monotonic()+10
        while time.monotonic()<until:
            value = callback()
            if value:
                return value
            time.sleep(.25)
        raise AssertionError('Wireless event did not reach collector within 10 seconds')

    connection = api('/connection')
    assert connection['transport']=='wifi' and connection['serial_port'] is None
    assert not tool('get_interaction_status')['active_session'], 'Do not interrupt a user interaction'
    status = tool('doll_get_status')
    assert status['wifi_connected'] and status['sensor_mode']=='simulation'
    assert not status['physical_outputs_enabled']
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    device = WifiLink(connection['device_host'],config)
    channels = tool('get_channel_config')['channels']
    channel = next(ch['channel'] for ch in channels if ch['type']=='pressure' and ch['enabled'])
    port = None
    session = None
    checks = ['Wi-Fi selected; USB absent from collector connection',
              'Live status, full channel configuration and simulation mode over Wi-Fi']
    try:
        # Hold the CDC port WITHOUT sending bytes; the collector cannot use USB during this test.
        from serial.tools import list_ports
        serial_port = config.get('port','COM3')
        if any(p.device==serial_port for p in list_ports.comports()):
            port = serial.Serial(port=None,baudrate=115200,timeout=.1)
            port.dtr=False
            port.rts=False
            port.port=serial_port
            port.open()
            checks.append('USB serial held exclusively idle while Wi-Fi test runs')
        else:
            checks.append('USB serial not present; Wi-Fi works without a computer USB connection')
        baseline = tool('query_touch_history',{'limit':200})
        while baseline['has_more']:
            baseline = tool('query_touch_history',{'after':baseline['next_cursor'],'limit':200})
        after = baseline['next_cursor']
        def press(value):
            return device.exchange({'cmd':'rpc','request':{'jsonrpc':'2.0','id':42,
                        'method':'tools/call','params':{'name':'doll_simulate_press',
                                                       'arguments':{'channel':channel,'value':value}}}})
        press(1750)
        time.sleep(.2)
        press(0)
        ordinary = wait_for(lambda: next((t for t in tool('query_touch_history',{'after':after})['touches']
                              if t['channel']==channel and t['peak_raw']==1750 and t['ended']),None))
        assert ordinary['source']=='simulation' and ordinary['session_id'] is None
        checks.append('Independent LAN sender -> Wi-Fi collector -> durable ordinary history')
        session = tool('start_interaction',{'chat_id':'wifi-transport-v2.4-live','idle_timeout_sec':60})['id']
        press(1850)
        time.sleep(.2)
        press(0)
        interactive = wait_for(lambda: next((t for t in tool('get_interaction_events',{'session_id':session})['touches']
                                  if t['peak_raw']==1850 and t['ended']),None))
        assert interactive['source']=='simulation' and interactive['session_id']==session
        assert len(tool('get_interaction_events',{'session_id':session})['touches'])==1
        assert not tool('get_interaction_events',{'session_id':session,'after':interactive['id']})['touches']
        checks.append('Current interaction ownership, pressure duration, deduplication and cursor over Wi-Fi')
        mixed = tool('get_interaction_device_events',{'session_id':session})
        assert any(e['sensor_type']=='pressure' and e['source']=='simulation' for e in mixed['events'])
        checks.append('Full mixed-event history tools retained')
        tool('end_interaction',{'session_id':session})
        session = None
        assert not tool('get_interaction_status')['active_session']
        assert not tool('get_interaction_status')['collector_error']
        checks.append('Session ended; healthy ordinary collection restored')
        report = {'passed':True,'bridge':'2.12.2','firmware':status['firmware'],
                  'transport':'wifi','device_id':status['device_id'],
                  'usb_serial_held_idle':port is not None,'checks':checks,
                  'not_tested':['Physical FSR/NTC/motor','Battery-powered hardware unless USB serial was absent']}
        (WORK/'wifi-companion-live-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
    finally:
        if session:
            tool('end_interaction',{'session_id':session})
        if port is not None:
            port.close()
        device.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
