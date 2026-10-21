/* METADATA
{
  "name":"ai_doll_companion",
  "enabledByDefault":true,
  "version":"2.24.1",
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
    {"name":"list_chats","description":"列出已有聊天，让用户按标题选择绑定。","parameters":[]},
    {"name":"view_history","description":"读取互动记录页面，支持按日期和游标翻页，不发送消息。","parameters":[{"name":"date","type":"string","required":false,"description":"可选本地日期YYYY-MM-DD；省略为近期记录"},{"name":"after","type":"number","required":false,"description":"上一页next_cursor，首次0"},{"name":"limit","type":"number","required":false,"description":"每页1到100条，默认50"}]},
    {"name":"setup_device","description":"在面板连接家庭网络的设备，仅安卓手机模式，不更改采样或校准。","parameters":[{"name":"host","type":"string","required":true,"description":"设备家庭局域网 IP 或固件显示的固定 .local 连接名"},{"name":"token","type":"string","required":false,"description":"可选设备 MCP 令牌"}]},
    {"name":"set_experience","description":"设置陪伴方式与合并等待；连接和聊天已保存即可开启，无需发送测试。","parameters":[{"name":"enabled","type":"boolean","required":false,"description":"主动回应和聊天融入"},{"name":"duration_sec","type":"number","required":false,"description":"限时60或900秒"},{"name":"continuous","type":"boolean","required":false,"description":"是否常开"},{"name":"response_wait_sec","type":"number","required":false,"description":"停止按压后等待0到30秒合并回应；0立即触发，默认1"}]},
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
const controls=require('../core/controls.js');
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
  const cfg=await store.config(),job=await refreshJob();
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
  if(cfg.continuous_enabled)throw Error('请先关闭常开，再更换连接。');
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
  const cfg=await store.config();if(cfg.continuous_enabled)throw Error('请先关闭常开，再更换设备。');
  const connection=await require('../core/device.js').pair(p.host,p.token,cfg.connection);
  if(cfg.connection?.kind!==connection.kind||cfg.connection?.device_id!==connection.device_id){
    cfg.binding=store.id();cfg.background_verified=false;cfg.probe_file=null;
  }
  cfg.continuous_enabled=false;cfg.connection=connection;await store.write('settings.json',cfg);
  return {saved:true,label:connection.label,mode:connection.mode,device_id:connection.device_id};
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
  const stopped=p.enabled===false?await stop():null;
  if(Object.keys(p).some(k=>k!=='response_wait_sec'))await store.noRunningJob();
  if(p.duration_sec!==undefined&&![60,900].includes(p.duration_sec))throw Error('请选择 1 分钟或 15 分钟。');
  if(p.enabled!==undefined&&typeof p.enabled!=='boolean')throw Error('请明确选择开启或关闭。');
  if(p.continuous!==undefined&&typeof p.continuous!=='boolean')throw Error('请明确选择常开或限时。');
  if(p.response_wait_sec!==undefined&&(!Number.isFinite(p.response_wait_sec)||p.response_wait_sec<0||p.response_wait_sec>30))throw Error('合并等待时间应为0～30秒。');
  const cfg=await store.config();
  if(cfg.continuous_enabled&&(p.continuous!==undefined||p.duration_sec!==undefined))throw Error('请先关闭常开，再修改陪伴方式。');
  let preferences;
  if(p.enabled!==undefined){
    if(!cfg.connection)throw Error('请先保存连接。');
    let result;
    try{
      const tool=await interaction.connect(cfg.connection.mcp_url,cfg.connection);
      result=await tool('update_companion_preferences',{changes:{chat_integration_enabled:true,proactive_enabled:p.enabled}});
    }catch(error){
      if(stopped)return {saved:false,locally_stopped:true,preference_sync_pending:true,
        message:'手机后台任务已停止，可修改设置；设备回应偏好暂未同步，连接恢复后再核对。'};
      throw error;
    }
    if(result.preferences?.proactive_enabled!==p.enabled||result.preferences?.chat_integration_enabled!==true)
      throw Error('回应开关未确认保存。');
    preferences=result.preferences;
  }
  if(p.duration_sec!==undefined){cfg.duration_sec=p.duration_sec;await store.write('settings.json',cfg);}
  if(p.continuous!==undefined){cfg.continuous=p.continuous;await store.write('settings.json',cfg);}
  if(p.response_wait_sec!==undefined){cfg.response_wait_sec=p.response_wait_sec;await store.write('settings.json',cfg);}
  return {saved:true,duration_sec:cfg.duration_sec,response_wait_sec:cfg.response_wait_sec??1,continuous:!!cfg.continuous,preferences};
}
async function list_chats() { return await Tools.Chat.listChats({limit:100,sort_by:'updatedAt',sort_order:'desc'}); }
async function view_history(p={}) {
  const cfg=await store.config();if(!cfg.connection)throw Error('请先保存连接。');
  const tool=await interaction.connect(cfg.connection.mcp_url,cfg.connection);
  const result=await tool('query_device_history',{...(p.date?{date:p.date}:{}),after:p.after||0,limit:p.limit||50});
  return {...result,events:result.events||[],has_more:!!result.has_more,next_cursor:result.next_cursor??p.after??0};
}
async function bind_chat(p) {
  await refreshJob(); await store.noRunningJob();
  if (!p.chat_id || p.chat_id==='main') throw Error('请在已有聊天列表中选择。');
  const result=await Tools.Chat.findChat({query:p.chat_id,match:'exact',index:0});
  if (result.chat?.id!==p.chat_id) throw Error('该已有聊天未找到，未更改绑定。');
  const cfg=await store.config();
  if(cfg.continuous_enabled)throw Error('请先关闭常开，再更换聊天。');
  if (cfg.chat?.id!==p.chat_id) {cfg.binding=store.id();cfg.background_verified=false;cfg.probe_file=null;}
  cfg.chat={id:p.chat_id,title:result.chat.title||'未命名聊天'};
  await store.write('settings.json',cfg);
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
  if (!['probe','interaction'].includes(p.kind)) throw Error('请选择连接自检或开始互动。');
  await refreshJob(); await store.noRunningJob();
  const cfg=await store.config(),params=store.parameters(cfg);
  const state=await store.read('delivery_'+cfg.binding+'.json');
  if(state?.pending?.phase==='completed')await interaction.settle(params,state,await interaction.connect(params.mcp_url,params.connection));
  if (state?.pending) throw Error('上次触摸发送结果尚未确认，请核对原聊天后使用恢复按钮；不需要重新发送自检。');
  const prior=cfg.probe_file?await store.read(cfg.probe_file):null;
  if (p.kind==='probe'&&prior&&prior.phase!=='completed') throw Error('上次自检结果不明确，请先核对原聊天并恢复；这不阻止正常陪伴。');
  if (p.kind==='interaction') {
    const tool=await interaction.connect(params.mcp_url,params.connection);
    const context=await tool('get_chat_context',{chat_id:params.chat_id,limit:1});
    if (!context.preferences?.proactive_enabled || !context.preferences.chat_integration_enabled)
      throw Error('请先在电脑反馈设置中明确开启主动回应和聊天融入。');
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
  const cfg=await store.config();
  if(!cfg.continuous_enabled||cfg.binding!==prior.binding)return {continued:false};
  const journal=await store.read('delivery_'+cfg.binding+'.json');
  if(journal?.pending?.phase==='sending')return {continued:false,needs_user_check:true};
  const next={schema:1,id:store.id(),binding:cfg.binding,kind:'interaction',continuous:true,
    slot:prior.slot==='interaction'?'interaction_alt':'interaction',phase:'scheduled',created_at:Date.now(),
    delay_ms:delay,expires_at:Date.now()+delay+90000,display_verified:false};
  await store.write('job.json',next);
  await flows.schedule(cfg,next.slot,next);
  if(!(await store.config()).continuous_enabled){await flows.disable(cfg);next.phase='stopped';await store.write('job.json',next);}
  return {continued:next.phase==='scheduled',job_id:next.id};
}
async function watchdog(binding) {
  const cfg=await store.config();
  if(!cfg.continuous_enabled||cfg.binding!==binding)return {listening:false,reason:'disabled'};
  const active=await refreshJob();
  if(active&&['scheduled','running','handoff','stopping'].includes(active.phase))return {listening:active.phase==='running'};
  return await continueListening({binding,slot:active?.slot});
}
async function run_task(p) {
  if(typeof p.job_id==='string'&&p.job_id.startsWith('watchdog:'))return await watchdog(p.job_id.slice(9));
  const cfg=await store.config(),job=await store.read('job.json');
  if (!job || job.id!==p.job_id || job.phase!=='scheduled' || job.binding!==cfg.binding || Date.now()>job.expires_at)
    throw Error('任务已结束、过期或不属于当前绑定，不会发送。');
  if(job.continuous&&!cfg.continuous_enabled)throw Error('常开已关闭，不再启动任务。');
  const chunk=job.continuous?240:cfg.duration_sec;
  job.phase='running';job.worker_deadline=Date.now()+chunk*1000+125000;
  await store.write('job.json',job);
  const params=store.parameters(cfg);
  params.duration_sec=chunk;params.continuous=!!job.continuous;
  let responseWait=cfg.response_wait_sec??1,lastHeartbeat=0;
  params.get_response_wait=()=>responseWait;
  params.ensure_active=async()=>{
    const active=await store.read('job.json');
    if (active?.id!==job.id || active.phase!=='running')
      throw Error('任务已停止，不再发送新反馈。');
    if(Date.now()-lastHeartbeat>=5000){
      const latest=await store.config();responseWait=latest.response_wait_sec??1;
      if(job.continuous&&!latest.continuous_enabled)throw Error('常开已关闭。');
      active.last_heartbeat=Date.now();lastHeartbeat=active.last_heartbeat;await store.write('job.json',active);
    }
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
      if(job.continuous&&result.state==='disabled'){
        const latest=await store.config();latest.continuous_enabled=false;await store.write('settings.json',latest);await flows.disable(latest);
      }
      if(job.continuous&&result.state!=='disabled')await continueListening(job);
    }
    return result;
  } catch(error) {
    const active=await store.read('job.json');
    if (active?.id===job.id && active.phase==='running') {
      job.phase='failed';job.error=String(error.message||error);await store.write('job.json',job);
      if(job.continuous)await continueListening(job,60000);
    }
    throw error;
  }
}
async function stop() {
  const cfg=await store.config(),job=await store.read('job.json');
  cfg.continuous_enabled=false;await store.write('settings.json',cfg);
  if (job && ['scheduled','running','handoff','stopping','interrupted'].includes(job.phase)) {
    job.phase='stopped';await store.write('job.json',job);
  }
  // Ending the owned server session prevents the next send, even if the Android
  // worker cannot be cancelled immediately. Never cancel a user's chat stream.
  let result={stopped:true},error=null,workflow_disabled=true,remote_session_ended=true;
  try {await flows.disable(cfg);} catch(e) {workflow_disabled=false;error=String(e.message||e);}
  try {if (cfg.connection&&cfg.chat) result=await interaction.stop_interaction(store.parameters(cfg));}
  catch(e) {remote_session_ended=false;error=error||String(e.message||e);}
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
for (const [name,fn] of Object.entries({status,setup,setup_device,update_computer_address,set_experience,view_history,list_chats,bind_chat,check_connection,schedule,
  get_panel:controls.panel,update_port:controls.updatePort,set_persona_source:controls.persona,diagnostics:controls.diagnostics,test_sensor:controls.testSensor,
  stop,confirm_probe,recover,run_task,import_legacy_state})) exports[name]=async(p={})=>complete(await fn(p));
