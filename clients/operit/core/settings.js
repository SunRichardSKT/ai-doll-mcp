// One persistent location, independent of connection, chat selection or update.
const PLUGIN = 'org.ai_doll.companion';
function folder() {
  const value = typeof getPluginConfigDir === 'function' ? getPluginConfigDir(PLUGIN) :
    '/storage/emulated/0/Download/Operit/plugins/'+PLUGIN;
  if (typeof value !== 'string' || !value.startsWith('/') || value.includes('..'))
    throw Error('无法取得插件存储位置，请更新 Operit 并检查文件权限。');
  return value.replace(/\/$/,'');
}
function path(name) {
  if (!/^[a-zA-Z0-9_-]+\.json$/.test(name)) throw Error('Invalid internal filename');
  return folder()+'/'+name;
}
const critical=name=>name==='settings.json'||name==='job.json';
const writes=new Map();
function digest(value){
  const text=JSON.stringify(value);let hash=2166136261;
  for(let i=0;i<text.length;i++){hash^=text.charCodeAt(i);hash=Math.imul(hash,16777619);}
  return (hash>>>0).toString(16);
}
function valid(name,value){
  return value&&typeof value==='object'&&(name==='settings.json'?
    value.schema===1&&typeof value.installation==='string'&&value.workflows&&typeof value.workflows==='object':
    typeof value.id==='string'&&typeof value.phase==='string');
}
async function rawRead(name, fallback=null) {
  const file=path(name), state=await Tools.Files.exists(file,'android');
  if (typeof state.exists !== 'boolean' || state.isDirectory) throw Error('无法读取插件状态，请检查 Operit 文件权限。');
  if (!state.exists) return fallback;
  return JSON.parse((await Tools.Files.read({path:file,environment:'android'})).content);
}
function paused(value){return {...value,continuous_enabled:false,active_reply_requested:false,sync_paused:true,
  control_generation:Math.max(Date.now(),(value.control_generation||0)+1)};}
async function read(name,fallback=null){
  if(!critical(name))return await rawRead(name,fallback);
  const missing={};let value,error;
  try{value=await rawRead(name,missing);if(value!==missing&&!valid(name,value))throw Error('invalid state');}
  catch(e){error=e;}
  if(!error&&value!==missing)return value;
  const backupName=name.replace('.json','_backup.json');let backup,backupError;
  try{backup=await rawRead(backupName,missing);}catch(e){backupError=e;}
  if(backup?.schema===1&&valid(name,backup.data)&&backup.checksum===digest(backup.data)){
    // Never resume a task from a possibly older copy, even if it was running.
    const restored=name==='settings.json'?{...paused(backup.data),storage_recovery:'设置已从有效副本恢复，后台任务已暂停；请核对连接后重新开启。'}:
      {...backup.data,phase:'interrupted',error:'任务记录已恢复，请重新开启后台任务。'};
    if(error)await preserveDamaged(name);
    await rawWrite(name,restored);await verify(name,restored);
    if(name==='job.json')await pauseSettings();else await interruptJob();
    return restored;
  }
  if(!error&&value===missing&&backup===missing&&!backupError)return fallback;
  if(name==='job.json'){
    await pauseSettings();
    return {id:'storage-recovery',phase:'interrupted',error:'任务记录损坏，已暂停后台任务，原文件保留。'};
  }
  const failure=Error('设置及恢复副本无法读取。原记录保留；请重新导入连接并选择原聊天，后台任务不会自动恢复。');
  failure.storage_recovery=true;throw failure;
}
async function pauseSettings(){
  const cfg=await read('settings.json').catch(e=>{if(!e.storage_recovery)throw e;return null;});
  if(cfg){const value={...paused(cfg),storage_recovery:'任务记录损坏，后台任务已暂停；请核对后重新开启。'};
    await rawWrite('settings.json',value);await verify('settings.json',value);}
}
async function interruptJob(){
  let job;try{job=await rawRead('job.json');}catch(_){}
  if(job&&['scheduled','running','handoff','stopping'].includes(job.phase)){
    job={...job,phase:'interrupted',error:'设置恢复后已暂停任务，请核对连接后重新开启。'};
    await rawWrite('job.json',job);await verify('job.json',job);
  }
}
async function preserveDamaged(name){
  const state=await Tools.Files.exists(path(name),'android');
  if(state.exists){const text=(await Tools.Files.read({path:path(name),environment:'android'})).content;
    await rawWrite(name.replace('.json','_damaged_'+id()+'.json'),{original_file:name,content:text});}
}
async function rawWrite(name, value) {
  const parent=folder();
  const directory=await Tools.Files.exists(parent,'android');
  if (!directory.exists) {
    const result=await Tools.Files.mkdir(parent,true,'android');
    if (result.successful !== true) throw Error('无法创建插件数据目录，请授予 Operit 文件访问权限。');
  } else if (directory.isDirectory === false) throw Error('插件数据目录不是文件夹。');
  const result=await Tools.Files.write(path(name),JSON.stringify(value),false,'android');
  if (result.successful !== true) throw Error('设置未保存，请检查文件权限；不会继续发送。');
}
async function verify(name,value){
  if(JSON.stringify(await rawRead(name))!==JSON.stringify(value))throw Error('文件写入校验失败，未提交新的状态。');
}
async function write(name,value){
  if(!critical(name))return await rawWrite(name,value);
  if(!valid(name,value))throw Error('无法保存不完整的设置或任务。');
  value=JSON.parse(JSON.stringify(value));
  const previous=writes.get(name)||Promise.resolve();
  const next=previous.then(async()=>{
    let old;try{old=await rawRead(name);if(old!==null&&!valid(name,old))await preserveDamaged(name);}catch(_){await preserveDamaged(name);}
    const backupName=name.replace('.json','_backup.json');
    const backup=async data=>{const envelope={schema:1,data,checksum:digest(data)};await rawWrite(backupName,envelope);await verify(backupName,envelope);};
    if(valid(name,old))await backup(old);
    await rawWrite(name,value);await verify(name,value);
    await backup(value);
  });
  writes.set(name,next.catch(()=>{}));return await next;
}
async function checkedWrite(name,value){
  await write(name,value);
  if(JSON.stringify(await read(name))!==JSON.stringify(value))throw Error('归档写入校验失败，设备副本尚未确认。');
}
async function listNames(prefix=''){
  const listing=await Tools.Files.list(folder(),'android');
  if(!Array.isArray(listing.entries))throw Error('无法读取归档目录，设备副本尚未确认。');
  return listing.entries.filter(e=>!e.isDirectory&&typeof e.name==='string'&&e.name.startsWith(prefix)&&/^[a-zA-Z0-9_-]+\.json$/.test(e.name)).map(e=>e.name);
}
function id() { return Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,12); }
async function config() {
  let saved;
  try{saved=await read('settings.json');}catch(e){
    if(!e.storage_recovery)throw e;
    await interruptJob();
    // Recovery UI is usable, but this is not a new installation or permission to send.
    return {schema:1,installation:null,connection:null,chat:null,binding:null,workflows:{},duration_sec:60,
      response_wait_sec:1,continuous:false,continuous_enabled:false,auto_sync_enabled:false,sync_paused:true,
      recovery_required:true,storage_recovery:e.message};
  }
  if (saved) {
    if (saved.schema!==1 || typeof saved.installation!=='string' || !saved.workflows)
      throw Error('配置版本无法识别，原文件保留。请导出诊断后更新工具包。');
    return {...saved,auto_sync_enabled:saved.auto_sync_enabled??false,sync_paused:saved.sync_paused??false};
  }
  const value={schema:1,installation:id(),connection:null,chat:null,binding:null,
    workflows:{},duration_sec:60,response_wait_sec:1,continuous:false,continuous_enabled:false,background_verified:false,
    auto_sync_enabled:false,sync_paused:false};
  await write('settings.json',value);
  return value;
}
function parameters(cfg) {
  if (!cfg.connection || !cfg.chat || !cfg.binding) throw Error('请先连接娃娃，并选择已有聊天。');
  return {mcp_url:cfg.connection.mcp_url,connection:cfg.connection,chat_id:cfg.chat.id,
    state_path:path('delivery_'+cfg.binding+'.json'),workflow_confirmed:true,duration_sec:cfg.duration_sec,
    response_wait_sec:cfg.response_wait_sec??1};
}
function validateConnection(value) {
  if (!value || value.schema!==1 || value.kind!=='ai-doll-operit-connection' ||
      typeof value.mcp_url!=='string' || !/^https?:\/\/[^\s?#@]+\/[^\s?#]*mcp$/.test(value.mcp_url))
    throw Error('请选择管理中心导出的 AI Doll 连接 JSON，不是工作流或诊断文件。');
  // Do not import paths, chat IDs, model credentials, workflow instructions or outputs.
  return {schema:1,kind:value.kind,mcp_url:value.mcp_url,
    mode:['simulation','server'].includes(value.mode)?value.mode:'device',label:String(value.label||'AI Doll').slice(0,80),
    ...Object.fromEntries(['server_instance_id','pairing_id','expected_device_id'].filter(k=>typeof value[k]==='string').map(k=>[k,value[k]]))};
}
function sameConnection(a,b){
  if(!a||!b||a.kind!==b.kind)return false;
  if(a.kind==='ai-doll-device-connection')return a.device_id===b.device_id;
  if(a.mode==='server'&&b.mode==='server'&&a.server_instance_id&&a.pairing_id)
    return a.server_instance_id===b.server_instance_id&&a.pairing_id===b.pairing_id;
  return a.mcp_url===b.mcp_url||sameComputer(a.mcp_url,b);
}
function computerEndpoint(url) {
  return typeof url==='string'?url.match(/^(https?:\/\/)([^/:]+)(:\d+)?(\/[0-9a-f]{64}\/mcp)$/):null;
}
function sameComputer(url, connection) {
  if (connection?.kind!=='ai-doll-operit-connection'||!['device','simulation'].includes(connection.mode))return false;
  const previous=computerEndpoint(url),current=computerEndpoint(connection.mcp_url);
  // The private path identifies the same installation across DHCP changes.
  return !!(previous&&current&&previous[1]===current[1]&&previous[3]===current[3]&&previous[4]===current[4]);
}
function replaceComputerIP(connection, host) {
  if (!connection || connection.kind!=='ai-doll-operit-connection' || connection.mode==='server')
    throw Error('该入口用于已保存的电脑连接，请先导入电脑连接文件。');
  host=String(host||'').trim();
  const parts=host.split('.');
  if(parts.length!==4||parts.some(v=>!/^\d{1,3}$/.test(v)||Number(v)>255)||
     !((Number(parts[0])===10)||(Number(parts[0])===172&&Number(parts[1])>=16&&Number(parts[1])<=31)||
       (Number(parts[0])===192&&Number(parts[1])===168)))
    throw Error('请输入电脑当前的局域网 IPv4 地址，例如 192.168.1.20。');
  host=parts.map(Number).join('.');
  const match=computerEndpoint(connection.mcp_url);
  if(!match)throw Error('原电脑地址无法识别，请重新导入连接文件。');
  return {...connection,mcp_url:match[1]+host+(match[3]||'')+match[4]};
}
async function noRunningJob() {
  const job=await read('job.json');
  if (job && ['scheduled','running','handoff','stopping'].includes(job.phase))
    throw Error('请先停止当前后台任务，再更改连接、绑定或开始新任务。');
}
exports.read=read; exports.write=write; exports.config=config; exports.path=path;
exports.id=id; exports.parameters=parameters; exports.validateConnection=validateConnection;
exports.noRunningJob=noRunningJob;
exports.replaceComputerIP=replaceComputerIP;
exports.sameComputer=sameComputer;
exports.sameConnection=sameConnection;exports.checkedWrite=checkedWrite;exports.listNames=listNames;exports.folder=folder;
