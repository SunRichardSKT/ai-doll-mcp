"""Real-device mixed-channel regression using official MCP clients. Restores config/persona."""
import asyncio, datetime, json, os, pathlib, site, sys, urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
SDK=ROOT/'.tools/mcp-test-sdk';sys.path.insert(0,str(SDK));site.addsitedir(str(SDK))
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
import httpx

async def main():
 checks=[];work=ROOT/'build/device-lab'
 params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'tools/companion_mcp.py')])
 async with stdio_client(params) as (read,write):
  async with ClientSession(read,write,read_timeout_seconds=datetime.timedelta(seconds=60)) as session:
   await session.initialize();listed=await session.list_tools();assert len(listed.tools)==37
   async def call(name,args=None,error=False):
    r=await session.call_tool(name,args or {})
    if error:assert r.isError,(name,r);return
    assert not r.isError,(name,r);return json.loads(r.content[0].text)
   status=await call('doll_get_status');assert status['firmware']=='doll-lab-2.5.0'
   assert not (await call('get_interaction_status'))['active_session'],'Do not interrupt a user interaction'
   assert not (await call('get_sensor_config'))['enabled'],'Disable assembled input sampling before simulation tests'
   caps=await call('get_channel_capabilities');assert caps['max_channels']==16 and caps['mux_ports']==8
   assert {t['type'] for t in caps['types']}=={'pressure','temperature','vibration'}
   assert not caps['physical_outputs_enabled'];checks.append('37 STDIO tools, typed capabilities and safe boot defaults')
   original=await call('get_channel_config');sid=None
   try:
    mixed=[dict(c) for c in original['channels']]
    assert not any(c['channel']>=8 for c in mixed),'This regression needs free logical IDs 8..15; do not overwrite user expansions'
    mixed += [dict(channel=8,name='测试温度探头',type='temperature',driver='simulation',options={}),
              dict(channel=9,name='测试震动输出',type='vibration',driver='simulation',options={})]
    saved=await call('set_channel_config',{'channels':mixed});assert len(saved['channels'])==10
    checks.append('pressure channels preserved; temperature and vibration presets added')
    await call('set_channel_config',{'channels':[dict(channel=0,name='bad',type='vibration',driver='mux_adc',mux_port=0)]},error=True)
    await call('set_channel_config',{'channels':[dict(channel=0,name='bad',type='not_installed',driver='simulation')]},error=True)
    await call('set_channel_config',{'channels':[dict(channel=0,name='bad',type='vibration',driver='gpio_pwm',gpio=8)]},error=True)
    dup=[dict(c) for c in saved['channels']];dup[1]['mux_port']=dup[0].get('mux_port',0)
    await call('set_channel_config',{'channels':dup},error=True)
    assert (await call('get_channel_config'))['channels']==saved['channels']
    checks.append('incompatible direction/driver, reserved GPIO and duplicate physical port rejected atomically')
    await call('simulate_channel_input',{'channel':8,'value':32.5,'unit':'degC'})
    values=(await call('read_channel_values'))['values'];temp=next(v for v in values if v['channel']==8)
    assert temp['value']==32.5 and temp['source']=='simulation' and temp['unit']=='degC'
    await call('simulate_channel_input',{'channel':8,'value':1336,'unit':'millivolt'})
    temp=next(v for v in (await call('read_channel_values'))['values'] if v['channel']==8)
    assert abs(temp['value']-25)<0.1,temp
    await call('simulate_channel_input',{'channel':8,'value':0,'unit':'millivolt'})
    temp=next(v for v in (await call('read_channel_values'))['values'] if v['channel']==8)
    assert temp['value'] is None and temp['quality']=='adc_out_of_range'
    await call('simulate_channel_input',{'channel':8,'value':126,'unit':'degC'},error=True)
    await call('simulate_channel_input',{'channel':9,'value':100},error=True)
    checks.append('temperature unit/source, 25C NTC conversion, invalid ADC quality/null and input/output separation')
    sid=(await call('start_interaction',{'chat_id':'typed-channel-regression'}))['id']
    await call('simulate_channel_input',{'channel':8,'value':31,'unit':'degC'})
    await call('set_vibration',{'channel':9,'intensity':40,'duration_ms':200})
    parts=(await call('get_body_map'))['parts'];parts[9]['name']='测试震动改名后';await call('set_body_map',{'parts':parts})
    await asyncio.sleep(.7)
    events=(await call('get_interaction_device_events',{'session_id':sid}))
    assert {e['sensor_type'] for e in events['events']}=={'temperature','vibration'}
    vib=[e for e in events['events'] if e['sensor_type']=='vibration'];assert [e['phase'] for e in vib]==['output','stop']
    assert all(e['body_part']=='测试震动输出' and e['direction']=='output' and e['source']=='simulation' for e in vib)
    assert not (await call('get_interaction_events',{'session_id':sid}))['touches']
    assert not (await call('get_interaction_device_events',{'session_id':sid,'after':events['next_cursor']}))['events']
    page=await call('get_interaction_device_events',{'session_id':sid,'limit':1});assert page['has_more']
    await call('end_interaction',{'session_id':sid});sid=None
    checks.append('mixed interaction history, independent cursor/pagination, output label snapshot and simulated auto-stop')
    physical=[dict(c) for c in saved['channels']];physical[-1].update(driver='gpio_pwm',gpio=10)
    await call('set_channel_config',{'channels':physical})
    await call('set_vibration',{'channel':9,'intensity':50,'duration_ms':200},error=True)
    await call('set_output_enabled',{'enabled':True,'external_driver_confirmed':False},error=True)
    assert not (await call('get_channel_capabilities'))['physical_outputs_enabled']
    await call('set_vibration',{'channel':9,'intensity':0,'duration_ms':1})
    checks.append('physical motor driver remains unarmed; nonzero output denied without confirmation')
    # A full 16-channel blob exceeds the NVS string limit; long Chinese labels exercise USB and NVS boundaries.
    full=[dict(channel=i,name='温'*30+str(i),type='temperature',driver='simulation',options={}) for i in range(16)]
    sixteen=await call('set_channel_config',{'channels':full});assert len(sixteen['channels'])==16
    cfg=json.loads((work/'companion-private.json').read_text(encoding='utf-8'))
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    raw=opener.open('http://127.0.0.1:8768/').read().decode()
    import re
    csrf=re.search("const csrf='([^']+)'",raw).group(1)
    request=urllib.request.Request('http://127.0.0.1:8768/rpc',data=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'doll_get_status','arguments':{}}}).encode(),headers={'X-CSRF-Token':csrf,'Content-Type':'application/json'})
    assert opener.open(request).status==200
    request=urllib.request.Request('http://127.0.0.1:8768/companion/tool',data=json.dumps({'name':'get_channel_config','arguments':{}}).encode(),headers={'Authorization':'Bearer '+cfg['token'],'Content-Type':'application/json'})
    assert len(json.load(opener.open(request))['channels'])==16
    # Software reboot through the USB service, using the existing request channel; no serial-port race.
    # Reboot uses the host endpoint added for local authenticated maintenance.
    req=urllib.request.Request('http://127.0.0.1:8768/reboot',data=b'{}',headers={'X-CSRF-Token':csrf,'Content-Type':'application/json'})
    connection=json.loads((work/'connection-private.json').read_text(encoding='utf-8'))
    if connection['transport']=='wifi':
     port=os.environ.get('DOLL_TEST_REBOOT_PORT')
     if not port:raise AssertionError('Wi-Fi regression needs explicit DOLL_TEST_REBOOT_PORT for the maintenance reboot')
     from device_lab import SerialLink
     link=SerialLink(port)
     previous_boot=status['boot_id']
     try:
      try:assert link.exchange({'cmd':'reboot'})['ok']
      except TimeoutError:pass  # Do not resend: verify the new boot over Wi-Fi below.
     finally:link.close()
    else:assert json.load(opener.open(req))['ok']
    for _ in range(30):
     await asyncio.sleep(.5)
     try:
      restored=await call('get_channel_config')
      current=await call('doll_get_status')
      if restored['channels']==sixteen['channels'] and (connection['transport']!='wifi' or current['boot_id']!=previous_boot):break
     except AssertionError:continue
    else:raise AssertionError('Expanded NVS config did not restore')
    assert not (await call('get_channel_capabilities'))['physical_inputs_enabled']
    assert not (await call('get_channel_capabilities'))['physical_outputs_enabled']
    checks.append('16 long-label channels persist across reboot with inputs/outputs disabled')
    # Device HTTP MCP retains the same capability contract as local stdio.
    status=await call('doll_get_status');assert status['wifi_connected']
    private=json.loads((work/'device-private.json').read_text(encoding='utf-8'))
    async with httpx.AsyncClient(headers={'Authorization':'Bearer '+private['mcp_token']},trust_env=False,timeout=30) as client:
     async with streamable_http_client('http://'+status['ip']+'/mcp',http_client=client) as (r,w,_):
      async with ClientSession(r,w) as http:
       await http.initialize();tools=await http.list_tools();assert len(tools.tools)==25
       response=await http.call_tool('get_channel_capabilities');assert not response.isError
       assert json.loads(response.content[0].text)['max_channels']==16
    checks.append('25 device HTTP MCP tools and matching typed capability discovery over Wi-Fi')
   finally:
    if sid:await call('end_interaction',{'session_id':sid})
    await call('set_output_enabled',{'enabled':False})
    await call('set_channel_config',{'channels':original['channels']})
   assert (await call('get_channel_config'))['channels']==original['channels']
   checks.append('original channel config restored after tests')
 report={'passed':True,'firmware':'doll-lab-2.5.0','at':datetime.datetime.now().astimezone().isoformat(),'checks':checks,
         'not_tested':['Physical NTC probe','Physical vibration motor/driver and timer cutoff','Physical FSR ADC measurements']}
 (work/'channel-device-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');asyncio.run(main())
