// Actual phone modules; Android and ESP32 RPC APIs are explicit doubles.
const assert=require('node:assert/strict'),path=require('node:path');
const {fixture}=require('./operit_test_host.cjs');
function phone(options={}){
  const f=fixture(),nativeCalls=[];
  const token='test_device_token_1234567890';let boot='fixture-boot',device='AI-Doll-phone-fixture',events=[],seq=0;
  const uptime=()=>100000+(f.shared.Date.now()-1700000000000);
  function emit(phase='start',change={}){
    events.push({seq:++seq,uptime_ms:uptime(),phase,touch_id:'touch-1',channel:0,body_part:'头',
      source:'sensor',sensor_type:'pressure',direction:'input',quality:'ok',value:2500,unit:'adc_raw',...change});
  }
  f.tools.Net.http=async p=>{
    if(options.offline)throw Error('device unavailable');
    if(p.method==='GET')return {statusCode:options.authRequired?401:200,content:JSON.stringify({enabled:true,token})};
    assert.equal(p.headers.Authorization,'Bearer '+token);
    const body=JSON.parse(p.body);
    if(body.method==='notifications/initialized')return {statusCode:202,content:''};
    let result;
    if(body.method==='initialize')result={protocolVersion:'2025-11-25'};
    else {
      const name=body.params.name,a=body.params.arguments;nativeCalls.push(name);
      if(name==='doll_get_status')result={device_id:device,firmware:'fixture-2.9',boot_id:boot,event_cursor:seq,uptime_ms:uptime(),
        sensor_mode:'sensor',wifi_connected:true,physical_outputs_enabled:false,remote_server:{enabled:!!options.serverEnabled}};
      else if(name==='get_channel_config')result={channels:[{channel:0,name:'头',type:'pressure',enabled:true,calibration:{keep:42}}]};
      else if(name==='read_channel_values')result={values:[{channel:0,value:0,quality:'ok'}]};
      else if(name==='get_touch_events'){
        if(options.emitOnce){options.emitOnce=false;emit();emit('end');}
        result={device_id:device,boot_id:boot,uptime_ms:uptime(),next_cursor:seq,boot_changed:a.boot_id!==boot,
          gap:!!options.gap,events:events.filter(e=>e.seq>a.after)};
      } else throw Error('Unexpected device write/read '+name);
      result={content:[{type:'text',text:JSON.stringify(result)}]};
    }
    return {statusCode:200,content:JSON.stringify({jsonrpc:'2.0',id:body.id,result})};
  };
  async function prepare(){await f.invoke('setup_device',{host:'192.168.1.50'});await f.invoke('bind_chat',{chat_id:'chat-1'});}
  const connect=()=>f.load(path.resolve(__dirname,'../clients/operit/core/device.js')).connect(f.cfg().connection);
  return {f,options,nativeCalls,emit,prepare,connect,reboot:()=>{boot='new-boot';seq=0;events=[];},replaceDevice:()=>{device='different-device';}};
}
(async()=>{
  const p=phone();await p.prepare();
  const cfg=p.f.cfg();assert.equal(cfg.connection.mode,'phone');
  assert.equal((await p.f.invoke('check_connection')).overview.transport,'phone_device_wifi');
  assert.ok(!JSON.stringify(await p.f.invoke('status')).includes(cfg.connection.token),'status never returns device credentials');
  await p.f.invoke('set_experience',{enabled:true,duration_sec:900});
  assert.equal(p.f.cfg().duration_sec,900);
  const tool=await p.connect();
  p.emit(); // Events before the new session are not replayed as live input.
  const s=await tool('start_interaction',{chat_id:'chat-1',duration_sec:60});
  p.emit();p.emit('end');p.emit('start',{touch_id:'bad-quality',quality:'fault'});
  p.emit('start',{touch_id:'old',uptime_ms:69000});
  const args={chat_id:'chat-1',session_id:s.id,after:0};
  const batch=await tool('get_interaction_device_events',args);assert.equal(batch.events.length,4);
  assert.equal((await tool('get_interaction_device_events',{...args,after:batch.next_cursor})).events.length,0);
  const c=await tool('get_chat_context',{chat_id:'chat-1'});
  assert.equal(c.events.length,1);assert.equal(c.events[0].source,'sensor');
  assert.equal(c.events[0].body_part,'头');assert.equal(c.events[0].unit,'adc_raw');
  assert.equal((await tool('get_chat_context',{chat_id:'chat-1'})).receipt_id,c.receipt_id);
  await assert.rejects(tool('acknowledge_chat_context',{chat_id:'chat-2',receipt_id:c.receipt_id}),/回执/);
  await tool('acknowledge_chat_context',{chat_id:'chat-1',receipt_id:c.receipt_id});
  assert.equal((await tool('get_chat_context',{chat_id:'chat-1'})).events.length,0);
  assert.equal((await tool('get_chat_context',{chat_id:'chat-2'})).events.length,1);
  assert.ok([...p.f.disk.keys()].some(k=>/history_\d{8}\.json$/.test(k)),'daily history saved on Android');
  await assert.rejects(tool('end_interaction',{chat_id:'chat-2',session_id:s.id}),/其他聊天/);
  await tool('end_interaction',{chat_id:'chat-1',session_id:s.id});
  const before=JSON.stringify([...p.f.disk.entries()].filter(([k])=>k.includes('history_')));
  const again=await tool('start_interaction',{chat_id:'chat-1',duration_sec:1});p.f.advance(1100);
  assert.equal((await tool('get_interaction_device_events',{chat_id:'chat-1',session_id:again.id})).session_closed,true);
  assert.equal(JSON.stringify([...p.f.disk.entries()].filter(([k])=>k.includes('history_'))),before);
  const restart=await tool('start_interaction',{chat_id:'chat-1',duration_sec:60});p.reboot();
  await assert.rejects(tool('get_interaction_device_events',{chat_id:'chat-1',session_id:restart.id}),/重启/);
  assert.equal((await tool('get_interaction_status')).active_session,null);
  const original=p.f.disk.get('/managed/settings.json');p.replaceDevice();
  await assert.rejects(p.f.invoke('check_connection'),/身份/);
  assert.equal(p.f.disk.get('/managed/settings.json'),original);
  const bad=phone({serverEnabled:true});await assert.rejects(bad.prepare(),/直传服务器/);
  const auth=phone({authRequired:true});await assert.rejects(auth.prepare(),/登录保护/);
  assert.equal((await auth.f.invoke('setup_device',{host:'192.168.1.50',token:'test_device_token_1234567890'})).saved,true);
  const old=phone({gap:true});await old.prepare();await old.f.invoke('set_experience',{enabled:true});const ot=await old.connect();
  const os=await ot('start_interaction',{chat_id:'chat-1',duration_sec:60});old.emit();
  await ot('get_interaction_device_events',{chat_id:'chat-1',session_id:os.id});
  assert.equal((await ot('get_chat_context',{chat_id:'chat-1'})).events.length,0,'gap recovery is history only');
  await ot('update_companion_preferences',{changes:{muted:true}});
  assert.equal((await ot('get_chat_context',{chat_id:'chat-1'})).events.length,0);
  const live=phone();await live.prepare();await live.f.invoke('check_connection');await live.f.invoke('set_experience',{enabled:true});
  await live.f.invoke('schedule',{kind:'probe'});await live.f.invoke('run_task',{job_id:live.f.job().id});await live.f.invoke('confirm_probe');
  const settings=live.f.cfg();settings.duration_sec=2;live.f.disk.set('/managed/settings.json',JSON.stringify(settings));
  live.options.emitOnce=true;await live.f.invoke('schedule',{kind:'interaction'});
  const done=await live.f.invoke('run_task',{job_id:live.f.job().id});
  assert.equal(done.replies,1);assert.equal(live.f.messages.length,2);
  assert.equal(live.f.messages[1].flags.runtime,'main');assert.equal(live.f.messages[1].id,'chat-1');
  assert.ok(live.f.messages[1].text.includes('"source":"sensor"'));
  assert.ok(live.nativeCalls.every(n=>['doll_get_status','get_channel_config','read_channel_values','get_touch_events'].includes(n)),
    'phone mode never writes sampling, calibration, outputs or flash acknowledgements');
  const priorBinding=live.f.cfg().binding,priorKey=live.f.cfg().connection.storage_key;
  await live.f.invoke('setup_device',{host:'192.168.1.51'});
  assert.equal(live.f.cfg().binding,priorBinding,'same hardware at new DHCP address keeps chat binding');
  assert.equal(live.f.cfg().connection.storage_key,priorKey,'same hardware keeps history and receipts');
  const engine=live.f.load(path.resolve(__dirname,'../clients/operit/core/interaction.js'));
  const params=live.f.load(path.resolve(__dirname,'../clients/operit/core/settings.js')).parameters(live.f.cfg());
  assert.equal((await engine.load(params)).mcp_url,'http://192.168.1.51/mcp','journal accepts only confirmed same device identity');
  live.options.offline=true;
  assert.equal((await live.f.invoke('view_history')).events.length,2,'phone history remains readable offline');
  assert.equal((await live.f.invoke('set_experience',{enabled:false})).preferences.proactive_enabled,false,
    'local stop and preferences still work without the device network');
  const local=p.f.load(path.resolve(__dirname,'../clients/operit/core/device.js'));
  for(const host of ['127.0.0.1','example.com','192.168.1.1:80','192.168.1.1/anything','999.1.1.1','8.8.8.8'])
    assert.throws(()=>local.localHost(host));
  console.log('PASS phone-only modules: pairing, auth, identity, history, receipts, isolation, freshness, release suppression, reboot, gap, bounded interaction and original MAIN chat. ESP32/Android are doubles.');
})().catch(e=>{console.error(e);process.exitCode=1;});
