const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/../templates/operit/ai_doll_chat_probe.js','utf8');
const p={chat_id:'existing-chat',workflow_confirmed:true};
function fixture(options={}) {
  const storage=new Map(),sent=[],entries=[];let result;
  const host={exports:{},JSON,Date,Math,Number,Error,complete:r=>{result=r;},Tools:{
    Chat:{findChat:async()=>({chat:options.missing?null:{id:p.chat_id,title:'Existing chat'}}),
      listChats:async()=>({currentChatId:options.other?'other':p.chat_id}),
      getMessages:async()=>({messages:entries}),
      sendMessage:async(message,id,role,sender,flags)=>{
        assert.equal([...storage.values()].map(JSON.parse)[0].phase,'sending');
        sent.push({message,id,flags,role});
        const nonce=message.match(/probe_\d+_[a-f0-9]+/)[0];
        if(!options.noHistory)entries.push({sender:'user',content:message});
        if(options.timeout)throw Error('Timeout waiting for AI reply');
        const text='后台连接正常 '+nonce;entries.push({sender:'ai',content:text});
        return {chatId:options.wrong?'wrong':id,aiResponse:text};
      }},
    Files:{exists:async path=>({exists:path==='/storage/emulated/0/Download'||storage.has(path),isDirectory:path==='/storage/emulated/0/Download'}),
      read:async arg=>({content:storage.get(arg.path)}),
      write:async(path,text)=>{if(options.writeFailure)return {successful:false};storage.set(path,text);return {successful:true};}}
  }};
  vm.runInNewContext(source,host);
  return {host,storage,sent,result:()=>result};
}
(async()=>{
  const f=fixture();await f.host.exports.inspect_chat({chat_id:p.chat_id});assert.equal(f.sent.length,0);
  await f.host.exports.send_probe(p);const r=f.result();
  assert.equal(r.reply_returned,true);assert.equal(r.reply_nonce_matches,true);
  assert.equal(r.history_ai_reply_present,true);assert.equal(r.display_verified,false);
  assert.equal(f.sent[0].flags.hide_user_message,false);assert.equal(f.sent[0].flags.timeout_ms,90000);
  assert.equal(f.sent[0].flags.runtime,'main');assert.equal(f.sent[0].role,undefined);
  await f.host.exports.send_probe(p);assert.equal(f.sent.length,1);assert.equal(f.result().already_completed,true);
  for(const option of ['timeout','noHistory']){
    const x=fixture({timeout:true,[option]:true});await x.host.exports.send_probe(p);
    assert.equal(x.result().reply_returned,false);
    assert.equal(x.result().history_probe_present,option!=='noHistory');
    await x.host.exports.send_probe(p);assert.equal(x.sent.length,1);assert.equal(x.result().blocked_by_prior_probe,true);
  }
  for(const option of ['missing','writeFailure']) {
    const x=fixture({[option]:true});await assert.rejects(()=>x.host.exports.send_probe(p));assert.equal(x.sent.length,0);
  }
  await assert.rejects(()=>fixture().host.exports.send_probe({...p,workflow_confirmed:false}));
  console.log('Standalone Operit chat probe: visible send, exact target, no MCP, history evidence, uncertain-send retention passed with host doubles.');
})().catch(e=>{console.error(e);process.exitCode=1;});
