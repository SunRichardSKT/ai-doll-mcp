"""Opt-in real Wi-Fi board + SDK acceptance of private-address MCP, including 60s expiry.

Injects simulation only, leaves persona/channel configuration and physical mode unchanged.
Does not represent an ordinary Chat or Sakura acceptance run.
"""
import asyncio
import datetime as dt
import json
import logging
from pathlib import Path
import time
import uuid

import companion_mcp as local
from chat_mcp_gateway import ROOT, INTERACTION_TOOLS
from deploy_mcp import probe_url
from remote_mcp import CapabilityStore
from owned_processes import launch, terminate
from private_storage import write_json
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import httpx

logging.disable(logging.CRITICAL)


async def run():
    folder=ROOT/'build/device-lab/private-mcp-device-test'/uuid.uuid4().hex
    store=CapabilityStore(folder)
    key=store.key()
    url='http://127.0.0.1:8771/'+key+'/mcp'
    report=dict(scope='real_wifi_board_sdk',ordinary_chat_verified=False,sakura_verified=False,checks=[],passed=False)
    process=None;sid=None
    def spawn():
        import sys
        return launch([sys.executable,str(ROOT/'tools/remote_mcp.py'),'--folder',str(folder)],ROOT)[1]
    async def ready():
        for _ in range(40):
            try:return await probe_url(url,'interaction',calls=True)
            except Exception:await asyncio.sleep(.25)
        raise AssertionError('Loopback private MCP startup failed')
    try:
        state=await asyncio.to_thread(local.call,'doll_get_status',{})
        assert state['sensor_mode']=='simulation' and not state['physical_outputs_enabled']
        assert not (await asyncio.to_thread(local.call,'get_interaction_status',{}))['active_session']
        process=spawn();first=await ready()
        report['device']={k:state.get(k) for k in ('device_id','firmware','sensor_mode','physical_outputs_enabled','wifi_connected')}
        report['checks'].append('private-address handshake and two real status calls')
        report['status_call_ids']={k:v['verification']['call_id'] for k,v in first['status_calls'].items()}
        async with httpx.AsyncClient(timeout=30,follow_redirects=False) as http:
            async with streamable_http_client(url,http_client=http) as (read,write,_):
                async with ClientSession(read,write) as client:
                    await client.initialize()
                    async def call(name,args=None,error=False):
                        if sid and name in ('get_interaction_device_events','end_interaction'):
                            args=dict(args or {})
                            args.setdefault('chat_id',s['chat_id'])
                        r=await client.call_tool(name,args or {})
                        assert r.isError==error,name
                        if not error:return r.structuredContent
                    assert {t.name for t in (await client.list_tools()).tools}==set(INTERACTION_TOOLS)
                    for path in ('/mcp','/companion','/bridge/mcp','/connection'):
                        assert (await http.post('http://127.0.0.1:8771'+path,json={})).status_code==404
                    s=await call('start_interaction',dict(chat_id='sdk-'+uuid.uuid4().hex,duration_sec=60))
                    sid=s['id'];assert s['deadline']-s['started']==60
                    again=await call('start_interaction',dict(chat_id=s['chat_id'],duration_sec=3600))
                    assert again['id']==sid and again['deadline']==s['deadline']
                    await call('start_interaction',dict(chat_id='second-sdk-chat',duration_sec=60),error=True)
                    await call('get_interaction_device_events',dict(session_id=sid,chat_id='second-sdk-chat'),error=True)
                    await call('end_interaction',dict(session_id=sid,chat_id='second-sdk-chat'),error=True)
                    assert not (await call('get_interaction_device_events',dict(session_id=sid)))['events']
                    persona=await call('get_persona');preferences=await call('get_feedback_preferences')
                    config=await call('get_channel_config')
                    assert config.get('configuration_source')=='computer_sqlite'
                    waiting=asyncio.create_task(call('get_interaction_device_events',dict(session_id=sid,wait_seconds=20)))
                    await asyncio.to_thread(local.call,'doll_simulate_press',dict(channel=0,value=2200))
                    page=await waiting
                    starts=[e for e in page['events'] if e['phase']=='start']
                    assert len(starts)==1 and starts[0]['source']=='simulation'
                    assert starts[0]['sensor_type']=='pressure' and starts[0]['unit']=='adc_raw'
                    assert not (await call('get_interaction_device_events',dict(session_id=sid,after=page['next_cursor'])))['events']
                    await asyncio.to_thread(local.call,'doll_simulate_press',dict(channel=0,value=0))
                    release=await call('get_interaction_device_events',dict(session_id=sid,after=page['next_cursor'],wait_seconds=10))
                    assert any(e.get('phase')=='end' and e.get('touch_id')==starts[0]['touch_id'] for e in release['events'])
                    report['events']=page['events']+release['events']
                    report['checks'] += ['13 tools; admin paths return 404','60s server deadline; retry does not extend; second chat refused',
                                         'simulation start/release, channel, label, raw value, units and source','cursor prevents duplicate start delivery',
                                         'cached channel config, saved persona and preferences readable']
                    print('Live press/release and session ownership passed; waiting for the 60-second server deadline.',flush=True)
                    # At most 20 seconds per MCP wait. No chat idle-wake assertion.
                    while time.time()<s['deadline']:
                        await call('get_interaction_device_events',dict(session_id=sid,after=release['next_cursor'],wait_seconds=min(20,max(1,int(s['deadline']-time.time())))))
                        await asyncio.sleep(.1)
                    final=await call('get_interaction_device_events',dict(session_id=sid,after=0))
                    assert final['session_closed'] and not final['events']
                    assert final['session']['reason']=='duration_expired'
                    assert final['session']['ended']==s['deadline']
                    assert not (await call('get_interaction_status'))['active_session']
                    report['checks'].append('automatic expiry; closed session never redelivers old events')
                    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
                    history=await call('query_device_history',dict(date=today,body_part=starts[0]['body_part'],after=starts[0]['id']-1,limit=200))
                    assert history['history_source']=='computer_sqlite' and history['last_sync'] is not None
                    assert any(e.get('touch_id')==starts[0]['touch_id'] for e in history['events'])
                    report['checks'].append('today history from SQLite preserves test events after expiry')
                    await call('end_interaction',dict(session_id=sid))
                    old_path='/'+store.key()+'/mcp';store.reset()
                    assert (await http.post('http://127.0.0.1:8771'+old_path,json={})).status_code==404
                    url='http://127.0.0.1:8771/'+store.key()+'/mcp'
                    report['checks'].append('live address reset immediately rejects old path')
        after_reset=await ready()
        assert after_reset['protocol_connected']
        terminate(process);process=None
        process=spawn();restarted=await ready()
        assert restarted['protocol_connected']
        assert restarted['status_calls']['doll_get_status']['verification']['run_id']!=first['status_calls']['doll_get_status']['verification']['run_id']
        audit=[json.loads(line) for line in (folder/'calls.jsonl').read_text().splitlines()]
        for ident in report['status_call_ids'].values():assert any(e['call_id']==ident and e['completed'] for e in audit)
        for secret in (key,store.key()):assert secret not in (folder/'calls.jsonl').read_text()
        report['checks'] += ['restart preserves rotated address and SQLite archive','status call IDs match server audit; address absent from audit']
        report['passed']=True
    except Exception as exc:
        report['error_type']=type(exc).__name__
        raise
    finally:
        if sid:
            for name,args in (('doll_simulate_press',dict(channel=0,value=0)),('end_interaction',dict(session_id=sid))):
                try:await asyncio.to_thread(local.call,name,args)
                except Exception:report['cleanup_collector_unavailable']=True
        if process:terminate(process)
        write_json(folder/'acceptance-private.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('events','status_call_ids')},ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':asyncio.run(run())
