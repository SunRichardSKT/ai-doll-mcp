/* METADATA
{
  "name":"ai_doll_companion",
  "enabledByDefault":true,
  "version":"2.25.3",
  "description":"AI Doll 统一入口。配置与启动请使用工具箱的 AI Doll 面板；不从目标聊天递归等待或发送。",
  "category":"NETWORK",
  "tools":[
    {"name":"update_computer_address","description":"用户修改电脑局域网 IP，检查后保存，保留聊天和发送记录。","parameters":[{"name":"host","type":"string","required":true,"description":"电脑当前局域网 IPv4"}]},
    {"name":"status","description":"查看连接、聊天绑定和后台任务状态；refresh时只读检查连接，不发送消息。","parameters":[{"name":"refresh","type":"boolean","required":false,"description":"是否刷新设备在线状态；省略时读取本机缓存"}]},
    {"name":"get_panel","description":"读取设置面板所需的端口、部位、人设与可访问设置入口，不发送消息。","parameters":[]},
    {"name":"update_port","description":"用户明确修改一个输入端口的关闭／模拟／已接入状态或部位，不修改阈值和其他端口。","parameters":[{"name":"channel","type":"number","required":true,"description":"已配置的输入端口编号，0到15"},{"name":"mode","type":"string","required":false,"description":"端口状态：off关闭、simulation模拟、connected已接入；省略时保留"},{"name":"name","type":"string","required":false,"description":"该端口对应的部位名称；省略时保留"}]},
    {"name":"set_persona_source","description":"用户选择当前聊天或娃娃人设；只影响身体互动反馈。","parameters":[{"name":"source","type":"string","required":true,"description":"人设来源：chat跟随原聊天，doll使用保存的娃娃人设"},{"name":"text","type":"string","required":false,"description":"用户设置的娃娃人设文本，最多4000字；省略时保留"}]},
    {"name":"diagnostics","description":"开发者只读诊断，不模拟事件或发送消息。","parameters":[]},
    {"name":"test_sensor","description":"用户点按测试后等待10秒真实按压，只读，不发送聊天或修改阈值。","parameters":[]},
    {"name":"setup","description":"设置面板导入连接文件，一次保存。","parameters":[{"name":"connection_file","type":"string","required":false,"description":"系统选择器提供的本地文件"},{"name":"connection_json","type":"string","required":false,"description":"管理中心导出的连接 JSON"}]},
    {"name":"read_hotspot_pairing","description":"读取当前设备热点的配对草稿，不改现有连接，不返回凭据。","parameters":[]},
    {"name":"finish_pairing","description":"切回家庭网络后核对热点草稿并提交连接。","parameters":[{"name":"candidate_id","type":"string","required":true,"description":"热点读取返回的草稿编号"}]},
    {"name":"import_connection_code","description":"导入设备或服务器连接码，验证成功后才保存。","parameters":[{"name":"connection_code","type":"string","required":true,"description":"连接码或JSON文本"}]},
    {"name":"set_record_sync","description":"设置手机自动同步记录；独立于触摸主动回复。","parameters":[{"name":"enabled","type":"boolean","required":true,"description":"是否在Operit任务运行时同步设备缓存"}]},
    {"name":"sync_now","description":"请求同步记录，不发送聊天；已有采集任务时复用。","parameters":[]},
    {"name":"list_chats","description":"列出已有聊天，让用户按标题选择绑定。","parameters":[]},
    {"name":"view_history","description":"读取互动记录页面，支持按日期和游标翻页，不发送消息。","parameters":[{"name":"date","type":"string","required":false,"description":"可选本地日期YYYY-MM-DD；省略为近期记录"},{"name":"after","type":"number","required":false,"description":"上一页next_cursor，首次0"},{"name":"limit","type":"number","required":false,"description":"每页1到100条，默认50"}]},
    {"name":"setup_device","description":"在面板连接家庭网络的设备，仅安卓手机模式，不更改采样或校准。","parameters":[{"name":"host","type":"string","required":true,"description":"设备家庭局域网 IP 或固件显示的固定 .local 连接名"},{"name":"token","type":"string","required":false,"description":"可选设备 MCP 令牌"}]},
    {"name":"set_experience","description":"设置陪伴方式与合并等待；连接和聊天已保存即可开启，无需发送测试。","parameters":[{"name":"enabled","type":"boolean","required":false,"description":"主动回应和聊天融入"},{"name":"duration_sec","type":"number","required":false,"description":"限时60或900秒"},{"name":"continuous","type":"boolean","required":false,"description":"是否常开"},{"name":"response_wait_sec","type":"number","required":false,"description":"停止按压后等待0到30秒合并回应；0立即触发，默认1"}]},
    {"name":"bind_chat","description":"仅在用户选择聊天标题后保存绑定。","parameters":[{"name":"chat_id","type":"string","required":true,"description":"设置页用户选中的聊天"}]},
    {"name":"check_connection","description":"一键检查文件、已有聊天与真实 MCP 工具发现，不发送消息。","parameters":[]},
    {"name":"import_legacy_state","description":"升级时由用户选择旧发送记录；核对原聊天与连接后导入，不删除旧文件。","parameters":[{"name":"legacy_file","type":"string","required":true,"description":"系统文件选择器提供的旧 JSON 文件"}]},
    {"name":"schedule","description":"仅设置面板的用户按钮使用，安排独立有限后台任务并立即返回；禁止从 AI 工具轮启动。","parameters":[{"name":"kind","type":"string","required":true,"description":"probe、interaction 或 sync"}]},
    {"name":"stop","description":"停止本插件任务，保留尚未确认的发送记录。","parameters":[]},
    {"name":"confirm_probe","description":"用户在原聊天看到自检输入和回复后确认；仅记录用户确认，不冒充宿主显示证明。","parameters":[]},
    {"name":"recover","description":"用户核对原聊天后恢复，不立即生成新回复。","parameters":[{"name":"decision","type":"string","required":true,"description":"delivered、not_sent 或 discard"}]},
    {"name":"run_task","description":"内部工作流节点；需要匹配已保存的短期任务，不接受聊天地址等手工参数。","parameters":[{"name":"job_id","type":"string","required":true,"description":"内部任务编号"}]}
  ]
}
*/
const store=require('../core/settings.js'),flows=require('../core/workflows.js');
const interaction=require('../core/interaction.js'),probe=require('../core/probe.js');
const controls=require('../core/controls.js');
const recovery=require('../core/recovery.js');
let activeWorker=null,continuationFlight=null;
async function refreshJob() {
  const job=await store.read('job.json');
  if (job?.phase==='scheduled' && Date.now()>job.expires_at) {
    job.phase='expired'; await store.write('job.json',job);
  }
  if (['running','handoff'].includes(job?.phase) && Date.now()>job.worker_deadline) {
    job.phase='interrupted'; await store.write('job.json',job);
  }
  return job;
}
async function status(p={}) {
  let cfg=await store.config();const job=await refreshJob();
  if(job?.phase==='interrupted')cfg=await store.config();
  const journal=cfg.binding?await store.read('delivery_'+cfg.binding+'.json'):null;
  const network=cfg.connection?.kind==='ai-doll-device-connection'?await store.read('device_'+cfg.connection.storage_key+'_network.json'):null;
  let panel=cfg.binding?await store.read('panel_'+cfg.binding+'.json'):null;
  if(p.refresh&&cfg.connection){
    try{panel=await controls.refreshOverview(cfg,panel||{});}
    catch(e){panel={...panel,connection_error:String(e.message||e),overview:{...panel?.overview,online:false},checked_at:Date.now()};await store.write('panel_'+cfg.binding+'.json',panel);}
  }
  return {configured:!!cfg.connection,connection:cfg.connection?{label:cfg.connection.label,mode:cfg.connection.mode,
    device_host:cfg.connection.kind==='ai-doll-device-connection'?(network?.hostname||cfg.connection.hostname||network?.ip||cfg.connection.mcp_url.replace(/^http:\/\//,'').split('/')[0]):null,
    computer_host:cfg.connection.kind==='ai-doll-operit-connection'&&cfg.connection.mode!=='server'?cfg.connection.mcp_url.match(/^https?:\/\/([^/:]+)/)?.[1]:null}:null,
    chat:cfg.chat,background_user_confirmed:cfg.background_verified===cfg.binding,
    probe_has_attempt:!!(job?.kind==='probe'&&job.result?.probe_id),
    panel,connection_state:!cfg.connection?'unconfigured':!panel?.checked_at?'checking':panel.connection_error?'unreachable':Date.now()-panel.checked_at>15000?'stale':panel.overview?.online?'online':'device_offline',
    queued_touches:(journal?.queue||[]).reduce((n,q)=>n+(q.events?.length||0),0),
    duration_sec:cfg.duration_sec,response_wait_sec:cfg.response_wait_sec??1,continuous:!!cfg.continuous,continuous_enabled:!!cfg.continuous_enabled,
    job,uncertain_delivery:journal?.pending?.phase==='sending',
    auto_sync_enabled:!!cfg.auto_sync_enabled,sync_paused:!!cfg.sync_paused,
    sync_state:cfg.connection?.kind==='ai-doll-device-connection'?await store.read('device_'+cfg.connection.storage_key+'_sync.json',{}):null,
    storage_recovery:cfg.storage_recovery||null,recovery_required:!!cfg.recovery_required,
    display_verified:false,storage_managed:true};
}
function wantsSync(cfg){return !!(cfg.connection?.kind==='ai-doll-device-connection'&&cfg.auto_sync_enabled&&!cfg.sync_paused&&!cfg.sync_identity_changed);}
async function commitConnection(connection){
  const cfg=await store.config(),same=store.sameConnection(cfg.connection,connection);
  if(cfg.recovery_required){cfg.installation=store.id();delete cfg.recovery_required;cfg.storage_recovery='连接已重新核对；请选择原聊天后再开启，原归档文件保留。';}
  if(!same){await refreshJob();await store.noRunningJob();if(cfg.continuous_enabled)throw Error('请先停止当前陪伴再更换设备。');}
  if(connection.kind==='ai-doll-device-connection')connection={...connection,storage_key:same?cfg.connection.storage_key:(connection.storage_key||store.id())};
  if(!same){if(cfg.connection)cfg.chat=null;cfg.binding=store.id();cfg.background_verified=false;cfg.probe_file=null;cfg.continuous_enabled=false;
    cfg.auto_sync_enabled=connection.kind==='ai-doll-device-connection';cfg.sync_paused=false;}
  cfg.sync_identity_changed=false;
  cfg.connection=connection;await store.checkedWrite('settings.json',cfg);
  let syncScheduled=false,syncError=null;
  if(wantsSync(cfg)){
    const active=await refreshJob();
    if(!active||!['scheduled','running','handoff'].includes(active.phase)){
      try{await schedule({kind:'sync'});syncScheduled=true;}catch(error){syncError=String(error.message||error);}
    }else syncScheduled=true;
  }
  return {saved:true,label:connection.label,mode:connection.mode,device_id:connection.device_id,
    chat_preserved:same,history_preserved:true,auto_sync_enabled:!!cfg.auto_sync_enabled,sync_scheduled:syncScheduled,sync_error:syncError};
}
async function setup(p) {
  let text=p.connection_json;
  if(p.connection_file){
    if(typeof p.connection_file!=='string'||!p.connection_file.startsWith('/')||p.connection_file.includes('..'))throw Error('请选择连接文件，不是文件夹。');
    text=(await Tools.Files.read({path:p.connection_file,environment:'android'})).content;
  }
  if(typeof text!=='string'||text.length>16384)throw Error('未取得连接文件。');
  const pairing=require('../core/pairing.js'),cfg=await store.config();
  return await commitConnection(await pairing.finish(pairing.parse(text),cfg.connection));
}
async function read_hotspot_pairing(){return await require('../core/pairing.js').readHotspot();}
async function finish_pairing(p){
  const cfg=await store.config();return await commitConnection(await require('../core/pairing.js').finish({candidate_id:p.candidate_id},cfg.connection));
}
async function import_connection_code(p){return await setup({connection_json:p.connection_code});}
async function setup_device(p) {
  const cfg=await store.config();return await commitConnection(await require('../core/device.js').pair(p.host,p.token,cfg.connection));
}
async function set_record_sync(p){
  if(typeof p.enabled!=='boolean')throw Error('请选择是否自动同步记录。');
  const cfg=await store.config();if(cfg.connection?.kind!=='ai-doll-device-connection')throw Error('自动同步用于手机直连；服务器自行保存设备上传记录。');
  cfg.auto_sync_enabled=p.enabled;cfg.sync_paused=false;if(p.enabled)delete cfg.storage_recovery;await store.checkedWrite('settings.json',cfg);
  const job=await refreshJob();
  if(p.enabled){if(!job||!['scheduled','running','handoff'].includes(job.phase))await schedule({kind:'sync'});}
  else if(job?.kind==='sync')await stopSyncOnly(cfg,job);
  return {saved:true,auto_sync_enabled:p.enabled,message:p.enabled?'自动同步已开启，手机任务运行时保存记录；不会发送聊天。':'自动同步已关闭，历史保留。'};
}
async function stopSyncOnly(cfg,job){
  if(job){job.phase='stopped';await store.write('job.json',job);}
  await flows.disable(cfg);
  try{const tool=await interaction.connect(cfg.connection.mcp_url,cfg.connection);await tool('_stop_record_sync');}catch(_){}
}
async function sync_now(){
  const cfg=await store.config();if(cfg.connection?.kind!=='ai-doll-device-connection')throw Error('服务器收到上传后会自动同步，可刷新设备状态。');
  const job=await refreshJob();
  if(job&&['scheduled','running','handoff'].includes(job.phase))return {scheduled:true,reused:true,message:'正在复用当前采集任务同步记录。'};
  cfg.sync_paused=false;delete cfg.storage_recovery;await store.write('settings.json',cfg);
  const once={schema:1,id:store.id(),binding:cfg.binding,kind:'sync',phase:'running',worker_deadline:Date.now()+30000};
  await store.write('job.json',once);
  try{
    const tool=await interaction.connect(cfg.connection.mcp_url,cfg.connection),result=await tool('_sync_records');
    once.phase='completed';await store.write('job.json',once);
    if(wantsSync(cfg))await continueListening(once);
    return {...result,message:'已读取并归档记录；离线补传不会发送聊天。'};
  }catch(error){once.phase='failed';once.error=String(error.message||error);await store.write('job.json',once);throw error;}
}
async function update_computer_address(p) {
  const cfg=await store.config(),connection=store.replaceComputerIP(cfg.connection,p.host);
  // Probe the candidate before touching jobs, binding or durable send receipts.
  const tool=await interaction.connect(connection.mcp_url,connection);
  await tool('get_installation_status');
  cfg.continuous_enabled=false;
  await store.write('settings.json',cfg);
  await flows.disable(cfg);
  const job=await refreshJob();
  if(job&&['scheduled','running','handoff','stopping','interrupted'].includes(job.phase)){
    job.phase='stopping';await store.write('job.json',job);
    // The same private path reaches the moved service. Stop only this chat's session.
    if(cfg.chat&&cfg.binding)await interaction.stop_interaction({...store.parameters(cfg),connection,mcp_url:connection.mcp_url});
    job.phase='stopped';job.error=null;await store.write('job.json',job);
  }
  cfg.connection=connection;await store.write('settings.json',cfg);
  return {saved:true,host:connection.mcp_url.match(/^https?:\/\/([^/:]+)/)[1],chat_preserved:true,delivery_preserved:true,
    message:'电脑地址已更新，聊天绑定与发送记录保留。可在原聊天重新开始互动。'};
}
async function set_experience(p) {
  await refreshJob();
  if(p.duration_sec!==undefined&&![60,900].includes(p.duration_sec))throw Error('请选择 1 分钟或 15 分钟。');
  if(p.enabled!==undefined&&typeof p.enabled!=='boolean')throw Error('请明确选择开启或关闭。');
  if(p.continuous!==undefined&&typeof p.continuous!=='boolean')throw Error('请明确选择常开或限时。');
  if(p.response_wait_sec!==undefined&&(!Number.isFinite(p.response_wait_sec)||p.response_wait_sec<0||p.response_wait_sec>30))throw Error('合并等待时间应为0～30秒。');
  const cfg=await store.config();
  if(cfg.continuous_enabled&&(p.continuous!==undefined||p.duration_sec!==undefined)&&p.enabled!==false)throw Error('请先关闭常开，再修改陪伴方式。');
  let preferences;
  if(p.enabled!==undefined){
    if(!cfg.connection)throw Error('请先保存连接。');
    if(!p.enabled){cfg.continuous_enabled=false;cfg.active_reply_requested=false;await store.write('settings.json',cfg);}
    const tool=await interaction.connect(cfg.connection.mcp_url,cfg.connection);
    const result=await tool('update_companion_preferences',{changes:{chat_integration_enabled:true,proactive_enabled:p.enabled}});
    if(result.preferences?.proactive_enabled!==p.enabled||result.preferences?.chat_integration_enabled!==true)throw Error('回应开关未确认保存。');
    preferences=result.preferences;
    if(!p.enabled){
      try{if(cfg.chat)await interaction.stop_interaction(store.parameters(cfg));}catch(_){}
      const job=await refreshJob();
      if(job?.kind==='interaction'){
        if(wantsSync(cfg)){job.kind='sync';job.continuous=true;await store.write('job.json',job);}
        else await stop();
      }
    }else {cfg.sync_paused=false;delete cfg.storage_recovery;}
  }
  if(p.duration_sec!==undefined)cfg.duration_sec=p.duration_sec;
  if(p.continuous!==undefined)cfg.continuous=p.continuous;
  if(p.response_wait_sec!==undefined)cfg.response_wait_sec=p.response_wait_sec;
  await store.write('settings.json',cfg);
  return {saved:true,duration_sec:cfg.duration_sec,response_wait_sec:cfg.response_wait_sec??1,continuous:!!cfg.continuous,preferences,
    auto_sync_enabled:!!cfg.auto_sync_enabled,message:p.enabled===false&&wantsSync(cfg)?'触摸主动回复已关闭，记录同步继续。':undefined};
}
async function list_chats() { return await Tools.Chat.listChats({limit:100,sort_by:'updatedAt',sort_order:'desc'}); }
async function view_history(p={}) {
  const cfg=await store.config();if(!cfg.connection)throw Error('请先保存连接。');
  const tool=await interaction.connect(cfg.connection.mcp_url,cfg.connection);
  const result=await tool('query_device_history',{...(p.date?{date:p.date}:{}),after:p.after??0,limit:p.limit??50});
  return {...result,events:result.events||[],has_more:!!result.has_more,next_cursor:result.next_cursor??p.after??0};
}
async function bind_chat(p) {
  const priorJob=await refreshJob();if(priorJob?.kind!=='sync')await store.noRunningJob();
  if (!p.chat_id || p.chat_id==='main') throw Error('请在已有聊天列表中选择。');
  const result=await Tools.Chat.findChat({query:p.chat_id,match:'exact',index:0});
  if (result.chat?.id!==p.chat_id) throw Error('该已有聊天未找到，未更改绑定。');
  const cfg=await store.config();
  if(cfg.continuous_enabled)throw Error('请先关闭常开，再更换聊天。');
  if (cfg.chat?.id!==p.chat_id) {cfg.binding=store.id();cfg.background_verified=false;cfg.probe_file=null;}
  cfg.chat={id:p.chat_id,title:result.chat.title||'未命名聊天'};
  await store.write('settings.json',cfg);
  if(priorJob?.kind==='sync'){priorJob.binding=cfg.binding;await store.write('job.json',priorJob);await flows.watchdog(cfg);}
  return {bound:true,chat:cfg.chat};
}
async function check_connection() {
  const cfg=await store.config(),p=store.parameters(cfg);
  const chat=await Tools.Chat.findChat({query:p.chat_id,match:'exact',index:0});
  if(chat.chat?.id!==p.chat_id)throw Error('原聊天未找到，请重新选择。');
  const snapshot=await controls.refreshOverview(cfg,await store.read('panel_'+cfg.binding+'.json')||{});
  const overview=snapshot.overview;
  await flows.ensure(cfg,'probe'); await flows.ensure(cfg,'interaction');
  return {files:true,chat,overview,workflow_ready:true,
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
  if (!['probe','interaction','sync'].includes(p.kind)) throw Error('请选择连接自检或开始互动。');
  const current=await refreshJob(),cfg=await store.config();
  if(current?.kind==='sync'&&['scheduled','running','handoff'].includes(current.phase)&&p.kind==='interaction'){
    store.parameters(cfg);
    const call=await interaction.connect(cfg.connection.mcp_url,cfg.connection),context=await call('get_chat_context',{chat_id:cfg.chat.id,limit:1});
    if(!context.preferences?.proactive_enabled||!context.preferences.chat_integration_enabled)throw Error('请先开启触摸主动回复。');
    const journal=await store.read('delivery_'+cfg.binding+'.json');
    if(journal?.pending?.phase==='sending')throw Error('上次发送结果尚未确认，请先核对原聊天并恢复。');
    cfg.active_reply_requested=true;
    if(cfg.continuous)cfg.continuous_enabled=true;await store.write('settings.json',cfg);
    current.kind='interaction';current.continuous=!!cfg.continuous;await store.write('job.json',current);
    return {state:current.phase,reused:true,message:'当前采集任务将接入原聊天陪伴，不会重复启动。'};
  }
  if(current?.kind==='sync'&&['scheduled','running','handoff'].includes(current.phase)&&p.kind==='probe')await stopSyncOnly(cfg,current);
  await store.noRunningJob();
  if(p.kind==='sync'){
    if(!wantsSync(cfg))throw Error('请先开启手机自动同步。');
    const job={schema:1,id:store.id(),binding:cfg.binding,kind:'sync',continuous:true,slot:'interaction',phase:'scheduled',created_at:Date.now(),expires_at:Date.now()+90000};
    try{
      await store.write('job.json',job);await flows.ensure(cfg,'interaction_alt');await flows.watchdog(cfg);
      return {...await flows.schedule(cfg,'interaction',job),message:'记录同步已安排；手机调度可能延迟，不会发送聊天。'};
    }catch(error){job.phase='failed';job.error=String(error.message||error);await store.write('job.json',job);throw error;}
  }
  const params=store.parameters(cfg);
  const state=await store.read('delivery_'+cfg.binding+'.json');
  if(state?.pending?.phase==='completed')await interaction.settle(params,state,await interaction.connect(params.mcp_url,params.connection));
  if (state?.pending) throw Error('上次触摸发送结果尚未确认，请核对原聊天后使用恢复按钮；不需要重新发送自检。');
  const prior=cfg.probe_file?await store.read(cfg.probe_file):null;
  if (p.kind==='probe'&&prior&&prior.phase!=='completed') throw Error('上次自检结果不明确，请先核对原聊天并恢复；这不阻止正常陪伴。');
  if (p.kind==='interaction') {
    const tool=await interaction.connect(params.mcp_url,params.connection);
    const context=await tool('get_chat_context',{chat_id:params.chat_id,limit:1});
    if (!context.preferences?.proactive_enabled || !context.preferences.chat_integration_enabled)
      throw Error('请先在陪伴设置中开启触摸主动回复和聊天融入。');
  }
  const job={schema:1,id:store.id(),binding:cfg.binding,kind:p.kind,phase:'scheduled',
    created_at:Date.now(),expires_at:Date.now()+90000,display_verified:false};
  if(p.kind==='interaction'&&cfg.continuous){
    cfg.continuous_enabled=true;await store.write('settings.json',cfg);
    job.continuous=true;job.slot='interaction';
    await flows.ensure(cfg,'interaction_alt');await flows.watchdog(cfg);
  }
  if (p.kind==='probe') {
    job.probe_file='probe_'+cfg.binding+'_'+job.id+'.json';
    cfg.probe_file=job.probe_file;
    await store.write('settings.json',cfg);
  }
  await store.write('job.json',job);
  try {return {...await flows.schedule(cfg,p.kind,job),message:'任务已安排，请返回绑定聊天；手机调度可能延迟。'};}
  catch(error) {job.phase='failed';job.error=String(error.message||error);await store.write('job.json',job);throw error;}
}
async function continueListening(prior,delay=10000) {
  if(continuationFlight)return await continuationFlight;
  continuationFlight=continueOnce(prior,delay).finally(()=>{continuationFlight=null;});return await continuationFlight;
}
async function continueOnce(prior,delay) {
  const cfg=await store.config();
  if((!cfg.continuous_enabled&&!wantsSync(cfg))||cfg.binding!==prior.binding)return {continued:false};
  const journal=cfg.binding?await store.read('delivery_'+cfg.binding+'.json'):null;
  const uncertain=journal?.pending?.phase==='sending';
  if(uncertain&&!wantsSync(cfg))return {continued:false,needs_user_check:true};
  const kind=(cfg.continuous_enabled||cfg.active_reply_requested)&&!uncertain?'interaction':'sync';
  const next={schema:1,id:store.id(),binding:cfg.binding,kind,continuous:kind==='sync'||!!cfg.continuous_enabled,
    slot:prior.slot==='interaction'?'interaction_alt':'interaction',phase:'scheduled',created_at:Date.now(),
    delay_ms:delay,expires_at:Date.now()+delay+90000,display_verified:false};
  const latestBefore=await store.config();
  if((latestBefore.control_generation||0)!==(cfg.control_generation||0))return {continued:false};
  await store.write('job.json',next);await flows.schedule(cfg,next.slot,next);
  const latest=await store.config();
  if((latest.control_generation||0)!==(cfg.control_generation||0)||(!latest.continuous_enabled&&!wantsSync(latest))){await flows.disable(latest);next.phase='stopped';await store.write('job.json',next);}
  return {continued:next.phase==='scheduled',job_id:next.id};
}
async function watchdog(binding) {
  const cfg=await store.config();
  if((!cfg.continuous_enabled&&!wantsSync(cfg))||cfg.binding!==binding)return {listening:false,reason:'disabled'};
  const active=await refreshJob();
  if(active&&['scheduled','running','handoff','stopping'].includes(active.phase))return {listening:active.phase==='running'};
  return await continueListening({binding,slot:active?.slot});
}
async function run_task(p) {
  if(typeof p.job_id==='string'&&p.job_id.startsWith('watchdog:'))return await watchdog(p.job_id.slice(9));
  if(activeWorker)throw Error('已有设备采集任务正在运行，不启动重复任务。');
  activeWorker=p.job_id;
  try{return await executeTask(p);}finally{activeWorker=null;}
}
async function executeTask(p) {
  const cfg=await store.config(),job=await store.read('job.json');
  if (!job || job.id!==p.job_id || job.phase!=='scheduled' || job.binding!==cfg.binding || Date.now()>job.expires_at)
    throw Error('任务已结束、过期或不属于当前绑定，不会发送。');
  if(job.continuous&&!cfg.continuous_enabled&&!wantsSync(cfg))throw Error('后台任务已关闭，不再启动。');
  if(job.kind==='interaction'&&cfg.active_reply_requested){cfg.active_reply_requested=false;await store.write('settings.json',cfg);}
  const chunk=job.continuous?240:cfg.duration_sec;
  const generation=cfg.control_generation||0;
  job.phase='running';job.worker_deadline=Date.now()+chunk*1000+125000;
  await store.write('job.json',job);
  const params=job.kind==='sync'?{mcp_url:cfg.connection.mcp_url,connection:cfg.connection}:store.parameters(cfg);
  params.duration_sec=chunk;params.continuous=!!job.continuous;
  let responseWait=cfg.response_wait_sec??1,lastHeartbeat=0;
  params.get_response_wait=()=>responseWait;
  params.ensure_active=async()=>{
    const active=await store.read('job.json');
    if (active?.id!==job.id || active.phase!=='running')
      throw Error('任务已停止，不再发送新反馈。');
    if(Date.now()-lastHeartbeat>=5000){
      const latest=await store.config();responseWait=latest.response_wait_sec??1;
      if((latest.control_generation||0)!==generation||latest.sync_identity_changed)throw Error('后台任务已停止。');
      if(job.continuous&&!latest.continuous_enabled&&!wantsSync(latest))throw Error('后台任务已关闭。');
      active.last_heartbeat=Date.now();lastHeartbeat=active.last_heartbeat;await store.write('job.json',active);
    }
  };
  try {
    await params.ensure_active();
    const result=job.kind==='probe'?await probe.send_probe({...params,
      state_path:store.path(job.probe_file),timeout_sec:90}):job.kind==='sync'?await require('../core/collector.js').run(params):await interaction.listen_interaction(params);
    const active=await store.read('job.json');
    if (active?.id===job.id && active.phase==='running') {
      job.phase=result.error?'failed':'completed';job.result=result;
      if (result.error) job.error=result.error;
      await store.write('job.json',job);
      if(job.continuous&&result.state==='disabled'&&!wantsSync(await store.config())){
        const latest=await store.config();latest.continuous_enabled=false;await store.write('settings.json',latest);await flows.disable(latest);
      }
      job.binding=(await store.config()).binding;
      if((job.continuous&&result.state!=='disabled')||wantsSync(await store.config()))await continueListening(job);
    }
    return result;
  } catch(error) {
    const active=await store.read('job.json');
    if (active?.id===job.id && active.phase==='running') {
      job.phase='failed';job.error=String(error.message||error);await store.write('job.json',job);
      if(recovery.fatal(error)){
        const latest=await store.config();latest.sync_identity_changed=true;latest.continuous_enabled=false;await store.write('settings.json',latest);await flows.disable(latest);
      }else if(recovery.retryable(error)&&(job.continuous||wantsSync(await store.config())))await continueListening(job,60000);
      else if(/main_chat_send/.test(job.error)){if(wantsSync(await store.config()))await continueListening(job,60000);}
      else{
        const latest=await store.config();latest.sync_paused=true;latest.continuous_enabled=false;await store.write('settings.json',latest);await flows.disable(latest);
      }
    }
    throw error;
  } finally {
    if(cfg.connection?.kind==='ai-doll-device-connection'){
      const current=await store.read('job.json');
      if(!current||!['scheduled','running','handoff'].includes(current.phase)){
        try{const tool=await interaction.connect(cfg.connection.mcp_url,cfg.connection);await tool('_stop_record_sync');}catch(_){}
      }
    }
  }
}
async function stop() {
  const cfg=await store.config(),job=await store.read('job.json');
  if(cfg.recovery_required)return {stopped:true,cleanup_pending:true,message:cfg.storage_recovery};
  cfg.continuous_enabled=false;cfg.active_reply_requested=false;cfg.sync_paused=true;cfg.control_generation=(cfg.control_generation||0)+1;await store.write('settings.json',cfg);
  if (job && ['scheduled','running','handoff','stopping','interrupted'].includes(job.phase)) {
    job.phase='stopped';await store.write('job.json',job);
  }
  // Ending the owned server session prevents the next send, even if the Android
  // worker cannot be cancelled immediately. Never cancel a user's chat stream.
  let result={stopped:true},error=null,workflow_disabled=true,remote_session_ended=true;
  try {await flows.disable(cfg);} catch(e) {workflow_disabled=false;error=String(e.message||e);}
  try {if (cfg.connection&&cfg.chat) result=await interaction.stop_interaction(store.parameters(cfg));}
  catch(e) {remote_session_ended=false;error=error||String(e.message||e);}
  if(cfg.connection?.kind==='ai-doll-device-connection'){try{const tool=await interaction.connect(cfg.connection.mcp_url,cfg.connection);await tool('_stop_record_sync');}catch(e){error=error||String(e.message||e);}}
  if (job) {job.phase='stopped';job.error=error;job.cleanup_pending=!!error;await store.write('job.json',job);}
  return {...result,stopped:true,workflow_disabled,remote_session_ended,cleanup_pending:!!error,
    message:error?'手机后台任务已停止，可修改设置；远端会话或工作流清理未确认，连接恢复后可再次停止核对。':
      '已停止后台任务，可以修改设置；已提交给模型的回复可能仍完成，发送记录保留。'};
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
  const job=await store.read('job.json');
  const next=cfg.continuous_enabled?await continueListening({binding:cfg.binding,slot:job?.slot}):null;
  return {recovered:true,automatic_retry:false,continued:!!next?.continued,display_verified:false,
    message:next?.continued?'已保存核对结果，常开陪伴将继续；不会自动重发刚才未确认的消息。':'结果已保存，可重新开启陪伴；无需重新发送自检。'};
}
// Export plain functions for tests and tools. Native complete is called only at
// the public boundary, never from a shared engine that could end the wrong turn.
for (const [name,fn] of Object.entries({status,setup,setup_device,read_hotspot_pairing,finish_pairing,import_connection_code,set_record_sync,sync_now,update_computer_address,set_experience,view_history,list_chats,bind_chat,check_connection,schedule,
  get_panel:controls.panel,update_port:controls.updatePort,set_persona_source:controls.persona,diagnostics:controls.diagnostics,test_sensor:controls.testSensor,
  stop,confirm_probe,recover,run_task,import_legacy_state})) exports[name]=async(p={})=>complete(await fn(p));
