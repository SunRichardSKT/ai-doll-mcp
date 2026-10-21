// Actual queue module; native Android, device and model are explicit doubles.
const assert=require('node:assert/strict'),path=require('node:path');
const {fixture}=require('./operit_test_host.cjs');
let finished=false;
process.on('beforeExit',()=>{if(!finished){console.error('FAIL unresolved queue test');process.exitCode=1;}});
async function scenario({delay=45,duration=70,wait=0,disable=false,stop=false,ackFailure=false,continuous=false}={}){
 let f,session,resolveFirst,started,reads=0,active=0,maxActive=0,emitted=0,firstSendAt;
 const events=[],acks=[],sends=[],captured=[],times=[0,2,2.2,2.4,2.6,2.8];
 const prefs={proactive_enabled:true,chat_integration_enabled:true};
 const options={tool:async(name,a)=>{
  const now=f.shared.Date.now()/1000;
  if(name==='get_interaction_status')return {active_session:session};
  if(name==='start_interaction'){started=now;session={id:'queue-session',chat_id:a.chat_id,started:now,deadline:now+a.duration_sec};return session;}
  if(name==='end_interaction'){session=null;return {ended:true};}
  if(name==='get_chat_context'){
   const selected=a.session_id?events.filter(e=>e.phase==='start'&&e.id>a.after&&e.id<=a.through):[];
   if(selected.length)captured.push(...selected.map(e=>e.event_id));
   return {context_protocol:'leased-batch-v1',preferences:prefs,proactive_delivery_allowed:!disable||firstSendAt===undefined||now-firstSendAt<delay,
    channels:[{channel:0,mode:'connected',feedback_level:'normal'}],events:selected,
    receipt_id:selected.length?'r'+selected.map(e=>e.id).join('_'):null,
    expires_at:selected.length?selected[0].at+30:null,persona:'',feedback:{}};
  }
  if(name==='get_interaction_device_events'){
   reads++;if(reads>1)f.advance(100);
   const t=f.shared.Date.now()/1000;
   while(emitted<times.length&&t-started>=times[emitted]){
    const e={id:events.length+1,event_id:'e'+(events.length+1),session_id:session.id,channel:0,touch_id:'t'+emitted,
     boot:'boot',phase:'start',sensor_type:'pressure',direction:'input',quality:'ok',source:'sensor',at:started+times[emitted],
     body_preferences:{feedback_level:'normal'}};
    events.push(e,{...e,id:e.id+1,event_id:'e'+(e.id+1),phase:'end',duration_ms:50});emitted++;
   }
   if(resolveFirst&&t-firstSendAt>=delay){
    const journal=JSON.parse(f.disk.get('/managed/queue.json'));
    assert.equal(journal.cursor,12,'all presses and releases are durable before the first reply completes');
    const finish=resolveFirst;resolveFirst=null;active--;finish({chatId:'chat-1',aiResponse:'收到摸摸啦'});
   }
   return {session,events:events.filter(e=>e.id>a.after),next_cursor:events.length};
  }
  if(name==='acknowledge_chat_context'){if(ackFailure)throw Error('ACK offline');acks.push(a.receipt_id);return {acknowledged:true};}
  throw Error('unexpected '+name);
 }};
 f=fixture(options);f.tools.Chat.sendMessage=(text,id,role,sender,flags)=>{
  sends.push({text,id,flags,at:f.shared.Date.now()/1000});active++;maxActive=Math.max(maxActive,active);
  if(sends.length===1){firstSendAt=f.shared.Date.now()/1000;return new Promise(resolve=>{
   resolveFirst=resolve;
   if(delay>duration)setImmediate(()=>{if(resolveFirst){resolveFirst=null;active--;resolve({chatId:'chat-1',aiResponse:'已完成'});}});
  });}
  active--;return Promise.resolve({chatId:id,aiResponse:'后面的摸摸也收到啦'});
 };
 const engine=f.load(path.resolve(__dirname,'../clients/operit/core/interaction.js'));
 const p={mcp_url:f.connection.mcp_url,chat_id:'chat-1',state_path:'/managed/queue.json',workflow_confirmed:true,duration_sec:duration,
  response_wait_sec:wait,continuous,ensure_active:async()=>{if(stop&&emitted===6){if(resolveFirst){const r=resolveFirst;resolveFirst=null;active--;r({chatId:'chat-1',aiResponse:'完成'});}throw Error('任务已停止');}}};
 let result,error;try{result=await engine.listen_interaction(p);}catch(e){error=e;}
 return {result,error,sends,acks,maxActive,captured,started,journal:JSON.parse(f.disk.get('/managed/queue.json'))};
}
(async()=>{
 const q=await scenario();assert.ifError(q.error);
 assert.equal(q.sends.length,2);assert.equal(q.maxActive,1);
 const first=JSON.parse(q.sends[0].text.split('\n').pop()),second=JSON.parse(q.sends[1].text.split('\n').pop());
 assert.equal(first.touch_count,1);assert.equal(second.touch_count,5);
 assert.deepEqual(second.events.map(e=>e.touch_id),['t1','t2','t3','t4','t5']);
 assert.equal(q.captured.length,6);assert.equal(new Set(q.captured).size,6);assert.equal(q.journal.pending,null);
 assert.ok(q.sends[1].at-q.sends[0].at>=45);assert.ok(second.events.every(e=>e.duration_ms===50));
 const merged=await scenario({wait:3});assert.ifError(merged.error);assert.equal(merged.sends.length,1);
 assert.equal(JSON.parse(merged.sends[0].text.split('\n').pop()).touch_count,6);
 assert.ok(merged.sends[0].at-merged.started>=5.8,'wait restarts after the last press/release');
 const mute=await scenario({disable:true});assert.ifError(mute.error);assert.equal(mute.sends.length,1);
 const expiry=await scenario({delay:135,duration:155});assert.ifError(expiry.error);assert.equal(expiry.sends.length,1);
 const deadline=await scenario({delay:25,duration:20});assert.ifError(deadline.error);assert.equal(deadline.sends.length,1);
 const stopped=await scenario({stop:true});assert.match(stopped.error.message,/停止/);assert.equal(stopped.sends.length,1);assert.deepEqual(stopped.journal.queue,[]);
 const ack=await scenario({ackFailure:true});assert.match(ack.error.message,/ACK offline/);assert.equal(ack.journal.pending.phase,'completed');
 const boundary=await scenario({continuous:true,duration:30});assert.ifError(boundary.error);
 assert.equal(boundary.result.state,'continued');assert.equal(boundary.journal.queue.flatMap(q=>q.events).length,5);
 const recovery=fixture();await recovery.prepare();
 const store=recovery.load(path.resolve(__dirname,'../clients/operit/core/settings.js'));
 const engine=recovery.load(path.resolve(__dirname,'../clients/operit/core/interaction.js'));
 const params=store.parameters(recovery.cfg()),journal={pending:{phase:'completed',receipt_ids:['r1','r2','r3']}};
 await assert.rejects(engine.settle(params,journal,async(name,a)=>{if(a.receipt_id==='r2')throw Error('ACK interrupted');return {acknowledged:true};}),/interrupted/);
 const saved=JSON.parse(recovery.disk.get(params.state_path));assert.deepEqual(saved.pending.receipt_ids,['r2','r3']);
 const resumed=[];await engine.settle(params,saved,async(name,a)=>{resumed.push(a.receipt_id);return {acknowledged:true};});
 assert.deepEqual(resumed,['r2','r3'],'partial ACK recovery never starts over at a pruned receipt');
 finished=true;console.log('PASS queue: 1 + 5 rapid presses during 45s generation, IDs/durations, custom quiet wait, single stream, expiry, stop, mute, ACK recovery and handoff. Host/device are doubles.');
})().catch(e=>{console.error(e);process.exitCode=1;});
