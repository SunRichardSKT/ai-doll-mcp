// Default: explicit Compose/Android doubles. --upstream [directory] exercises
// the cached official Operit 1.12.2 context bridge without adding build deps.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {fixture}=require('./operit_test_host.cjs');
const root=path.resolve(__dirname,'..'),prefix='ai_doll_companion:';
function find(node,text){if(node.type==='Button'&&node.props.text===text)return node;for(const child of node.children||[]){const match=find(child,text);if(match)return match;}}
function basicContext(context){
 const state={},refs={},actions=new Map();let count=0;
 const props=value=>Object.fromEntries(Object.entries(value||{}).map(([k,v])=>{
  if(typeof v==='function'){const id='action-'+ ++count;actions.set(id,v);return [k,{__actionId:id}];}return [k,v];
 }));
 const ctx={UI:new Proxy({},{get:(_,type)=>(p,children=[])=>({type,props:props(p),children})}),
  useState:(key,value)=>{if(!(key in state))state[key]=value;return [state[key],v=>{state[key]=v;}];},
  useRef:(key,value)=>refs[key]||(refs[key]={current:value}),callTool:context.toolCall,
  openFilePicker:options=>new Promise((resolve,reject)=>context.NativeInterface.composeOpenFilePickerSuspend(JSON.stringify({options}),(r,e)=>e?reject(r):resolve(r.data))),
  createWebViewController:key=>({key,evaluateJavascript:script=>new Promise((resolve,reject)=>
   context.NativeInterface.composeWebViewControllerCommandSuspend(JSON.stringify({command:'evaluateJavascript',key,payload:{script}}),(r,e)=>e?reject(r):resolve(r.data)))})};
 return {ctx,state,invokeAction:(id,payload)=>actions.get(id)(payload)};
}
(async()=>{
 const id='fixture-ui-pairing-device',token='fixture_ui_pairing_token_225';
 const f=fixture({realTime:true,tool:async name=>name==='doll_get_status'?{device_id:id,device_name:'同手机娃娃',hostname:'ai-doll-000000000002.local',ip:'192.168.1.26',boot_id:'fixture-boot',event_cursor:0,
  remote_server:{enabled:false}}:name==='get_channel_config'?{channels:[]}:name==='read_channel_values'?{values:[]}:{ok:true}});
 if(!f.tools.Files.list)f.tools.Files.list=async()=>({entries:[]});
 const http=f.tools.Net.http;
 f.tools.Net.http=async p=>p.method==='GET'?{statusCode:200,content:JSON.stringify(p.url.endsWith('/api/setup')?{enabled:true,token}:
  {device_id:id,hostname:'ai-doll-000000000002.local',ip:'192.168.1.26'})}:http(p);
 const returned=[],pickers=[];let picked={cancelled:true},pendingPicker=null,readerState={state:'ready'},reads=0,replyCode=null;
 const qr=f.load(path.join(root,'clients/operit/core/qr.js')),qrModule={...qr,html:()=>require('../clients/operit/core/qr.js').html({
  decoder:fs.readFileSync(path.join(root,'clients/operit/vendor/jsQR.js'),'utf8'),generator:fs.readFileSync(path.join(root,'clients/operit/vendor/qrcodegen.js'),'utf8')})};
 f.tools.Files.readBinary=async()=>({contentBase64:'iVBORw0KGgo='});
 const context={exports:{},console,NativeInterface:{},require:name=>{
  assert.equal(name,'../core/qr.js');return qrModule;
 },toolCall:async(name,args)=>{
  assert.ok(name.startsWith(prefix));const result=await f.invoke(name.slice(prefix.length),args);returned.push({name,result});return result;
 }};
 const callback=(target,result)=>typeof target==='function'?target(result,false):context[target](result,false);
 context.NativeInterface.composeOpenFilePickerSuspend=(raw,target)=>{
  pickers.push(JSON.parse(raw).options);
  if(picked==='pending'){pendingPicker=()=>callback(target,{success:true,data:{files:[{path:'/late.png'}]}});return;}
  callback(target,{success:true,data:picked});
 };
 context.NativeInterface.composeWebViewControllerCommandSuspend=(raw,target)=>{
  const {payload}=JSON.parse(raw),script=payload.script;
  if(script.includes('.start(')){const [data,id]=JSON.parse('['+script.slice(script.indexOf('.start(')+7,-1)+']');readerState={state:'loading',id};reads=0;}
  else if(script.includes('.cancel('))readerState={state:'cancelled'};
  else if(script.includes('.state()')&&++reads>=2&&replyCode)readerState={state:'done',id:readerState.id,text:replyCode};
  callback(target,{success:true,data:JSON.stringify(script.includes('.state()')?readerState:true)});
 };
 vm.createContext(context);
 const upstream=process.argv.indexOf('--upstream');
 if(upstream>=0){const directory=process.argv[upstream+1]||path.join(root,'build/integration-research/operit-1.12.2/runtime');
  vm.runInContext(fs.readFileSync(path.join(directory,'context.js'),'utf8'),context);
 }
 vm.runInContext(fs.readFileSync(path.join(root,'clients/operit/ui/settings.ui.js'),'utf8'),context);
 const bundle=upstream>=0?context.OperitComposeDslRuntime.createContext({packageName:'org.ai_doll.companion'}):basicContext(context);
 let tree=await context.exports.default(bundle.ctx);
 await bundle.invokeAction(find(tree,'添加娃娃').props.onClick.__actionId);
 tree=await context.exports.default(bundle.ctx);assert.ok(find(tree,'读取热点设备'));
 await bundle.invokeAction(find(tree,'读取热点设备').props.onClick.__actionId);
 tree=await context.exports.default(bundle.ctx);
 assert.equal(f.cfg().connection,null,'hotspot draft leaves the current connection unchanged');
 assert.equal(JSON.stringify(returned.find(x=>x.name.endsWith('read_hotspot_pairing')).result).includes(token),false);
 await bundle.invokeAction(find(tree,'打开热点设置，配置家庭 Wi-Fi').props.onClick.__actionId);
 tree=await context.exports.default(bundle.ctx);assert.ok(find(tree,'返回配对向导'));
 await bundle.invokeAction(find(tree,'返回配对向导').props.onClick.__actionId);
 tree=await context.exports.default(bundle.ctx);
 await bundle.invokeAction(find(tree,'已切回家庭 Wi-Fi，完成配对').props.onClick.__actionId);
 assert.equal(f.cfg().connection.device_id,id);assert.equal(f.cfg().auto_sync_enabled,true);
 assert.equal(f.cfg().chat,null,'pairing does not create a different chat');assert.equal(f.messages.length,0);
 tree=await context.exports.default(bundle.ctx);assert.ok(find(tree,'立即同步记录'));
 assert.ok(find(tree,'选择原聊天'),'the existing chat picker is still the next optional setup step');
 const original=f.disk.get('/managed/settings.json');
 bundle.state.page='connection';tree=await context.exports.default(bundle.ctx);
 await bundle.invokeAction(find(tree,'拍照／相册读取连接二维码').props.onClick.__actionId);
 tree=await context.exports.default(bundle.ctx);
 const web=tree.children.find(node=>node.type==='WebView');assert.ok(web?.props.html.includes('window.aiDollQR'));
 await bundle.invokeAction(web.props.onPageFinished.__actionId);tree=await context.exports.default(bundle.ctx);
 await bundle.invokeAction(find(tree,'从相册选择二维码').props.onClick.__actionId);
 assert.equal(f.disk.get('/managed/settings.json'),original,'cancelled Android picker never commits a connection');
 picked={files:[{path:'/fixture.png'}]};replyCode='not a connection code';
 tree=await context.exports.default(bundle.ctx);
 await bundle.invokeAction(find(tree,'拍照读取二维码').props.onClick.__actionId);
 assert.equal(f.disk.get('/managed/settings.json'),original,'decoded invalid connection preserves saved state');
 assert.match(bundle.state.message,/未识别/);
 replyCode=f.load(path.join(root,'clients/operit/core/pairing.js')).encode({schema:1,kind:'ai-doll-device-connection',mode:'phone',
  device_id:id,hostname:'ai-doll-000000000002.local',mcp_url:'http://192.168.1.26/mcp',token,label:'同手机娃娃'});
 tree=await context.exports.default(bundle.ctx);
 await bundle.invokeAction(find(tree,'从相册选择二维码').props.onClick.__actionId);
 assert.equal(bundle.state.page,'home');assert.equal(f.cfg().connection.device_id,id);assert.equal(f.cfg().binding,JSON.parse(original).binding);
 assert.ok(pickers.some(x=>x.picker==='camera')&&pickers.some(x=>x.picker==='image'));
 bundle.state.page='qr';bundle.state.qrReady=true;tree=await context.exports.default(bundle.ctx);
 picked='pending';const late=bundle.invokeAction(find(tree,'从相册选择二维码').props.onClick.__actionId);
 assert.ok(pendingPicker);const beforeCancel=f.disk.get('/managed/settings.json');
 await bundle.invokeAction(find(tree,'取消并返回连接').props.onClick.__actionId);pendingPicker();await late;
 assert.equal(bundle.state.page,'connection');assert.equal(f.disk.get('/managed/settings.json'),beforeCancel,'late picker result cannot commit after leaving QR');
 console.log('PASS: '+(upstream>=0?'official Operit 1.12.2 bridge':'explicit Compose double')+' hotspot→settings→home; camera/album cancellation, async QR validation, invalid candidate and late result preserve connection. Android/model remain unverified.');
})().catch(error=>{console.error(error.stack||error);process.exitCode=1});
