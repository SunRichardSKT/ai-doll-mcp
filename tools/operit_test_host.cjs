// Native Android APIs are explicit doubles. This loader exercises the actual
// CommonJS modules and public metadata, not a rewritten implementation.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../clients/operit');
function fixture(options={}) {
  const disk=new Map(),dirs=new Set(['/managed']),flows=new Map(),messages=[],calls=[];
  let clock=1700000000000,result,counter=0;
  class Clock extends Date {constructor(...args){super(...(args.length?args:[clock]));}static now(){return clock;}}
  // Operit 1.12.2 ToolResultData.toJson uses __type and omits Kotlin defaults.
  // In particular WorkflowNode.type and manual triggerType are absent on wire.
  function wireFlow(flow) {
    const result=JSON.parse(JSON.stringify(flow));
    result.nodes=result.nodes.map(node=>{
      const type=node.type;
      node.__type='com.ai.assistance.operit.data.model.'+(type==='trigger'?'TriggerNode':'ExecuteNode');
      if (!options.explicitWorkflowTypes) delete node.type;
      if (node.triggerType==='manual') delete node.triggerType;
      if (node.actionConfig) node.actionConfig=Object.fromEntries(Object.entries(node.actionConfig)
        .map(([key,value])=>[key,{__type:'com.ai.assistance.operit.data.model.ParameterValue.StaticValue',value}]));
      return node;
    });
    return result;
  }
  const tools={Files:{exists:async p=>({exists:disk.has(p)||dirs.has(p),isDirectory:dirs.has(p)}),
    list:async p=>({entries:[...disk.keys()].filter(k=>k.startsWith(p+'/')).map(k=>({name:k.slice(p.length+1),isDirectory:false}))}),
    mkdir:async p=>{dirs.add(p);return {successful:true};},
    read:async p=>{if(!disk.has(p.path))throw Error('missing file');return {content:disk.get(p.path)};},
    write:async(p,text)=>{if(options.writeFailure)return {successful:false};disk.set(p,text);return {successful:true};}},
    Workflow:{create:async(name,description,nodes,connections,enabled)=>{
      const flow={id:'workflow-'+(++counter),name,description,nodes,connections,enabled};flows.set(flow.id,flow);return wireFlow(flow);},
      get:async id=>{if(!flows.has(id))throw Error('missing workflow');return wireFlow(flows.get(id));},
      update:async(id,updates)=>{if(!flows.has(id))throw Error('missing workflow');if(options.workflowWriteFailure)throw Error('workflow update failed');Object.assign(flows.get(id),updates);return wireFlow(flows.get(id));},
      trigger:async()=>{throw Error('must not await trigger from control/UI');}},
    Chat:{listChats:async()=>({currentChatId:'chat-1',chats:[{id:'chat-1',title:'原聊天'},{id:'chat-2',title:'另一个聊天'}]}),
      findChat:async p=>({chat:options.chatMissing?null:{id:p.query,title:p.query==='chat-1'?'原聊天':'另一个聊天'}}),
      getMessages:async()=>({messages:messages.flatMap(m=>[{sender:'user',content:m.text},{sender:'ai',content:m.response||''}])}),
      sendMessage:async(text,id,role,sender,flags)=>{
        const entry={text,id,role,flags};messages.push(entry);
        if(options.sendFailure)throw Error('Timeout waiting for AI reply');
        entry.response=text.includes('后台发送自检')?'后台连接正常 '+text.match(/probe_\w+/)[0]:'模拟摸摸收到啦';
        return {chatId:id,aiResponse:entry.response};}},
    System:{sleep:async ms=>{if(options.realTime)await new Promise(r=>setTimeout(r,ms));else clock+=ms;}},
    Net:{http:async p=>{
      if(options.networkFailure)throw Error('unreachable');
      const body=JSON.parse(p.body);calls.push(body);
      if(body.method==='notifications/initialized')return {statusCode:202,content:''};
      const data=body.method==='initialize'?{protocolVersion:'2025-11-25'}:
        options.tool?await options.tool(body.params.name,body.params.arguments):
        body.params.name==='get_chat_context'?{context_protocol:'leased-batch-v1',preferences:{chat_integration_enabled:true,proactive_enabled:true},events:[]}:
        body.params.name==='get_device_overview'?{online:false}:{ok:true};
      return {statusCode:200,content:JSON.stringify({jsonrpc:'2.0',id:body.id,result:
        body.method==='initialize'?data:{structuredContent:data}})};
    }}};
  const cache=new Map();
  const shared={Tools:tools,Date:options.realTime?Date:Clock,JSON,Math,Number,String,Set,Error,Object,
    getPluginConfigDir:()=>'/managed',complete:r=>{result=r;}};
  function load(file) {
    file=path.resolve(file);
    if(!file.startsWith(root+path.sep))throw Error('Module outside toolpkg');
    if(cache.has(file))return cache.get(file);
    const exported={};cache.set(file,exported);
    vm.runInNewContext(fs.readFileSync(file,'utf8'),{...shared,exports:exported,
      require:p=>load(path.resolve(path.dirname(file),p))},{filename:file});
    return exported;
  }
  let app=load(path.join(root,'packages/companion.js'));
  const invoke=async(name,args={})=>{result=undefined;const returned=await app[name](args);return returned===undefined?result:returned;};
  const cfg=()=>JSON.parse(disk.get('/managed/settings.json'));
  const job=()=>JSON.parse(disk.get('/managed/job.json'));
  const connection={schema:1,kind:'ai-doll-operit-connection',mcp_url:'http://192.168.1.20:8775/'+ 'a'.repeat(64)+'/mcp',mode:'simulation',label:'演示'};
  const prepare=async()=>{await invoke('setup',{connection_json:JSON.stringify(connection)});await invoke('bind_chat',{chat_id:'chat-1'});};
  return {load,invoke,disk,dirs,flows,messages,calls,cfg,job,tools,options,connection,prepare,
    advance:ms=>{clock+=ms;},shared,resetModules:()=>{cache.clear();app=load(path.join(root,'packages/companion.js'));}};
}
exports.fixture=fixture;
