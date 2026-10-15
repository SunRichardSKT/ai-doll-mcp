// Network is real MCP HTTP. Android Chat/Files APIs below are explicit test doubles.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [url,statePath]=process.argv.slice(2);
const androidStatePath=statePath.startsWith('/')?statePath:'/'+statePath;
const disk=p=>/^\/[a-z]:\//i.test(p)?p.slice(1):p;
let output;const messages=[];
const tools={
  Net:{http:async p=>{const r=await fetch(p.url,{method:p.method,headers:p.headers,body:p.body,redirect:'manual'});
    return {statusCode:r.status,content:await r.text()};}},
  Files:{exists:async p=>({exists:fs.existsSync(disk(p)),isDirectory:fs.existsSync(disk(p))&&fs.statSync(disk(p)).isDirectory()}),
    read:async p=>({content:fs.readFileSync(disk(p.path),'utf8')}),
    write:async(p,content)=>{fs.writeFileSync(disk(p),content);return {successful:true};}},
  System:{sleep:ms=>new Promise(resolve=>setTimeout(resolve,ms))},
  Chat:{findChat:async p=>({matchedCount:1,chat:{id:p.query}}),
    agentStatus:async()=>{throw Error('Chat service not connected');},
    sendMessage:async(message,chatId,...rest)=>{messages.push({message,chatId,options:rest[2]});
      return {chatId,aiResponse:'fixture model reply; not an actual Android model'};}}
};
const app={exports:{},Tools:tools,Date,JSON,Number,Error,complete:r=>{output=r;}};
vm.runInNewContext(fs.readFileSync(__dirname+'/../templates/operit/ai_doll_prototype.js','utf8'),app);
(async()=>{
  await app.exports.listen_interaction({mcp_url:url,chat_id:'operit-sdk-chat',state_path:androidStatePath,
    workflow_confirmed:true,duration_sec:3});
  assert.equal(messages.length,1);assert.equal(messages[0].chatId,'operit-sdk-chat');
  assert.ok(messages[0].message.includes('simulation'));assert.equal(output.display_verified,false);
  assert.equal(JSON.parse(fs.readFileSync(statePath,'utf8')).pending,null);
  console.log('Real MCP HTTP + isolated archive + Operit host doubles passed; no Android/model/display verification.');
})().catch(e=>{console.error(e);process.exitCode=1;});
