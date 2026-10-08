"""Wi-Fi SDK + pushed observations; bare-board only, restoring owner preferences."""
import asyncio,datetime,json,pathlib,site,sys,time,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
SDK=ROOT/'.tools/mcp-test-sdk';sys.path.insert(0,str(SDK));site.addsitedir(str(SDK))
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
 private=json.loads((ROOT/'build/device-lab/companion-private.json').read_text(encoding='utf-8'))
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 def api(path,data=None):
  req=urllib.request.Request('http://127.0.0.1:8768'+path,data=None if data is None else json.dumps(data).encode(),
       headers={'Authorization':'Bearer '+private['token'],'Content-Type':'application/json'})
  return json.load(opener.open(req,timeout=15))
 def receive(sub):
  req=urllib.request.Request('http://127.0.0.1:8768/bridge/events?subscription_id='+sub,
       headers={'Authorization':'Bearer '+private['token']})
  with opener.open(req,timeout=12) as response:
   data=[];length=0;deadline=time.monotonic()+12
   while time.monotonic()<deadline:
    line=response.readline().decode();length+=len(line)
    if not line or length>262144:raise AssertionError('No bounded event frame')
    if line.startswith('data:'):data.append(line[5:].strip())
    if line.strip()=='' and data:return json.loads('\n'.join(data))
   raise AssertionError('No event received')
 checks=[]
 async with stdio_client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'tools/companion_mcp.py')])) as (r,w):
  async with ClientSession(r,w) as client:
   await client.initialize();names={t.name for t in (await client.list_tools()).tools}
   assert len(names)==35 and {'summarize_interactions','get_installation_status'}<=names
   async def call(name,args=None):
    result=await client.call_tool(name,args or {});assert not result.isError,(name,result)
    return json.loads(result.content[0].text)
   assert not (await call('get_interaction_status'))['active_session'],'Do not interrupt another chat'
   mode=await call('get_operating_mode');assert mode['mode']=='manual' and not mode['physical_inputs_enabled'] and not mode['physical_outputs_enabled']
   status=await call('get_installation_status',dict(client_kind='stdio'))
   assert status['bridge']=='doll-bridge-2.6.0' and status['runtime']['transport']=='wifi'
   assert status['runtime']['tool_count']==35 and status['device']['firmware']=='doll-lab-2.3.0'
   assert status['client_registration']=='not_inspected' and status['host_event_support']=='not_verified'
   checks.append('35 official SDK tools; runtime/device selfcheck works and does not claim host capability')
   cfg=await call('get_channel_config');ch=next(c['channel'] for c in cfg['channels'] if c['enabled'] and c['type']=='pressure')
   original=await call('get_feedback_preferences');sid=sub=None
   try:
    policy=dict(original['policy'],merge_ms=100,cooldown_ms=0,allow_simulation=True,notify_pressure_patterns=True,
                tap_max_ms=1200,tap_gap_ms=2000,long_press_ms=2000,quiet_hours=dict(original['policy']['quiet_hours'],enabled=False))
    feedback=dict(original['feedback'],preferred_address='测试称呼',avoid_phrases=['测试禁用语'])
    await call('set_feedback_preferences',dict(policy=policy,feedback=feedback))
    sid=(await call('start_interaction',dict(chat_id='observations-v2.6-regression',idle_timeout_sec=60)))['id']
    sub=api('/bridge/subscriptions',dict(target_id='observations-v2.6-regression',session_id=sid,device_id=status['device']['device_id'],ttl_sec=120))['id']
    for _ in range(2):
     await call('doll_simulate_press',dict(channel=ch,value=2200));await asyncio.sleep(.12)
     await call('doll_simulate_press',dict(channel=ch,value=0));await asyncio.sleep(.12)
    await call('doll_simulate_press',dict(channel=ch,value=2300));await asyncio.sleep(2.15)
    await call('doll_simulate_press',dict(channel=ch,value=0))
    raw=await call('summarize_interactions',dict(session_id=sid))
    kinds={o['kind'] for o in raw['summary']['observations']}
    assert {'completed_long_press','repeated_short_presses'}<=kinds
    assert len(raw['events'])==6 and all(e['source']=='simulation' for e in raw['events'])
    checks.append('real ESP32 simulation produces raw six-event history, released long press and completed tap sequence')
    delivered=set()
    for _ in range(8):
     message=await asyncio.to_thread(receive,sub);data=message['event']['data']
     assert data['feedback']['preferred_address']=='测试称呼' and data['feedback']['avoid_phrases']==['测试禁用语']
     delivered.update(o['kind'] for o in data['summary']['observations'])
     api('/bridge/ack',dict(subscription_id=sub,event_id=message['event']['eventId'],lease=message['lease']))
     if {'completed_long_press','repeated_short_presses'}<=delivered:break
    else:raise AssertionError('Patterns missing from live push')
    checks.append('SSE delivers factual summaries and explicit user feedback preferences; ACK succeeds')
    quiet=dict(policy,quiet_hours=dict(enabled=True,start='00:00',end='00:00',timezone='Asia/Shanghai'))
    await call('set_feedback_preferences',dict(policy=quiet,feedback=feedback))
    before=api('/bridge/status')['deliveries'];cursor=raw['next_cursor']
    await call('doll_simulate_press',dict(channel=ch,value=2100));await asyncio.sleep(.15)
    await call('doll_simulate_press',dict(channel=ch,value=0))
    new=await call('get_interaction_device_events',dict(session_id=sid,after=cursor))
    assert len(new['events'])==2 and api('/bridge/status')['quiet_hours']['active']
    assert api('/bridge/status')['deliveries']==before
    await call('set_feedback_preferences',dict(policy=policy,feedback=feedback))
    assert api('/bridge/status')['deliveries']==before
    checks.append('quiet live preference records two more raw events, enqueues no reply and does not replay when disabled')
   finally:
    await call('doll_simulate_press',dict(channel=ch,value=0))
    if sub:api('/bridge/unsubscribe',dict(subscription_id=sub))
    if sid:await call('end_interaction',dict(session_id=sid))
    await call('set_feedback_preferences',original)
   assert (await call('get_feedback_preferences'))==original
   assert (await call('get_channel_config'))==cfg and (await call('get_operating_mode'))==mode
   checks.append('original preferences and channels preserved; session/subscription ended; physical inputs/outputs remain off')
 report=dict(passed=True,bridge='2.6.0',firmware='2.3.0',at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),checks=checks,
             not_tested=['Physical sensor pressure','User model generation or official chat event support'])
 (ROOT/'build/device-lab/feedback-features-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');asyncio.run(main())
