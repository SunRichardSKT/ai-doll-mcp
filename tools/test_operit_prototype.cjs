// Host API doubles: no Android application or real model is invoked.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/../templates/operit/ai_doll_prototype.js','utf8');
const params={mcp_url:'http://192.168.1.20:8775/example/mcp',chat_id:'existing-operit-chat',
  state_path:'/test/operit-state.json',workflow_confirmed:true,duration_sec:60};
function fixture(options={}) {
  let clock=1700000000000,active=null,polls=0,result;
  const storage=new Map(),calls=[],messages=[];
  class Clock extends Date { static now(){return clock;} }
  const event={id:1,event_id:'fixture:boot:1',session_id:'session',phase:'start',sensor_type:'pressure',
    direction:'input',quality:'ok',source:'simulation',at:clock/1000,body_part:'头',value:3100,unit:'adc_raw',
    body_preferences:{feedback_level:'normal'}};
  const context={preferences:{chat_integration_enabled:true,proactive_enabled:true},receipt_id:'receipt',
    events:[event],expires_at:clock/1000+30,persona:'补充人设',feedback:{tone:'温柔'}};
  const state=()=>JSON.parse(storage.get(params.state_path)||'null');
  async function tool(name,args) {
    calls.push({name,args});
    if(name==='get_interaction_status')return {active_session:active};
    if(name==='start_interaction')return active={id:'session',chat_id:params.chat_id,started:clock/1000,deadline:clock/1000+args.duration_sec};
    if(name==='end_interaction'){active=null;return {ended:clock/1000};}
    if(name==='get_interaction_device_events') {
      polls++;
      if(polls>2)return {events:[],next_cursor:1,session_closed:true,session:active};
      return {events:options.events||[event,{...event,phase:'end',id:2}],next_cursor:2,session:active,
        collector_error:options.offline?'offline':null};
    }
    if(name==='get_chat_context')return args.after===undefined?{preferences:context.preferences,events:[]}:
      options.noContext?{...context,events:[],receipt_id:null}:context;
    if(name==='acknowledge_chat_context'){
      if(options.ackFailure)throw Error('ack unavailable');
      context.events=[];return {acknowledged:true,display_verified:false};
    }
    throw Error('Unexpected tool '+name);
  }
  const host={exports:{},Date:Clock,JSON,Number,Set,Error,complete:value=>{result=JSON.parse(JSON.stringify(value));},Tools:{
    Net:{http:async request=>{
      const body=JSON.parse(request.body);
      if(body.method==='notifications/initialized')return {statusCode:202,content:''};
      let data=body.method==='initialize'?{protocolVersion:'2025-11-25'}:{structuredContent:await tool(body.params.name,body.params.arguments)};
      return {statusCode:200,content:JSON.stringify({jsonrpc:'2.0',id:body.id,result:data})};
    }},
    Files:{exists:async path=>path==='/test'?{exists:!options.parentMissing,isDirectory:true}:
        options.stateDirectory?{exists:true,isDirectory:true}:{exists:storage.has(path),isDirectory:false},
      read:async p=>({content:storage.get(p.path)}),
      write:async(path,text)=>{if(options.writeFailure)return {successful:false};storage.set(path,text);return {successful:true};}},
    System:{sleep:async milliseconds=>{clock+=milliseconds;}},
    Chat:{listChats:async()=>({chats:[{id:params.chat_id}]}),
      findChat:async p=>({matchedCount:options.chatMissing?0:1,chat:options.chatMissing?null:{id:p.query}}),
      agentStatus:async()=>{throw Error('Chat service not connected');},
      sendMessage:async(...args)=>{
        assert.equal(state().pending.phase,'sending','write-ahead intent before host send');
        if(options.nativeBusy)throw Error('Previous message is still being processed');
        messages.push(args);
        if(options.sendFailure)throw Error('ambiguous timeout');
        if(options.replyDelayMs) {
          if(options.replyDelayMs>args[4].timeout_ms) {clock+=args[4].timeout_ms;throw Error('Timeout waiting for AI reply');}
          clock+=options.replyDelayMs;
        }
        return {chatId:options.wrongChat?'another-chat':args[1],aiResponse:'模拟摸摸收到啦。'};
      }}
  }};
  vm.runInNewContext(source,host);
  return {host,calls,messages,storage,event,context,state,report:()=>result,options};
}
async function run() {
  const f=fixture();
  const meta=JSON.parse(source.match(/\/\* METADATA\s*([\s\S]*?)\*\//)[1]);
  assert.deepEqual(meta.tools.map(x=>x.name).sort(),Object.keys(f.host.exports).sort());
  await f.host.exports.list_existing_chats();assert.equal(f.report().chats[0].id,params.chat_id);
  await f.host.exports.listen_interaction(params);
  assert.equal(f.messages.length,1,'duplicate page/release does not generate another reply');
  const sent=f.messages[0];assert.equal(sent[1],params.chat_id);assert.equal(sent[4].runtime,'main');
  assert.equal(sent[4].hide_user_message,true);assert.equal(sent[2],undefined,'no new role/model');
  assert.ok(sent[4].timeout_ms<=30000,'native queue wait is bounded by context freshness');
  assert.ok(sent[0].includes('simulation'));assert.equal(f.state().pending,null);
  assert.equal(f.report().display_verified,false);assert.equal(f.report().model_response_returned,true);
  assert.ok(f.calls.some(x=>x.name==='end_interaction'));
  const slow=fixture({replyDelayMs:20000});
  await slow.host.exports.listen_interaction({...params,duration_sec:15});
  assert.equal(slow.messages.length,1,'reply may finish after new-touch admission window');
  assert.ok(slow.messages[0][4].timeout_ms>15000);
  assert.equal(slow.report().model_response_returned,true);
  const tooSlow=fixture({replyDelayMs:40000});
  await assert.rejects(()=>tooSlow.host.exports.listen_interaction({...params,duration_sec:15}),/main_chat_send.*Timeout/);
  assert.equal(tooSlow.state().pending.phase,'sending');
  await tooSlow.host.exports.reconcile_delivery({...params,decision:'discard'});
  assert.equal(tooSlow.state().pending,null);
  assert.equal(tooSlow.report().model_reply_verified,false);
  assert.equal(tooSlow.messages.length,1,'discard must not regenerate');
  for(const invalid of [{chat_id:'main'},{workflow_confirmed:false},{duration_sec:61},{state_path:'relative'},
    {state_path:'/storage/emulated/0/Download/Operit/'},{state_path:'/storage/emulated/0/Download/Operit'},
    {mcp_url:'http://user:pass@example.com/mcp'}]) {
    const x=fixture();await assert.rejects(()=>x.host.exports.listen_interaction({...params,...invalid}));
    assert.equal(x.messages.length,0);
  }
  for(const field of [{phase:'end'},{direction:'output'},{source:'offline'},{delivery_quality:'offline_replay'},
    {quality:'fault'},{at:1699999900},{session_id:'other-session'},{sensor_type:'temperature'}]) {
    const x=fixture();x.options.events=[{...x.event,...field}];
    await x.host.exports.listen_interaction(params);assert.equal(x.messages.length,0);
  }
  for(const level of ['light','off']) {
    const x=fixture();x.context.events[0].body_preferences.feedback_level=level;
    await x.host.exports.listen_interaction(params);assert.equal(x.messages.length,0);
  }
  for(const flag of ['proactive_enabled','chat_integration_enabled']) {
    const x=fixture();x.context.preferences[flag]=false;
    await assert.rejects(()=>x.host.exports.listen_interaction(params));assert.equal(x.messages.length,0);
  }
  for(const option of ['chatMissing','nativeBusy','offline','writeFailure','stateDirectory','parentMissing']) {
    const x=fixture({[option]:true});await assert.rejects(()=>x.host.exports.listen_interaction(params));
    assert.equal(x.messages.length,0);
  }
  for(const option of ['stateDirectory','parentMissing']) {
    const x=fixture({[option]:true});
    await assert.rejects(()=>x.host.exports.listen_interaction(params),/AI Doll \[delivery_state\]/);
    assert.ok(!x.calls.some(c=>c.name==='start_interaction'),'invalid state directory cannot create a session');
  }
  const missing=fixture({chatMissing:true});
  await assert.rejects(()=>missing.host.exports.listen_interaction(params),/AI Doll \[chat_binding\]/);
  assert.equal(missing.calls.length,0,'invalid chat must fail before MCP/session creation');
  const ambiguous=fixture({sendFailure:true});
  await assert.rejects(()=>ambiguous.host.exports.listen_interaction(params));
  assert.equal(ambiguous.state().pending.phase,'sending');
  await assert.rejects(()=>ambiguous.host.exports.listen_interaction(params),/Uncertain send/);
  assert.equal(ambiguous.messages.length,1,'ambiguous timeout must not replay');
  await ambiguous.host.exports.reconcile_delivery({...params,decision:'delivered'});
  assert.equal(ambiguous.state().pending,null);
  const lostAck=fixture({ackFailure:true});
  await assert.rejects(()=>lostAck.host.exports.listen_interaction(params));
  assert.equal(lostAck.state().pending.phase,'completed');
  lostAck.options.ackFailure=false;
  await lostAck.host.exports.listen_interaction(params);
  assert.equal(lostAck.messages.length,1,'ACK retry cannot regenerate');
  const wrong=fixture({wrongChat:true});await assert.rejects(()=>wrong.host.exports.listen_interaction(params));
  assert.equal(wrong.state().pending.phase,'sending');
  const mismatch=fixture();mismatch.storage.set(params.state_path,JSON.stringify({schema:1,chat_id:'other',mcp_url:params.mcp_url}));
  await assert.rejects(()=>mismatch.host.exports.listen_interaction(params),/another chat/);
  console.log('Operit prototype: workflow, freshness, body levels, preferences, durable recovery, ACK retry and chat isolation passed. Host/model APIs are test doubles.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
