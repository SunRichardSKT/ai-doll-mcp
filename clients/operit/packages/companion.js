/* METADATA
{
  "name":"ai_doll_companion",
  "enabledByDefault":true,
  "version":"2.20.0",
  "description":"AI Doll 统一入口。配置与启动请使用工具箱的 AI Doll 面板；不从目标聊天递归等待或发送。",
  "category":"NETWORK",
  "tools":[
    {"name":"status","description":"查看连接、聊天绑定和后台任务状态，不发送消息。","parameters":[]},
    {"name":"setup","description":"设置面板导入连接文件，一次保存。","parameters":[{"name":"connection_file","type":"string","required":false,"description":"系统选择器提供的本地文件"},{"name":"connection_json","type":"string","required":false,"description":"管理中心导出的连接 JSON"}]},
    {"name":"list_chats","description":"列出已有聊天，让用户按标题选择绑定。","parameters":[]},
    {"name":"view_history","description":"用户查看互动记录时读取一页历史，不向原聊天发送。","parameters":[]},
    {"name":"setup_device","description":"在面板连接家庭网络的设备，仅安卓手机模式，不更改采样或校准。","parameters":[{"name":"host","type":"string","required":true,"description":"设备家庭局域网 IP"},{"name":"token","type":"string","required":false,"description":"可选设备 MCP 令牌"}]},
    {"name":"set_experience","description":"用户在面板选择触摸回应开关与互动时长。","parameters":[{"name":"enabled","type":"boolean","required":false,"description":"主动回应和聊天融入"},{"name":"duration_sec","type":"number","required":false,"description":"60 或 900 秒"}]},
    {"name":"bind_chat","description":"仅在用户选择聊天标题后保存绑定。","parameters":[{"name":"chat_id","type":"string","required":true,"description":"设置页用户选中的聊天"}]},
    {"name":"check_connection","description":"一键检查文件、已有聊天与真实 MCP 工具发现，不发送消息。","parameters":[]},
    {"name":"import_legacy_state","description":"升级时由用户选择旧发送记录；核对原聊天与连接后导入，不删除旧文件。","parameters":[{"name":"legacy_file","type":"string","required":true,"description":"系统文件选择器提供的旧 JSON 文件"}]},
    {"name":"schedule","description":"仅设置面板的用户按钮使用，安排独立有限后台任务并立即返回；禁止从 AI 工具轮启动。","parameters":[{"name":"kind","type":"string","required":true,"description":"probe 或 interaction"}]},
    {"name":"stop","description":"停止本插件任务，保留尚未确认的发送记录。","parameters":[]},
    {"name":"confirm_probe","description":"用户在原聊天看到自检输入和回复后确认；仅记录用户确认，不冒充宿主显示证明。","parameters":[]},
    {"name":"recover","description":"用户核对原聊天后恢复，不立即生成新回复。","parameters":[{"name":"decision","type":"string","required":true,"description":"delivered、not_sent 或 discard"}]},
    {"name":"run_task","description":"内部工作流节点；需要匹配已保存的短期任务，不接受聊天地址等手工参数。","parameters":[{"name":"job_id","type":"string","required":true,"description":"内部任务编号"}]}
  ]
}
*/
const store=require('../core/settings.js'),flows=require('../core/workflows.js');
const interaction=require('../core/interaction.js'),probe=require('../core/probe.js');
async function refreshJob() {
  const job=await store.read('job.json');
  if (job?.phase==='scheduled' && Date.now()>job.expires_at) {
    job.phase='expired'; await store.write('job.json',job);
  }
  if (job?.phase==='running' && Date.now()>job.worker_deadline) {
    job.phase='interrupted'; await store.write('job.json',job);
  }
  return job;
}
async function status() {
  const cfg=await store.config(),job=await refreshJob();
  const journal=cfg.binding?await store.read('delivery_'+cfg.binding+'.json'):null;
  return {configured:!!cfg.connection,connection:cfg.connection?{label:cfg.connection.label,mode:cfg.connection.mode}:null,
    chat:cfg.chat,background_user_confirmed:cfg.background_verified===cfg.binding,
    duration_sec:cfg.duration_sec,job,uncertain_delivery:journal?.pending?.phase==='sending',
    display_verified:false,storage_managed:true};
}
async function setup(p) {
  await refreshJob(); await store.noRunningJob();
  let text=p.connection_json;
  if (p.connection_file) {
    // Document picker returns a copied local file. Directory content URIs are
    // never converted into fake absolute Android paths.
    if (typeof p.connection_file!=='string' || !p.connection_file.startsWith('/') || p.connection_file.includes('..'))
      throw Error('请选择连接文件，不是文件夹。');
    text=(await Tools.Files.read({path:p.connection_file,environment:'android'})).content;
  }
  if (typeof text!=='string' || text.length>16384) throw Error('未取得连接文件。');
  const connection=store.validateConnection(JSON.parse(text)),cfg=await store.config();
  // Connectivity check before replacing any saved connection.
  const tool=await interaction.connect(connection.mcp_url);
  await tool('get_installation_status');
  if (cfg.connection?.mcp_url!==connection.mcp_url) {
    cfg.binding=store.id(); cfg.background_verified=false;cfg.probe_file=null;
  }
  cfg.connection=connection;
  await store.write('settings.json',cfg);
  return {saved:true,label:connection.label,mode:connection.mode};
}
async function setup_device(p) {
  await refreshJob();await store.noRunningJob();
  const cfg=await store.config(),connection=await require('../core/device.js').pair(p.host,p.token,cfg.connection);
  if(cfg.connection?.kind!==connection.kind||cfg.connection?.device_id!==connection.device_id){
    cfg.binding=store.id();cfg.background_verified=false;cfg.probe_file=null;
  }
  cfg.connection=connection;await store.write('settings.json',cfg);
  return {saved:true,label:connection.label,mode:connection.mode,device_id:connection.device_id};
}
async function set_experience(p) {
  await refreshJob();
  if(p.enabled===false)await stop();
  await store.noRunningJob();
  if(p.duration_sec!==undefined&&![60,900].includes(p.duration_sec))throw Error('请选择 1 分钟或 15 分钟。');
  if(p.enabled!==undefined&&typeof p.enabled!=='boolean')throw Error('请明确选择开启或关闭。');
  const cfg=await store.config();
  let preferences;
  if(p.enabled!==undefined){
    if(!cfg.connection)throw Error('请先保存连接。');
    const tool=await interaction.connect(cfg.connection.mcp_url,cfg.connection);
    const result=await tool('update_companion_preferences',{changes:{chat_integration_enabled:true,proactive_enabled:p.enabled}});
    if(result.preferences?.proactive_enabled!==p.enabled||result.preferences?.chat_integration_enabled!==true)
      throw Error('回应开关未确认保存。');
    preferences=result.preferences;
  }
  if(p.duration_sec!==undefined){cfg.duration_sec=p.duration_sec;await store.write('settings.json',cfg);}
  return {saved:true,duration_sec:cfg.duration_sec,preferences};
}
async function list_chats() { return await Tools.Chat.listChats({limit:100,sort_by:'updatedAt',sort_order:'desc'}); }
async function view_history() {
  const cfg=await store.config();if(!cfg.connection)throw Error('请先保存连接。');
  const tool=await interaction.connect(cfg.connection.mcp_url,cfg.connection);
  return await tool('query_device_history',{limit:20});
}
async function bind_chat(p) {
  await refreshJob(); await store.noRunningJob();
  if (!p.chat_id || p.chat_id==='main') throw Error('请在已有聊天列表中选择。');
  const result=await Tools.Chat.findChat({query:p.chat_id,match:'exact',index:0});
  if (result.chat?.id!==p.chat_id) throw Error('该已有聊天未找到，未更改绑定。');
  const cfg=await store.config();
  if (cfg.chat?.id!==p.chat_id) {cfg.binding=store.id();cfg.background_verified=false;cfg.probe_file=null;}
  cfg.chat={id:p.chat_id,title:result.chat.title||'未命名聊天'};
  await store.write('settings.json',cfg);
  return {bound:true,chat:cfg.chat};
}
async function check_connection() {
  const cfg=await store.config(),p=store.parameters(cfg);
  const chat=await probe.inspect_chat({chat_id:p.chat_id});
  const tool=await interaction.connect(p.mcp_url,p.connection);
  const installation=await tool('get_installation_status');
  const overview=await tool('get_device_overview');
  await flows.ensure(cfg,'probe'); await flows.ensure(cfg,'interaction');
  return {files:true,chat,installation,overview,workflow_ready:true,
    background_user_confirmed:cfg.background_verified===cfg.binding,display_verified:false};
}
async function import_legacy_state(p) {
  await refreshJob(); await store.noRunningJob();
  const cfg=await store.config(),params=store.parameters(cfg);
  if (typeof p.legacy_file!=='string' || !p.legacy_file.startsWith('/') || p.legacy_file.includes('..'))
    throw Error('请用文件选择器选择旧发送记录。');
  const prior=JSON.parse((await Tools.Files.read({path:p.legacy_file,environment:'android'})).content);
  if (prior.schema!==1 || prior.chat_id!==params.chat_id || prior.mcp_url!==params.mcp_url ||
      (prior.pending && !['sending','completed'].includes(prior.pending.phase)))
    throw Error('旧记录不属于当前绑定的聊天和连接，未导入。');
  const target='delivery_'+cfg.binding+'.json';
  if (await store.read(target)) throw Error('新版已有发送记录，未覆盖；旧文件保留。');
  await store.write(target,prior);
  return {imported:true,uncertain_delivery:prior.pending?.phase==='sending',old_file_preserved:true};
}
async function schedule(p) {
  if (!['probe','interaction'].includes(p.kind)) throw Error('请选择连接自检或开始互动。');
  await refreshJob(); await store.noRunningJob();
  const cfg=await store.config(),params=store.parameters(cfg);
  const state=await store.read('delivery_'+cfg.binding+'.json');
  if (state?.pending) throw Error('有尚未确认的触摸发送。请核对原聊天后使用恢复按钮。');
  if (p.kind==='interaction' && cfg.background_verified!==cfg.binding)
    throw Error('请先运行原聊天自检，并在看到回复后点击“我已看到自检回复”。');
  const prior=cfg.probe_file?await store.read(cfg.probe_file):null;
  if (prior && prior.phase!=='completed') throw Error('上次自检结果不明确，请先核对原聊天并恢复。');
  if (p.kind==='interaction') {
    const tool=await interaction.connect(params.mcp_url,params.connection);
    const context=await tool('get_chat_context',{chat_id:params.chat_id,limit:1});
    if (!context.preferences?.proactive_enabled || !context.preferences.chat_integration_enabled)
      throw Error('请先在电脑反馈设置中明确开启主动回应和聊天融入。');
  }
  const job={schema:1,id:store.id(),binding:cfg.binding,kind:p.kind,phase:'scheduled',
    created_at:Date.now(),expires_at:Date.now()+90000,display_verified:false};
  if (p.kind==='probe') {
    job.probe_file='probe_'+cfg.binding+'_'+job.id+'.json';
    cfg.probe_file=job.probe_file;
    await store.write('settings.json',cfg);
  }
  await store.write('job.json',job);
  try {return {...await flows.schedule(cfg,p.kind,job),message:'任务已安排，请返回绑定聊天；手机调度可能延迟。'};}
  catch(error) {job.phase='failed';job.error=String(error.message||error);await store.write('job.json',job);throw error;}
}
async function run_task(p) {
  const cfg=await store.config(),job=await store.read('job.json');
  if (!job || job.id!==p.job_id || job.phase!=='scheduled' || job.binding!==cfg.binding || Date.now()>job.expires_at)
    throw Error('任务已结束、过期或不属于当前绑定，不会发送。');
  job.phase='running';job.worker_deadline=Date.now()+cfg.duration_sec*1000+125000;
  await store.write('job.json',job);
  const params=store.parameters(cfg);
  params.ensure_active=async()=>{
    const active=await store.read('job.json');
    if (active?.id!==job.id || active.phase!=='running') throw Error('任务已停止，不再发送新反馈。');
  };
  try {
    await params.ensure_active();
    const result=job.kind==='probe'?await probe.send_probe({...params,
      state_path:store.path(job.probe_file),timeout_sec:90}):await interaction.listen_interaction(params);
    const active=await store.read('job.json');
    if (active?.id===job.id && active.phase==='running') {
      job.phase=result.error?'failed':'completed';job.result=result;
      if (result.error) job.error=result.error;
      await store.write('job.json',job);
    }
    return result;
  } catch(error) {
    const active=await store.read('job.json');
    if (active?.id===job.id && active.phase==='running') {
      job.phase='failed';job.error=String(error.message||error);await store.write('job.json',job);
    }
    throw error;
  }
}
async function stop() {
  const cfg=await store.config(),job=await store.read('job.json');
  if (job && ['scheduled','running','stopping','interrupted'].includes(job.phase)) {
    job.phase='stopping';await store.write('job.json',job);
  }
  // Ending the owned server session prevents the next send, even if the Android
  // worker cannot be cancelled immediately. Never cancel a user's chat stream.
  let result={stopped:true},error=null;
  try {if (cfg.connection&&cfg.chat) result=await interaction.stop_interaction(store.parameters(cfg));}
  catch(e) {error=String(e.message||e);}
  try {await flows.disable(cfg);} catch(e) {error=error||String(e.message||e);}
  if (job) {job.phase=error?'stopping':'stopped';job.error=error;await store.write('job.json',job);}
  if (error) throw Error('停止仍待核对：'+error);
  return {...result,message:'已停止新事件投递；已提交给模型的回复可能仍完成，发送记录保留。'};
}
async function confirm_probe() {
  const cfg=await store.config(),journal=cfg.probe_file?await store.read(cfg.probe_file):null;
  if (!journal?.result?.probe_id) throw Error('请先运行一次原聊天自检。');
  // This is an explicit user report, not a host display receipt.
  cfg.background_verified=cfg.binding; await store.write('settings.json',cfg);
  journal.phase='completed';journal.user_confirmed=true;await store.write(cfg.probe_file,journal);
  return {user_reported_seen:true,display_verified:false};
}
async function recover(p) {
  if (!['delivered','not_sent','discard'].includes(p.decision)) throw Error('请选择核对结果。');
  await refreshJob();await store.noRunningJob();
  const cfg=await store.config(),params=store.parameters(cfg);
  const touch=await store.read('delivery_'+cfg.binding+'.json');
  if (touch?.pending) await interaction.reconcile_delivery({...params,decision:p.decision});
  const journal=cfg.probe_file?await store.read(cfg.probe_file):null;
  if (journal && journal.phase!=='completed') {
    journal.phase='completed';journal.user_decision=p.decision;
    await store.write(cfg.probe_file,journal);
  }
  return {recovered:true,automatic_retry:false,display_verified:false};
}
// Export plain functions for tests and tools. Native complete is called only at
// the public boundary, never from a shared engine that could end the wrong turn.
for (const [name,fn] of Object.entries({status,setup,setup_device,set_experience,view_history,list_chats,bind_chat,check_connection,schedule,
  stop,confirm_probe,recover,run_task,import_legacy_state})) exports[name]=async(p={})=>complete(await fn(p));
