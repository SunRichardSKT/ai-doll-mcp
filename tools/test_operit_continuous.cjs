// Actual worker, state journal and Workflow code; Android scheduling/model are doubles.
const assert=require('node:assert/strict');
const {fixture}=require('./operit_test_host.cjs');
function host(){
 let f,session=null,seq=0,starts=0,emit=false;const events=[],acked=new Set(),reads=[];
 let preferences={chat_integration_enabled:true,proactive_enabled:true,persona_source:'chat',doll_persona:''};
 const options={tool:async(name,a)=>{
  if(options.offline)throw Error('fixture device offline');
  const now=f.shared.Date.now()/1000;
  if(session&&session.deadline<=now)session=null;
  if(name==='get_installation_status')return {online:true};
  if(name==='update_companion_preferences'){preferences={...preferences,...a.changes};return {preferences};}
  if(name==='get_interaction_status')return {active_session:session};
  if(name==='start_interaction'){starts++;session={id:'s'+starts,chat_id:a.chat_id,started:now,deadline:now+a.duration_sec};return session;}
  if(name==='end_interaction'){assert.equal(session?.id||a.session_id,a.session_id);session=null;return {ended:true};}
  if(name==='get_interaction_device_events'){
   reads.push({session:a.session_id,after:a.after});
   if(emit){emit=false;events.push({id:++seq,event_id:'e'+seq,session_id:session.id,phase:'start',sensor_type:'pressure',direction:'input',
    quality:'ok',source:'sensor',at:now,body_part:'头顶',touch_id:'t'+seq,body_preferences:{feedback_level:'normal'}});
    events.push({...events[events.length-1],id:++seq,event_id:'e'+seq,phase:'end'});}
   else f.advance(Math.max(500,(a.wait_seconds||0)*1000));
   return {session,events:events.filter(e=>e.session_id===a.session_id&&e.id>a.after),next_cursor:seq};
  }
  if(name==='get_chat_context'){
   const event=a.after===undefined?null:events.find(e=>e.id>a.after&&e.phase==='start'&&(!a.session_id||e.session_id===a.session_id)&&(a.through===undefined||e.id<=a.through)&&!acked.has(e.event_id));
   return {context_protocol:'leased-batch-v1',preferences,persona:preferences.doll_persona,persona_priority:preferences.persona_source==='doll'?'saved_doll':'current_chat',
    events:event?[event]:[],receipt_id:event?'r'+event.id:null,expires_at:event?event.at+30:null};
  }
  if(name==='acknowledge_chat_context'){acked.add('e'+a.receipt_id.slice(1));return {acknowledged:true};}
  return {online:true,channels:[]};
 }};
 f=fixture(options);
 async function ready(){await f.prepare();await f.invoke('schedule',{kind:'probe'});await f.invoke('run_task',{job_id:f.job().id});await f.invoke('confirm_probe');
  await f.invoke('set_experience',{enabled:true,continuous:true});await f.invoke('schedule',{kind:'interaction'});}
 return {f,options,ready,emit:()=>{emit=true;},reads,starts:()=>starts,preferences:()=>preferences};
}
(async()=>{
 const h=host();await h.ready();const f=h.f;
 assert.equal(f.cfg().continuous_enabled,true);
 const watchdog=f.flows.get(f.cfg().workflows.watchdog);
 assert.equal(watchdog.nodes[0].triggerConfig.repeat,'true');
 assert.equal(watchdog.nodes[0].triggerConfig.interval_ms,'900000');
 const before=f.messages.length,initial=f.shared.Date.now();
 for(let n=0;n<6;n++){
  h.emit();const id=f.job().id;
  await f.invoke('run_task',{job_id:id});
  assert.equal(f.job().phase,'scheduled','successful chunks automatically schedule their successor');
  assert.notEqual(f.job().id,id);assert.equal(f.cfg().continuous_enabled,true);
  if(n===0){const unchanged=f.job().id;await f.invoke('run_task',{job_id:'watchdog:'+f.cfg().binding});assert.equal(f.job().id,unchanged,'watchdog never duplicates a live successor');}
  f.advance(10000);
 }
 assert.ok(f.shared.Date.now()-initial>20*60000,'continuous mode lasts beyond fifteen minutes');
 assert.equal(f.messages.length-before,6,'one reply for each newly emitted touch');
 assert.ok(h.starts()>=2&&h.starts()<6,'bounded leases rotate while journal resumes intervening chunks');
 assert.ok(h.reads.some(r=>r.after>0),'handoff preserves event cursor');
 await f.invoke('set_experience',{response_wait_sec:2.5});assert.equal(f.cfg().response_wait_sec,2.5,'quiet delay can change without stopping continuous mode');
 await assert.rejects(f.invoke('set_experience',{continuous:false}),/关闭常开|停止当前后台任务/);
 await assert.rejects(f.invoke('bind_chat',{chat_id:'chat-2'}));
 await f.invoke('stop');assert.equal(f.cfg().continuous_enabled,false);
 assert.ok([...f.flows.values()].every(x=>!x.enabled));
 const count=f.messages.length;await f.invoke('run_task',{job_id:'watchdog:'+f.cfg().binding});assert.equal(f.messages.length,count);
 const killed=host();await killed.ready();const old=killed.f.job().id;killed.f.advance(91000);
 await killed.f.invoke('run_task',{job_id:'watchdog:'+killed.f.cfg().binding});
 assert.notEqual(killed.f.job().id,old,'periodic recovery replaces expired unsent jobs');
 const failed=host();await failed.ready();failed.options.sendFailure=true;failed.emit();
 const pendingJob=failed.f.job().id;
 await assert.rejects(failed.f.invoke('run_task',{job_id:pendingJob}),/main_chat_send/);
 assert.equal(failed.f.job().id,pendingJob,'uncertain send prevents automatic successor');
 await failed.f.invoke('run_task',{job_id:'watchdog:'+failed.f.cfg().binding});
 assert.equal(failed.f.job().id,pendingJob,'watchdog does not retry uncertain send');
 assert.equal(failed.f.messages.length,2,'one probe and one ambiguous attempt only');
 failed.options.sendFailure=false;await failed.f.invoke('recover',{decision:'discard'});
 assert.notEqual(failed.f.job().id,pendingJob,'user reconciliation resumes continuous listening without another send probe');
 assert.equal(failed.f.messages.length,2,'recovery never automatically resends the ambiguous message');
 const offline=host();await offline.ready();offline.options.offline=true;const first=offline.f.job().id;
 await assert.rejects(offline.f.invoke('run_task',{job_id:first}),/offline/);
 assert.notEqual(offline.f.job().id,first);assert.equal(offline.f.job().delay_ms,60000,'network failure uses delayed continuation');
 const stopped=await offline.f.invoke('stop');assert.equal(offline.f.cfg().continuous_enabled,false,'stop persists even if device is offline');
 assert.equal(offline.f.job().phase,'stopped','an offline remote cannot lock local settings');
 assert.equal(stopped.stopped,true);
 await offline.f.invoke('set_experience',{continuous:false});
 assert.equal(offline.f.cfg().continuous,false,'configuration is unlocked after local stop');
 const remote=host();await remote.ready();await remote.f.invoke('run_task',{job_id:remote.f.job().id});remote.options.offline=true;
 const pending=await remote.f.invoke('stop');assert.equal(pending.cleanup_pending,true);assert.equal(pending.remote_session_ended,false);
 await remote.f.invoke('bind_chat',{chat_id:'chat-2'});assert.equal(remote.f.cfg().chat.id,'chat-2');
 const disabled=host();await disabled.ready();disabled.preferences().proactive_enabled=false;disabled.emit();
 await disabled.f.invoke('run_task',{job_id:disabled.f.job().id});
 assert.equal(disabled.f.cfg().continuous_enabled,false,'remote preference off stops automatic continuation');
 assert.ok([...disabled.f.flows.values()].every(x=>!x.enabled));
 const moved=host();await moved.ready();
 await moved.f.invoke('update_computer_address',{host:'192.168.1.70'});
 assert.equal(moved.f.cfg().continuous_enabled,false,'IP repair clears continuous intent');
 assert.ok([...moved.f.flows.values()].every(x=>!x.enabled));
 console.log('PASS continuous: >20min, lease/cursor handoff, periodic recovery, stop, no duplicate jobs, uncertain-send block and offline backoff. Android is a double.');
})().catch(e=>{console.error(e);process.exitCode=1;});
