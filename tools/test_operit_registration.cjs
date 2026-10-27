// Registration contract, separate from Android UI rendering and model delivery.
// --upstream points to extracted official 1.12.2 JS, cached only under build/.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),client=path.join(root,'clients/operit');
const main=fs.readFileSync(path.join(client,'main.js'),'utf8');
const manifest=JSON.parse(fs.readFileSync(path.join(client,'manifest.json'),'utf8'));
function placeholderContract(source,kind) {
  const captured=[],marker='ui/settings.ui.js';
  const Screen=()=>null;Screen.__operit_toolpkg_module_path=marker;
  const context={exports:{},require:()=>kind==='registration'?Screen:{default:Screen},
    ToolPkg:{registerToolboxUiModule:value=>{
      assert.equal(typeof value.screen,'function','screen reference must survive import');
      assert.equal(value.screen.__operit_toolpkg_module_path,marker);captured.push(value);
    }}};
  vm.runInNewContext(source,context,{filename:'main.js'});
  context.exports.registerToolPkg();assert.equal(captured.length,1);
}
function upstreamContract(source,directory) {
  let result,error;const captured=[];
  const native=new Proxy({}, {get:(_,name)=>{
    if(name==='readToolPkgTextResource')return(pkg,p)=>{
      const file=path.resolve(client,p);
      if(!file.startsWith(client+path.sep)||!fs.existsSync(file))return '';
      return fs.readFileSync(file,'utf8');
    };
    if(name==='setCallResult')return(id,value)=>{result=value;};
    if(name==='setCallError')return(id,value)=>{error=value;};
    if(name==='registerToolPkgToolboxUiModule')return value=>captured.push(JSON.parse(value));
    return ()=>'';
  }});
  const context={NativeInterface:native,setTimeout,clearTimeout};
  context.globalThis=context;context.window=context;vm.createContext(context);
  for(const name of ['expose.js','registry.js','api.js','registration.js','execution.js'])
    vm.runInContext(fs.readFileSync(path.join(directory,name),'utf8'),context,{filename:name});
  context.__operitExecuteScriptFunction('registration-test',{
    toolPkgId:manifest.toolpkg_id,__operit_ui_package_name:manifest.toolpkg_id,
    __operit_plugin_id:'registration-test',__operit_registration_mode:true,
    __operit_script_screen:manifest.main},source,'registerToolPkg',null,null,{apiVersion:manifest.api_version});
  return {result,error,captured};
}
const broken=main.replace("typeof screenModule === 'function' ? screenModule : screenModule.default",'screenModule.default');
assert.throws(()=>placeholderContract(broken,'registration'),/screen reference/,'reproduce the exact old import failure');
placeholderContract(main,'registration');placeholderContract(main,'execution');
const flag=process.argv.indexOf('--upstream');
if(flag>=0) {
  const directory=process.argv[flag+1];assert.ok(directory,'upstream directory required');
  const bad=upstreamContract(broken,directory);
  assert.ok(bad.error?.includes('requires a serializable screen reference'),'official runtime reproduces old failure');
  const good=upstreamContract(main,directory);
  assert.equal(good.error,undefined,good.error);assert.equal(good.result,'true');
  assert.equal(good.captured[0]?.screen,'ui/settings.ui.js');
  assert.ok(fs.existsSync(path.join(client,good.captured[0].screen)));
  console.log('PASS official Operit 1.12.2 JS registration runtime under Node: old error reproduced, corrected package accepted. Android installation still requires user test.');
} else console.log('PASS screen registration and CommonJS export contracts; previous entry fails this regression.');

// Exercise overlapping calls in the published runtime, including its cached
// module and ambient complete callback. Files and chats remain explicit doubles.
async function concurrentTools(source,directory){
  const f=require('./operit_test_host.cjs').fixture();await f.prepare();
  const results=new Map(),errors=new Map();
  let releaseRead,releaseChats,readEntered=false,chatsEntered=false;
  const readGate=new Promise(resolve=>{releaseRead=resolve;}),chatGate=new Promise(resolve=>{releaseChats=resolve;});
  const read=f.tools.Files.read;
  f.tools.Files.read=async p=>{if(p.path==='/managed/settings.json'&&!readEntered){readEntered=true;await readGate;}return read(p);};
  f.tools.Chat.listChats=async()=>{chatsEntered=true;await chatGate;return {chats:[{id:'chat-1',title:'原聊天'}]};};
  const native=new Proxy({}, {get:(_,name)=>{
    if(name==='readToolPkgTextResource')return(pkg,p)=>{
      const file=path.resolve(client,p);return file.startsWith(client+path.sep)&&fs.existsSync(file)?fs.readFileSync(file,'utf8'):'';
    };
    if(name==='getPluginConfigDir')return()=>'/managed';
    if(name==='setCallResult')return(id,value)=>results.set(id,JSON.parse(value));
    if(name==='setCallError')return(id,value)=>errors.set(id,JSON.parse(value));
    return()=>'';
  }});
  const context={NativeInterface:native,setTimeout,clearTimeout,Tools:f.tools};context.globalThis=context;context.window=context;vm.createContext(context);
  for(const name of ['expose.js','registry.js','api.js','registration.js','execution.js'])
    vm.runInContext(fs.readFileSync(path.join(directory,name),'utf8'),context,{filename:name});
  function start(id,name){context.__operitExecuteScriptFunction(id,{toolPkgId:manifest.toolpkg_id,
    __operit_script_screen:'packages/companion.js'},source,name,null,null,{apiVersion:manifest.api_version});}
  try{
    start('status-call','status');await new Promise(setImmediate);assert.ok(readEntered);
    start('chats-call','list_chats');await new Promise(setImmediate);assert.ok(chatsEntered);
    releaseRead();await new Promise(setImmediate);
    releaseChats();await new Promise(setImmediate);
    return {results,errors};
  }finally{releaseRead();releaseChats();}
}
if(flag>=0)(async()=>{
  const source=fs.readFileSync(path.join(client,'packages/companion.js'),'utf8');
  const corrected=source;
  const broken=corrected.replace('=>fn(p);','=>complete(await fn(p));');
  assert.notEqual(broken,corrected,'test must exercise the production returned-promise boundary');
  const bad=await concurrentTools(broken,process.argv[flag+1]);
  assert.equal(bad.results.get('chats-call')?.configured,true,'old completion delivers status to the concurrent chat-list call');
  assert.ok(!bad.results.has('status-call'),'old status call loses its result');
  const good=await concurrentTools(corrected,process.argv[flag+1]);
  assert.equal(good.errors.size,0,JSON.stringify([...good.errors]));
  assert.equal(good.results.get('status-call')?.configured,true);
  assert.equal(good.results.get('chats-call')?.chats[0].id,'chat-1');
  console.log('PASS official Operit 1.12.2 concurrent completion: previous result routing failure reproduced; returned promises stay with their own callers.');
})().catch(error=>{console.error(error);process.exitCode=1;});
