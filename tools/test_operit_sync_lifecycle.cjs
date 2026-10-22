// Exercises real workflow + phone worker lifecycle; native scheduling is a double.
const assert=require('node:assert/strict'),path=require('node:path');
const {phone}=require('./test_operit_archive.cjs');
const tests=[];const test=(name,fn)=>tests.push([name,fn]);
let finished=false;process.on('beforeExit',()=>{if(!finished){console.error('FAIL unresolved sync lifecycle test');process.exitCode=1;}});
async function configure(p,changes){const cfg=p.f.cfg();Object.assign(cfg,changes);await p.store.write('settings.json',cfg);return cfg;}
function gateOn(p,name){let arrived,release,used=false;const entered=new Promise(r=>arrived=r);
  p.options.beforeCall=async called=>{if(called===name&&!used){used=true;arrived();await new Promise(r=>release=r);}};
  return {entered,release:()=>release()};
}
test('sync starts without binding a chat, duplicate worker is rejected, stop disables all renewal',async()=>{
  const p=await phone();await configure(p,{auto_sync_enabled:true,chat:null});p.backlog(48);
  await p.f.invoke('schedule',{kind:'sync'});const id=p.f.job().id,gate=gateOn(p,'get_touch_events');
  const task=p.f.invoke('run_task',{job_id:id});await gate.entered;
  await assert.rejects(p.f.invoke('run_task',{job_id:id}),/正在运行/);
  const stop=p.f.invoke('stop');
  // Wait until the stop action has cancelled this collection generation.
  for(let i=0;i<30&&!p.f.cfg().sync_paused;i++)await Promise.resolve();
  gate.release();await task.catch(()=>{});await stop;
  assert.equal(p.f.job().phase,'stopped');assert.equal(p.state.acks.length,0);assert.equal(p.state.lease,null);
  assert.equal(p.f.cfg().active_reply_requested,false);assert.ok([...p.f.flows.values()].every(x=>!x.enabled));
  await p.f.invoke('run_task',{job_id:'watchdog:'+p.f.cfg().binding});assert.equal(p.f.job().phase,'stopped');assert.equal(p.f.messages.length,0);
});
test('turning off proactive response hands back to sync without turning sync off',async()=>{
  const p=await phone();await configure(p,{auto_sync_enabled:true,continuous:true});
  await p.f.invoke('set_experience',{enabled:true});await p.f.invoke('schedule',{kind:'interaction'});
  const id=p.f.job().id,gate=gateOn(p,'get_touch_events');const task=p.f.invoke('run_task',{job_id:id});await gate.entered;
  await p.f.invoke('set_experience',{enabled:false});gate.release();await task;
  assert.equal(p.f.cfg().continuous_enabled,false);assert.equal(p.f.cfg().auto_sync_enabled,true);assert.equal(p.f.cfg().sync_paused,false);
  assert.equal(p.f.job().kind,'sync');assert.equal(p.f.job().phase,'scheduled');assert.equal(p.f.messages.length,0);
});
test('scheduled sync upgrades in place to a finite interaction and then returns to sync',async()=>{
  const p=await phone();await configure(p,{auto_sync_enabled:true,duration_sec:2});
  await p.f.invoke('set_experience',{enabled:true});await p.f.invoke('schedule',{kind:'sync'});const id=p.f.job().id;
  const up=await p.f.invoke('schedule',{kind:'interaction'});assert.equal(up.reused,true);assert.equal(p.f.job().id,id);
  await p.f.invoke('run_task',{job_id:id});assert.equal(p.f.cfg().active_reply_requested,false);
  assert.equal(p.f.job().kind,'sync');assert.equal(p.f.job().phase,'scheduled');assert.equal(p.f.cfg().continuous_enabled,false);
});
test('uncertain chat send permits sync but never loops back into interaction',async()=>{
  const p=await phone();await configure(p,{auto_sync_enabled:true,continuous_enabled:true});
  await p.store.write('delivery_fixture-binding.json',{schema:1,chat_id:'chat-1',mcp_url:p.c.mcp_url,pending:{phase:'sending'}});
  await p.f.invoke('schedule',{kind:'sync'});p.backlog(48);const id=p.f.job().id;
  await p.f.invoke('run_task',{job_id:id});assert.equal(p.state.persistent.length,0);assert.equal(p.f.job().kind,'sync');
  assert.equal(JSON.parse(p.f.disk.get('/managed/delivery_fixture-binding.json')).pending.phase,'sending');assert.equal(p.f.messages.length,0);
});
test('identity mismatch disables retries/watchdog while keeping history and calibration',async()=>{
  const p=await phone();await configure(p,{auto_sync_enabled:true});await p.f.invoke('schedule',{kind:'sync'});
  const id=p.f.job().id;p.state.device='another-device';await assert.rejects(p.f.invoke('run_task',{job_id:id}),/身份/);
  assert.equal(p.f.cfg().sync_identity_changed,true);assert.equal(p.f.job().id,id);assert.ok([...p.f.flows.values()].every(x=>!x.enabled));
  await p.f.invoke('run_task',{job_id:'watchdog:'+p.f.cfg().binding});assert.equal(p.f.job().id,id);
  assert.equal(p.f.cfg().connection.device_id,p.c.device_id);
});
test('file failures stop background renewal instead of retrying as network failures',async()=>{
  const p=await phone();await configure(p,{auto_sync_enabled:true});await p.f.invoke('schedule',{kind:'sync'});p.backlog(24);
  const write=p.f.tools.Files.write;p.f.tools.Files.write=async(name,...args)=>name.includes('_segment_')?{successful:false}:write(name,...args);
  const id=p.f.job().id;await assert.rejects(p.f.invoke('run_task',{job_id:id}),/保存/);
  assert.equal(p.f.job().id,id);assert.equal(p.f.cfg().sync_paused,true);assert.equal(p.state.acks.length,0);
  assert.ok([...p.f.flows.values()].every(x=>!x.enabled));
});
test('network retries back off and stop interrupts a retry',async()=>{
  const p=await phone();await configure(p,{auto_sync_enabled:true});await p.f.invoke('schedule',{kind:'sync'});
  let attempts=0;p.options.beforeCall=async name=>{if(name==='doll_get_status'){attempts++;throw Error('network unavailable');}};
  const sleep=p.f.tools.System.sleep;let stopped=false;
  p.f.tools.System.sleep=async ms=>{await sleep(ms);if(attempts>=3&&!stopped){stopped=true;await p.f.invoke('stop');}};
  await assert.rejects(p.f.invoke('run_task',{job_id:p.f.job().id}),/停止/);
  assert.equal(p.f.job().phase,'stopped');assert.ok(attempts<10);assert.equal(p.f.messages.length,0);
});
test('disabling automatic sync does not disable an active response preference',async()=>{
  const p=await phone();await configure(p,{auto_sync_enabled:true});await p.f.invoke('set_experience',{enabled:true});
  await p.f.invoke('schedule',{kind:'sync'});await p.f.invoke('set_record_sync',{enabled:false});
  assert.equal(p.f.job().phase,'stopped');const prefs=await p.tool('get_chat_context',{chat_id:'chat-1'});assert.equal(prefs.preferences.proactive_enabled,true);
});
test('record sync recovers from a killed scheduled worker but cannot rearm after explicit stop',async()=>{
  const p=await phone();await configure(p,{auto_sync_enabled:true});await p.f.invoke('schedule',{kind:'sync'});const old=p.f.job().id;
  p.f.advance(91000);await p.f.invoke('run_task',{job_id:'watchdog:'+p.f.cfg().binding});assert.notEqual(p.f.job().id,old);
  await p.f.invoke('stop');const id=p.f.job().id;p.f.advance(900000);await p.f.invoke('run_task',{job_id:'watchdog:'+p.f.cfg().binding});assert.equal(p.f.job().id,id);assert.equal(p.f.job().phase,'stopped');
});
(async()=>{for(const [name,fn]of tests){await fn();console.log('PASS sync lifecycle: '+name);}finished=true;console.log('PASS '+tests.length+' sync lifecycle scenarios. Android and device are doubles.');})().catch(e=>{console.error(e);process.exitCode=1;});
