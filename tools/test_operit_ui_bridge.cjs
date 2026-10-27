// Run the actual UI against Operit 1.12.2's JS context bridge; Android tools are
// explicit doubles. Cached upstream code stays under build/, never in delivery.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {fixture}=require('./operit_test_host.cjs');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'clients/operit/ui/settings.ui.js'),'utf8');
const directory=process.argv[2]||path.join(root,'build/integration-research/operit-1.12.2/runtime');
const bridge=fs.readFileSync(path.join(directory,'context.js'),'utf8');
const container='org.ai_doll.companion',prefix='ai_doll_companion:';
function find(node,text) {
  if(node.type==='Button'&&node.props.text===text)return node;
  for(const child of node.children||[]){const value=find(child,text);if(value)return value;}
}
function findField(node,label){if(node.type==='TextField'&&(!label||node.props.label===label))return node;for(const child of node.children||[]){const found=findField(child,label);if(found)return found;}}
async function test(ui) {
  const f=fixture();await f.prepare();const calls=[];
  const context={exports:{},console,NativeInterface:{},toolCall:async(name,p)=>{
    calls.push(name);
    if(!name.startsWith(prefix))throw Error('Tool not found '+name);
    return f.invoke(name.slice(prefix.length),p);
  }};
  vm.createContext(context);vm.runInContext(bridge,context,{filename:'official-context-1.12.2.js'});
  vm.runInContext(ui,context,{filename:'settings.ui.js'});
  const bundle=context.OperitComposeDslRuntime.createContext({packageName:container});
  const fallback=await bundle.ctx.resolveToolName({packageName:container,subpackageId:'ai_doll_companion',toolName:'list_chats'});
  assert.equal(fallback,container+':list_chats','published fallback reproduces the user error');
  bundle.state.page='chat';
  let tree=await context.exports.default(bundle.ctx);
  await bundle.invokeAction(find(tree,'选择已有聊天').props.onClick.__actionId);
  return {bundle,context,tree,calls,f};
}
(async()=>{
  const previous=source.replace("ctx.callTool('ai_doll_companion:'+name,params)",
    "ctx.callTool(await ctx.resolveToolName({packageName:'org.ai_doll.companion',subpackageId:'ai_doll_companion',toolName:name}),params)");
  const bad=await test(previous);
  assert.ok(bad.bundle.state.message.includes('Tool not found org.ai_doll.companion:list_chats'));
  const good=await test(source);
  good.bundle.state.page='home';good.bundle.state.loaded=false;
  let home=await good.context.exports.default(good.bundle.ctx);
  assert.ok(find(home,'发送诊断消息（可选）'),'diagnostic remains optional and accessible');
  assert.ok(!find(home,'② 我已看到自检输入和回复'),'normal startup does not require manual confirmation');
  function collect(node,type){return [node,...(node.children||[]).flatMap(c=>collect(c,type))].filter(n=>n.type===type);}
  const originalStatus=good.bundle.state.status;
  good.bundle.state.status={...originalStatus,job:{kind:'sync',phase:'running'},continuous_enabled:false};
  let syncHome=await good.context.exports.default(good.bundle.ctx);
  assert.ok(collect(syncHome,'Text').some(n=>n.props.text==='已关闭'));
  assert.ok(!collect(syncHome,'Text').some(n=>n.props.text==='正在陪伴'),'record-only collection is not active touch feedback');
  good.bundle.state.status={...originalStatus,job:{kind:'interaction',phase:'failed'},continuous_enabled:false};
  syncHome=await good.context.exports.default(good.bundle.ctx);
  assert.ok(collect(syncHome,'Text').some(n=>n.props.text==='需要检查连接'),'interaction failures remain visible');
  good.bundle.state.status=originalStatus;
  for(const c of collect(home,'Card')){
    assert.equal(c.props.containerColor.__colorToken,'surfaceContainer');
    assert.equal(c.props.contentColor.__colorToken,'onSurface');
  }
  for(const t of collect(home,'Text'))assert.ok(t.props.color?.__colorToken,'text uses native theme colors in light and dark modes');
  const touchSwitch=collect(home,'Switch')[0];assert.equal(touchSwitch.props.enabled,true,'configured chat can start without a diagnostic');
  assert.ok(home.props.onLoad?.__actionId,'native mount triggers live refresh');
  await good.bundle.invokeAction(home.props.onLoad.__actionId);
  assert.equal(good.bundle.state.status.connection_state,'device_offline');
  assert.equal(good.f.messages.length,0,'automatic check sends no chat message');
  const before=good.f.calls.length;
  home=await good.context.exports.default(good.bundle.ctx);
  assert.equal(good.f.calls.length,before,'rerender does not loop into repeated network checks');
  good.f.options.tool=async(name,a)=>name==='query_device_history'?{
    events:[{id:1,body_part:'头顶',phase:'start',source:'sensor',channel:0,at:1700000000}],has_more:false,next_cursor:1
  }:name==='get_device_overview'?{online:true}:{};
  home=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(home,'查看互动记录').props.onClick.__actionId);
  assert.equal(good.bundle.state.page,'history');assert.equal(good.bundle.state.history.events.length,1);
  const historyTree=await good.context.exports.default(good.bundle.ctx);
  assert.ok(collect(historyTree,'Text').some(n=>n.props.text==='头顶 · 按下'),'history is a readable page, not the top status message');
  const historyCalls=[],previousTool=good.f.options.tool,previousStatus=good.bundle.state.status;
  good.f.options.tool=async(name,args)=>{
    if(name!=='query_device_history')return previousTool(name,args);
    historyCalls.push({...args});
    return {events:[{id:args.after+1,body_part:'头顶',phase:'start',source:'sensor',channel:0,at:1700000000}],
      has_more:args.date==='unknown'&&args.after===0,next_cursor:args.after+1};
  };
  good.bundle.state.historyDate=' 2026－10－28 ';
  let dateHistory=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(dateHistory,'按日期查询').props.onClick.__actionId);
  assert.equal(historyCalls.at(-1).date,'2026-10-28','Chinese full-width hyphens become canonical before querying');
  assert.equal(good.bundle.state.historyDate,'2026-10-28');
  good.bundle.state.status={...previousStatus,connection:{...previousStatus.connection,mode:'phone'}};
  dateHistory=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(dateHistory,'查看时间未确认的记录').props.onClick.__actionId);
  good.bundle.state.historyDate='2026-10-01'; // Editing the field does not change the active page's filter.
  dateHistory=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(dateHistory,'加载下一页').props.onClick.__actionId);
  assert.equal(historyCalls.at(-1).date,'unknown','unknown-time pagination must keep its original filter');
  assert.equal(historyCalls.at(-1).after,1);
  good.f.options.tool=previousTool;good.bundle.state.status=previousStatus;good.bundle.state.historyDate='';
  good.bundle.state.page='home';
  home=await good.context.exports.default(good.bundle.ctx);
  const batchButton=collect(home,'Button').find(n=>n.props.text.startsWith('触摸合并：'));
  await good.bundle.invokeAction(batchButton.props.onClick.__actionId);
  let batching=await good.context.exports.default(good.bundle.ctx);
  const waitField=findField(batching,'停止按压后等待（秒）');
  await good.bundle.invokeAction(waitField.props.onValueChange.__actionId,{__composeTextFieldPayload:true,value:'2.5'});
  batching=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(batching,'保存等待时间').props.onClick.__actionId);
  assert.equal(good.f.cfg().response_wait_sec,2.5);
  good.f.options.tool=null;
  good.bundle.state.page='chat';
  assert.equal(good.bundle.state.chats.length,2);
  assert.ok(good.calls.every(name=>name.startsWith(prefix)));
  let tree=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(tree,'另一个聊天').props.onClick.__actionId);
  tree=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(tree,'确认绑定：另一个聊天').props.onClick.__actionId);
  assert.equal(good.f.cfg().chat.id,'chat-2');
  good.bundle.state.page='settings';
  tree=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(tree,'一键检查').props.onClick.__actionId);
  assert.ok(good.bundle.state.message.includes('检查通过'));
  assert.ok(good.calls.includes(prefix+'status')&&good.calls.includes(prefix+'list_chats')&&
    good.calls.includes(prefix+'bind_chat')&&good.calls.includes(prefix+'check_connection'));
  tree=await good.context.exports.default(good.bundle.ctx);
  good.bundle.state.page='connection';tree=await good.context.exports.default(good.bundle.ctx);
  const address=findField(tree,'电脑 IP（电脑重启后可修改）');
  assert.equal(address.props.value,'192.168.1.20');
  await good.bundle.invokeAction(address.props.onValueChange.__actionId,{__composeTextFieldPayload:true,value:'192.168.1.30'});
  tree=await good.context.exports.default(good.bundle.ctx);
  const binding=good.f.cfg().binding;
  await good.bundle.invokeAction(find(tree,'检查并保存电脑 IP').props.onClick.__actionId);
  assert.equal(good.f.cfg().connection.mcp_url.split('/')[2],'192.168.1.30:8775');
  assert.equal(good.f.cfg().binding,binding);
  assert.ok(good.bundle.state.message.includes('聊天绑定与发送记录保留'));
  tree=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(tree,'仅用安卓手机').props.onClick.__actionId);
  tree=await good.context.exports.default(good.bundle.ctx);
  const field=findField(tree,'设备家庭 IP');
  assert.equal(field.props.label,'设备家庭 IP');
  assert.ok(!findField(tree,'电脑 IP（电脑重启后可修改）'),'phone and computer addresses are distinct modes');
  await good.bundle.invokeAction(field.props.onValueChange.__actionId,{__composeTextFieldPayload:true,value:'192.168.1.50'});
  assert.equal(good.bundle.state.deviceHost,'192.168.1.50');
  good.bundle.state.page='duration';tree=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(tree,'15 分钟陪伴').props.onClick.__actionId);
  assert.equal(good.f.cfg().duration_sec,900);
  await good.f.invoke('schedule',{kind:'probe'});
  good.bundle.state.page='settings';good.bundle.state.loaded=false;
  tree=await good.context.exports.default(good.bundle.ctx);
  const stop=find(tree,'停止后台任务');assert.ok(stop&&stop.props.enabled,'settings always exposes stop, including pending probes');
  await good.bundle.invokeAction(stop.props.onClick.__actionId);
  assert.equal(good.f.job().phase,'stopped');assert.equal(good.f.messages.length,0);
  assert.ok(good.bundle.state.message.includes('可以修改设置'));
  console.log('PASS official Operit 1.12.2 UI bridge: old namespace failure reproduced; actual UI lists chats, confirms binding and checks MCP through exact subpackage names. Android/model remain unverified.');
})().catch(e=>{console.error(e);process.exitCode=1;});
