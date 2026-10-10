const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/../templates/operit/ai_doll.js','utf8');
const metadata=JSON.parse(source.match(/\/\* METADATA\s*([\s\S]*?)\*\//)[1]);
const calls=[],messages=[];let result;
const context={exports:{},Set,JSON,Date,Number,Error,complete:x=>{result=x},Tools:{Net:{
  http:async options=>{calls.push(options);const body=JSON.parse(options.body);
    if(body.method==='notifications/initialized')return {statusCode:202,content:''};
    return {statusCode:200,content:JSON.stringify({jsonrpc:'2.0',id:body.id,result:
      body.method==='initialize'?{protocolVersion:'2025-11-25'}:{structuredContent:{sensor_mode:'simulation',verification:{call_id:'fixture'}}}})}}},
  Chat:{sendMessage:async(...args)=>{messages.push(args);return {text:'fixture-host-result'}}}}};
vm.runInNewContext(source,context);
(async()=>{
  assert.deepEqual(metadata.tools.map(t=>t.name).sort(),Object.keys(context.exports).sort());
  await context.exports.call_mcp({mcp_url:'https://example.com/private/mcp',tool:'doll_get_status'});
  assert.equal(calls.length,3);assert.equal(result.verification.call_id,'fixture');
  assert.equal(calls[2].headers['MCP-Protocol-Version'],'2025-11-25');
  await assert.rejects(()=>context.exports.call_mcp({mcp_url:'https://example.com/private/mcp',tool:'doll_vibrate'}));
  const body={schema:'ai-doll.host-event.v1',target_id:'existing-chat',event_id:'evt_'+'a'.repeat(32),expires_at:Date.now()/1000+30,
    event:{eventId:'evt_'+'a'.repeat(32),data:{events:[{direction:'input',sensor_type:'pressure',source:'simulation'}]}}};
  await context.exports.respond_to_event({chat_id:'existing-chat',event_json:JSON.stringify(body)});
  assert.equal(messages[0][1],'existing-chat');assert.equal(messages[0][4].runtime,'main');
  assert.equal(messages[0][4].hide_user_message,true);assert.ok(messages[0][0].includes('simulation'));
  for(const change of [{target_id:'wrong-chat'},{expires_at:0}])
    await assert.rejects(()=>context.exports.respond_to_event({chat_id:'existing-chat',event_json:JSON.stringify({...body,...change})}));
  body.event.data.events[0].direction='output';
  await assert.rejects(()=>context.exports.respond_to_event({chat_id:'existing-chat',event_json:JSON.stringify(body)}));
  assert.equal(messages.length,1);
  console.log('Operit package API contract fixture passed; no actual Android/model invocation.');
})().catch(error=>{console.error(error);process.exitCode=1});
