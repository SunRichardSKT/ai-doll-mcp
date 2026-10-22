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
async function read(name, fallback=null) {
  const file=path(name), state=await Tools.Files.exists(file,'android');
  if (typeof state.exists !== 'boolean' || state.isDirectory) throw Error('无法读取插件状态，请检查 Operit 文件权限。');
  if (!state.exists) return fallback;
  // Corrupt state must never be treated as a fresh install or replay permission.
  return JSON.parse((await Tools.Files.read({path:file,environment:'android'})).content);
}
async function write(name, value) {
  const parent=folder();
  const directory=await Tools.Files.exists(parent,'android');
  if (!directory.exists) {
    const result=await Tools.Files.mkdir(parent,true,'android');
    if (result.successful !== true) throw Error('无法创建插件数据目录，请授予 Operit 文件访问权限。');
  } else if (directory.isDirectory === false) throw Error('插件数据目录不是文件夹。');
  const result=await Tools.Files.write(path(name),JSON.stringify(value),false,'android');
  if (result.successful !== true) throw Error('设置未保存，请检查文件权限；不会继续发送。');
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
  const saved=await read('settings.json');
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
