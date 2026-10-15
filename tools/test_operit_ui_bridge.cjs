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
  assert.equal(good.bundle.state.chats.length,2);
  assert.ok(good.calls.every(name=>name.startsWith(prefix)));
  let tree=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(tree,'另一个聊天').props.onClick.__actionId);
  tree=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(tree,'确认绑定：另一个聊天').props.onClick.__actionId);
  assert.equal(good.f.cfg().chat.id,'chat-2');
  tree=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(tree,'一键检查').props.onClick.__actionId);
  assert.ok(good.bundle.state.message.includes('检查通过'));
  assert.ok(good.calls.includes(prefix+'status')&&good.calls.includes(prefix+'list_chats')&&
    good.calls.includes(prefix+'bind_chat')&&good.calls.includes(prefix+'check_connection'));
  tree=await good.context.exports.default(good.bundle.ctx);
  await good.bundle.invokeAction(find(tree,'仅用安卓手机').props.onClick.__actionId);
  tree=await good.context.exports.default(good.bundle.ctx);
  const field=tree.children.find(n=>n.type==='TextField');
  assert.equal(field.props.label,'设备家庭 IP');
  await good.bundle.invokeAction(field.props.onValueChange.__actionId,{__composeTextFieldPayload:true,value:'192.168.1.50'});
  assert.equal(good.bundle.state.deviceHost,'192.168.1.50');
  await good.bundle.invokeAction(find(tree,'15 分钟陪伴').props.onClick.__actionId);
  assert.equal(good.f.cfg().duration_sec,900);
  console.log('PASS official Operit 1.12.2 UI bridge: old namespace failure reproduced; actual UI lists chats, confirms binding and checks MCP through exact subpackage names. Android/model remain unverified.');
})().catch(e=>{console.error(e);process.exitCode=1;});
