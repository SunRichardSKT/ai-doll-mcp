// Phone persistence and firmware transport contracts. Android/ESP32 are doubles;
// interruption tests reload the actual modules against the retained file map.
const assert=require('node:assert/strict'),path=require('node:path');
const {fixture}=require('./operit_test_host.cjs');
function host(options={}){
 const f=fixture(),calls=[],token='sync_fixture_token_1234567890';
 let boot='current_boot',epoch='a'.repeat(32),seq=0,storageId=0,ram=[],pending=[],lease=null,delivered=0,lost=0;
 const clock=()=>100000+f.shared.Date.now()-1700000000000;
 const storage=()=>({available:true,archive_lease_supported:options.legacy!==true,storage_epoch:epoch,
  pending_records:pending.length,lost_records:lost,corrupt_records:0,write_failures_since_boot:0,clock_synced:true});
 function emit(change={},eventBoot=boot){
  const raw={seq:++seq,uptime_ms:clock(),phase:seq%2?'start':'end',touch_id:'touch_'+Math.ceil(seq/2),channel:0,body_part:'头顶',
   sensor_type:'pressure',direction:'input',quality:'ok',source:'sensor',unit:'adc_raw',value:seq%2?2500:0,duration_ms:seq%2?0:2000,...change};
  if(eventBoot===boot){ram.push(raw);ram=ram.slice(-128);}
  pending.push({storage_id:++storageId,boot_id:eventBoot,event:raw});
  if(pending.length>256){pending.shift();lost++;}
  return raw;
 }
 const write=f.tools.Files.write;
 f.tools.Files.write=async(p,text,...args)=>{
  if(options.failCommit&&p.includes('_commit_'))return {successful:false};
  return await write(p,text,...args);
 };
 f.tools.Net.http=async p=>{
  if(options.offline)throw Error('fixture offline');
  if(p.method==='GET')return {statusCode:200,content:JSON.stringify(p.url.endsWith('/api/identity')?
   {device_id:'AI-Doll-sync',ip:'192.168.1.50',hostname:'ai-doll-112233445566.local'}:{enabled:true,token})};
  const body=JSON.parse(p.body);if(body.method==='notifications/initialized')return {statusCode:202,content:''};
  let result;
  if(body.method==='initialize')result={protocolVersion:'2025-11-25'};
  else{
   const n=body.params.name,a=body.params.arguments||{};calls.push({name:n,args:a});
   try{
    if(n==='doll_get_status')result={device_id:'AI-Doll-sync',device_name:'测试娃娃',boot_id:boot,event_cursor:seq,uptime_ms:clock(),
     ip:'192.168.1.50',hostname:'ai-doll-112233445566.local',archive_lease_supported:options.legacy!==true,remote_server:{enabled:false}};
    else if(n==='get_channel_config')result={port_state_model:'per_port_v1',channels:[{channel:0,name:'头顶',mode:'connected',enabled:true}]};
    else if(n==='read_channel_values')result={values:[]};
    else if(n==='acquire_archive_lease'){
     if(options.ownerBusy)throw Error('主归档端占用：computer');
     if(!lease||lease.expires<=f.shared.Date.now())lease={lease_id:'lease_'+f.shared.Date.now(),boot_id:boot,expires:f.shared.Date.now()+90000};
     result={lease_id:lease.lease_id,boot_id:boot,expires_in_sec:90};
    }else if(n==='renew_archive_lease'){
     assert.equal(a.lease_id,lease?.lease_id);lease.expires=f.shared.Date.now()+90000;result={...lease,expires_in_sec:90};
    }else if(n==='release_archive_lease'){lease=null;result={released:true};}
    else if(n==='get_touch_events'){
     const events=ram.filter(e=>e.seq>a.after).slice(0,24);
     result={device_id:'AI-Doll-sync',boot_id:boot,uptime_ms:clock(),events:a.include_persistent?[]:events,
      next_cursor:a.include_persistent?a.after:(events.at(-1)?.seq??a.after),event_storage:storage()};
     if(a.include_persistent){
      result.persistent_events=pending.slice(0,24);result.storage_cursor=result.persistent_events.at(-1)?.storage_id||0;
      result.storage_has_more=pending.length>result.persistent_events.length;
      if(a.archive_lease_id===lease?.lease_id)delivered=Math.max(delivered,result.storage_cursor);
      if(options.rebootAfterRead){options.rebootAfterRead=false;boot='restarted_boot';ram=[];seq=0;lease=null;}
     }
    }else if(n==='acknowledge_events'){
     assert.equal(a.boot_id,boot,'ACK uses the current response boot');assert.equal(a.storage_epoch,epoch);
     assert.equal(a.archive_lease_id,lease?.lease_id,'valid ownership is required');assert.ok(a.storage_cursor<=delivered);
     const persisted=[...f.disk].filter(([name])=>name.includes('_segment_')).flatMap(([,text])=>{
      try{return JSON.parse(text).data.events;}catch(_){return [];}
     });
     for(const entry of pending.filter(e=>e.storage_id<=a.storage_cursor)){
      const key='AI-Doll-sync:'+entry.boot_id+':'+entry.event.seq;
      assert.ok(persisted.some(e=>e.event_id===key),'a checked archive segment exists before device ACK');
     }
     assert.ok([...f.disk.keys()].some(name=>name.includes('_commit_')),'commit record precedes ACK');
     pending=pending.filter(e=>e.storage_id>a.storage_cursor);result=storage();
     if(options.loseAck){options.loseAck=false;throw Error('ACK response lost');}
    }else throw Error('Unexpected RPC '+n);
    result={structuredContent:result};
   }catch(error){return {statusCode:200,content:JSON.stringify({id:body.id,error:{code:-32602,message:error.message}})};}
  }
  return {statusCode:200,content:JSON.stringify({jsonrpc:'2.0',id:body.id,result})};
 };
 const connect=()=>f.load(path.resolve(__dirname,'../clients/operit/core/device.js')).connect(f.cfg().connection);
 const prepare=()=>f.invoke('setup_device',{host:'192.168.1.50'});
 return {f,options,calls,emit,connect,prepare,pending:()=>pending,boot:()=>boot,
  currentEpoch:()=>epoch,changeEpoch:()=>{epoch='b'.repeat(32);},reset:()=>f.resetModules()};
}
(async()=>{
 const h=host();await h.prepare();
 assert.equal(h.f.cfg().auto_sync_enabled,true);assert.equal(h.f.job().kind,'sync','recording can start before chat selection');
 assert.equal(h.f.cfg().chat,null);assert.equal(h.f.messages.length,0);
 for(let i=0;i<30;i++)h.emit({seq:i+1,uptime_ms:1000+i*100,time_quality:'unknown'},'unseen_old_boot');
 let tool=await h.connect();await tool('_sync_records');assert.equal(h.pending().length,6);
 await tool('_sync_records');assert.equal(h.pending().length,0);
 const unknown=await tool('query_device_history',{date:'unknown'});assert.equal(unknown.events.length,30);
 assert.ok(unknown.events.every(e=>e.at===null&&e.time_quality==='unknown'&&e.delivery_quality==='offline_replay'));
 assert.equal(h.f.messages.length,0,'backlog never sends a chat');
 const pages=h.calls.filter(c=>c.name==='get_touch_events');
 assert.ok(pages.every((p,i)=>!p.args.include_persistent||(i>0&&!pages[i-1].args.include_persistent)),'live page always precedes a persistent page');
 await h.f.invoke('bind_chat',{chat_id:'chat-1'});await h.f.invoke('set_experience',{enabled:true});
 const s=await tool('start_interaction',{chat_id:'chat-1',duration_sec:60});
 h.emit();h.emit();await tool('_sync_records');
 const live=await tool('get_chat_context',{chat_id:'chat-1',session_id:s.id});assert.equal(live.events.length,1);
 await tool('acknowledge_chat_context',{chat_id:'chat-1',receipt_id:live.receipt_id});
 const before=(await tool('query_device_history',{limit:200})).events.length;
 h.f.disk.set('/managed/device_'+h.f.cfg().connection.storage_key+'_events.json','broken index');
 h.reset();tool=await h.connect();await tool('_sync_records');
 assert.equal((await tool('query_device_history',{limit:200})).events.length,before,'segments rebuild a corrupt hot index');
 assert.equal((await tool('get_chat_context',{chat_id:'chat-1',session_id:s.id})).events.length,0,'receipt backup prevents replay during index rebuild');
 await h.f.invoke('set_experience',{enabled:false});assert.equal(h.f.cfg().auto_sync_enabled,true);
 assert.ok(['scheduled','running'].includes(h.f.job().phase),'turning proactive off preserves record collection');
 await h.f.invoke('stop');assert.equal(h.f.cfg().sync_paused,true);
 const stopped=h.f.job().id;await h.f.invoke('run_task',{job_id:'watchdog:'+h.f.cfg().binding});assert.equal(h.f.job().id,stopped);
 const failed=host({failCommit:true});await failed.prepare();failed.emit();
 let ft=await failed.connect();await assert.rejects(ft('_sync_records'),/保存/);
 assert.equal(failed.pending().length,1);assert.equal(failed.calls.filter(c=>c.name==='acknowledge_events').length,0);
 failed.options.failCommit=false;failed.reset();ft=await failed.connect();await ft('_sync_records');
 assert.equal(failed.pending().length,0);assert.equal((await ft('query_device_history')).events.length,1,'recovery does not duplicate a segment written before commit');
 const lost=host({loseAck:true});await lost.prepare();lost.emit();const lt=await lost.connect();
 await assert.rejects(lt('_sync_records'),/ACK response lost/);assert.equal(lost.pending().length,0);
 await lt('_sync_records');assert.equal((await lt('query_device_history')).events.length,1,'lost ACK response does not duplicate history');
 const reboot=host({rebootAfterRead:true});await reboot.prepare();reboot.emit();let rt=await reboot.connect();
 await assert.rejects(rt('_sync_records'),/current response boot|MCP/);assert.equal(reboot.pending().length,1);
 reboot.reset();rt=await reboot.connect();await rt('_sync_records');assert.equal(reboot.pending().length,0,'reboot rereads the page before acknowledging with the new boot');
 const busy=host({ownerBusy:true});await busy.prepare();busy.emit();const bt=await busy.connect();
 await assert.rejects(bt('_sync_records'),/主归档端占用/);assert.equal(busy.pending().length,1);
 const legacy=host({legacy:true});await legacy.prepare();for(let i=0;i<40;i++)legacy.emit();
 const old=await legacy.connect();await old('_sync_records');const oldCalls=legacy.calls.length;await old('_sync_records');
 assert.equal(legacy.calls.slice(oldCalls).filter(c=>c.name==='get_touch_events'&&c.args.include_persistent).length,0,'legacy duplicate page is throttled');
 assert.equal(legacy.pending().length,40);assert.equal(legacy.calls.filter(c=>c.name==='acknowledge_events').length,0);
 assert.equal((await old('get_record_sync_status')).compatibility_copy_only,true);
 const overflow=host();await overflow.prepare();for(let i=0;i<270;i++)overflow.emit();const ot=await overflow.connect();
 await ot('_sync_records');assert.equal((await ot('get_record_sync_status')).lost_records,14);
 assert.equal(overflow.f.messages.length,0);
 console.log('PASS phone sync: independent worker, live-first backlog, cross-boot unknown time, checked segments, index rebuild, ACK failure/reboot, ownership, legacy throttle, stop and overflow. Android/ESP32 are doubles.');
})().catch(e=>{console.error(e);process.exitCode=1;});
