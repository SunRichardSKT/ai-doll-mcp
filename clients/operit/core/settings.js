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
function id() { return Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,12); }
async function config() {
  const saved=await read('settings.json');
  if (saved) {
    if (saved.schema!==1 || typeof saved.installation!=='string' || !saved.workflows)
      throw Error('配置版本无法识别，原文件保留。请导出诊断后更新工具包。');
    return saved;
  }
  const value={schema:1,installation:id(),connection:null,chat:null,binding:null,
    workflows:{},duration_sec:60,background_verified:false};
  await write('settings.json',value);
  return value;
}
function parameters(cfg) {
  if (!cfg.connection || !cfg.chat || !cfg.binding) throw Error('请先导入电脑连接，并绑定已有聊天。');
  return {mcp_url:cfg.connection.mcp_url,connection:cfg.connection,chat_id:cfg.chat.id,
    state_path:path('delivery_'+cfg.binding+'.json'),workflow_confirmed:true,duration_sec:cfg.duration_sec};
}
function validateConnection(value) {
  if (!value || value.schema!==1 || value.kind!=='ai-doll-operit-connection' ||
      typeof value.mcp_url!=='string' || !/^https?:\/\/[^\s?#@]+\/[^\s?#]*mcp$/.test(value.mcp_url))
    throw Error('请选择管理中心导出的 AI Doll 连接 JSON，不是工作流或诊断文件。');
  // Do not import paths, chat IDs, model credentials, workflow instructions or outputs.
  return {schema:1,kind:value.kind,mcp_url:value.mcp_url,
    mode:['simulation','server'].includes(value.mode)?value.mode:'device',label:String(value.label||'AI Doll').slice(0,80)};
}
async function noRunningJob() {
  const job=await read('job.json');
  if (job && ['scheduled','running','stopping'].includes(job.phase))
    throw Error('请先停止当前后台任务，再更改连接、绑定或开始新任务。');
}
exports.read=read; exports.write=write; exports.config=config; exports.path=path;
exports.id=id; exports.parameters=parameters; exports.validateConnection=validateConnection;
exports.noRunningJob=noRunningJob;
