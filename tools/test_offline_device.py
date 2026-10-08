"""Stop the collector first. Persist/reboot/overflow tests use marked simulation only."""
import datetime
import json
import pathlib
import socket
import sys
import threading
import time

from companion import Companion
from device_lab import WORK, SerialLink
from service_lifecycle import ServiceLease


def run(port='COM3'):
    # Do not race a running collector or acknowledge into a disposable database.
    probe=socket.socket();probe.settimeout(.5)
    try:
        if probe.connect_ex(('127.0.0.1',8768))==0:
            raise RuntimeError('Stop the companion service before this test')
    finally:probe.close()
    with ServiceLease(WORK/'companion.lock'):
        link=SerialLink(port);collector=None;checks=[];original_parts=None;parts_changed=False
        def tool(name,args=None,fail=False):
            reply=link.exchange({'cmd':'rpc','request':{'jsonrpc':'2.0','id':1,'method':'tools/call',
                                       'params':{'name':name,'arguments':args or {}}}})
            if fail:
                assert 'error' in reply or reply.get('result',{}).get('isError'),name
                return
            assert 'error' not in reply and not reply['result'].get('isError'),name
            return json.loads(reply['result']['content'][0]['text'])
        def reboot():
            previous=link.exchange({'cmd':'status'})['boot_id']
            reply=link.exchange({'cmd':'reboot'});assert reply['reboot']
            link.close();time.sleep(2)
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                try:
                    state=link.exchange({'cmd':'status'})
                    if state['boot_id']!=previous:return state
                except (OSError,TimeoutError):link.close()
                time.sleep(.5)
            raise AssertionError('Restarted ESP32 did not return a new boot identity')
        def press(value):return tool('doll_simulate_press',{'channel':channel,'value':value})
        try:
            status=link.exchange({'cmd':'status'})
            assert status['firmware']=='doll-lab-2.5.0' and status['sensor_mode']=='simulation'
            assert not status['physical_outputs_enabled']
            assert link.require_request_id,'New firmware must correlate serial replies'
            assert status['event_storage']['available'],status['event_storage']['error']
            config=tool('get_channel_config');mode=tool('get_operating_mode')
            assert mode['mode']=='manual' and not mode['physical_inputs_enabled']
            channel=next(ch['channel'] for ch in config['channels'] if ch['enabled'] and ch['type']=='pressure')
            collector=Companion(WORK/'interactions.sqlite3',link.exchange,threading.Lock())
            assert collector.active() is None,'Do not interrupt another chat'
            # Drain any existing owner records into the REAL archive before testing capacity.
            for _ in range(4):collector.sync()
            assert tool('get_event_storage_status')['pending_records']==0

            original_parts=tool('get_body_map')
            temporary=json.loads(json.dumps(original_parts))
            for part in temporary['parts']:
                if part['channel']==channel:part['name']='\\'*96
            tool('set_body_map',temporary);parts_changed=True
            boundary_start=press(2000);press(0);collector.sync()
            label_row=collector.db.execute('SELECT payload FROM events WHERE device=? AND boot=? AND seq=?',
                (status['device_id'],boundary_start['boot_id'],boundary_start['event_cursor'])).fetchone()
            assert label_row and json.loads(label_row['payload'])['body_part']=='\\'*96
            assert tool('get_event_storage_status')['write_failures_since_boot']==0
            tool('set_body_map',original_parts);parts_changed=False
            checks.append('Maximum 96-byte escaped body label survives JSON/file integrity/archive round-trip and is restored')

            fresh=reboot();unknown_boot=fresh['boot_id']
            assert not fresh['event_storage']['clock_synced']
            for _ in range(2):press(2100);press(0)
            pending=tool('get_event_storage_status');assert pending['pending_records']==4
            raw=tool('get_touch_events',{})
            unknown_ids={e['event_id'] for e in raw['events']}
            assert len(unknown_ids)==4 and all(e['time_quality']=='unknown' for e in raw['events'])
            newer=reboot();assert newer['boot_id']!=unknown_boot
            collector.last_clock_sync=0
            collector.sync()
            recovered=collector.db.execute('SELECT at,payload FROM events WHERE device=? AND boot=?',
                               (status['device_id'],unknown_boot)).fetchall()
            assert len(recovered)==4 and all(r['at'] is None for r in recovered)
            assert {json.loads(r['payload'])['event_id'] for r in recovered}==unknown_ids
            assert all(json.loads(r['payload'])['delivery_quality']=='offline_replay' for r in recovered)
            assert tool('get_event_storage_status')['pending_records']==0
            checks.append('Four committed unclocked events survive software reboot, recover once with unknown time, then ACK clears flash')

            # Acknowledged entries must stay cleared, while the storage epoch persists.
            epoch=tool('get_event_storage_status')['storage_epoch']
            cleared=reboot()
            assert cleared['event_storage']['pending_records']==0 and cleared['event_storage']['storage_epoch']==epoch
            collector.sync()
            calibrated=tool('get_event_storage_status')
            assert calibrated['clock_synced'] and abs(calibrated['device_time_ms']-time.time()*1000)<2000
            checks.append('Acknowledged files stay cleared after reboot; clock is re-established on the new boot without a 60-second delay')

            boot=cleared['boot_id'];lost_before=calibrated['lost_records'];expected=[]
            print('Creating 270 simulated events without collector polling…',flush=True)
            for pair in range(135):
                for value in (2300,0):
                    state=press(value);expected.append(state['boot_id']+'-'+str(state['event_cursor']))
                if (pair+1)%45==0:print(str((pair+1)*2)+' events committed',flush=True)
            full=tool('get_event_storage_status')
            assert full['pending_records']==256 and full['lost_records']-lost_before==14
            assert full['write_failures_since_boot']==0 and full['corrupt_records']==calibrated['corrupt_records']
            page=link.exchange({'cmd':'events','after':0,'boot_id':boot})
            assert len(page['persistent_events'])==24 and not page['events']
            assert len(page['persistent_events'])+len(page['events'])<=24
            tool('acknowledge_events',dict(storage_cursor=9007199254740991,storage_epoch=epoch,boot_id=boot),fail=True)
            tool('acknowledge_events',dict(storage_cursor=page['storage_cursor'],storage_epoch=epoch,boot_id='bad'),fail=True)
            assert tool('get_event_storage_status')['pending_records']==256
            checks.append('Flash backlog bound is 256 records; 270 events evict exactly 14 oldest; invalid ACK cannot clear records')

            # Reboot again BEFORE polling: overflow survivors must still be durable.
            after_overflow=reboot();assert after_overflow['event_storage']['pending_records']==256
            for _ in range(5):collector.sync()
            rows=collector.db.execute('SELECT payload FROM events WHERE device=? AND boot=?',
                                     (status['device_id'],boot)).fetchall()
            assert len(rows)==256
            assert {json.loads(row['payload'])['event_id'] for row in rows}==set(expected[-256:])
            assert all(json.loads(row['payload'])['time_quality']=='device_clock' for row in rows)
            assert all(json.loads(row['payload'])['delivery_quality']=='offline_replay' for row in rows)
            assert tool('get_event_storage_status')['pending_records']==0
            collector.sync();collector.sync()
            assert collector.db.execute('SELECT COUNT(*) FROM events WHERE device=? AND boot=?',
                                        (status['device_id'],boot)).fetchone()[0]==256
            checks.append('After another software reboot all 256 survivors replay over multiple bounded pages with original clock and no duplicates')
            assert tool('get_channel_config')==config and tool('get_operating_mode')==mode
            assert not collector.active()
            assert not link.exchange({'cmd':'status'})['physical_outputs_enabled']
            checks.append('Original channels/manual mode preserved; no real sensor sampling, motor arming or output replay')
            report=dict(passed=True,bridge='2.8.0',firmware='2.5.0',
                    at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),checks=checks,
                    events_created=276,events_recovered=262,oldest_evicted=14,
                    unknown_archive_cursor=min(collector.db.execute('SELECT id FROM events WHERE device=? AND boot=?',
                        (status['device_id'],unknown_boot)).fetchall(),key=lambda row:row['id'])['id']-1,
                    limits=['Software resets tested, not physical power removal during a filesystem write.',
                            'No forced flash corruption/full-partition fault or physical sensors/motor.',
                            'Tests write explicitly labelled simulation into the existing owner archive.'])
            (WORK/'offline-device-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
        finally:
            if parts_changed and original_parts:tool('set_body_map',original_parts)
            if collector:collector.db.close()
            link.close()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    run(sys.argv[1] if len(sys.argv)>1 else 'COM3')
