// Settings operations share the actual connection used by the chat worker.
const store=require('./settings.js'),interaction=require('./interaction.js');
async function tool() {
  const cfg=await store.config();
  if(!cfg.connection)throw Error('请先设置设备连接。');
  return {cfg,call:await interaction.connect(cfg.connection.mcp_url,cfg.connection)};
}
function mode(c) {return c.mode||(!c.enabled?'off':c.driver==='simulation'?'simulation':'connected');}
async function panel() {
  const state=await store.config();
  if(state.recovery_required)return {channels:[],settings_entries:[],storage_recovery:state.storage_recovery,recovery_required:true};
  const {cfg,call}=await tool();
  const overview=await call('get_device_overview');
  let config,entry,persona;
  config=overview.port_state_model||(!overview.online&&Array.isArray(overview.channels))?{channels:overview.channels||[],port_state_model:overview.port_state_model}:await call('get_channel_config');
  const phone=cfg.connection.kind==='ai-doll-device-connection';
  entry=overview.device_ip&&phone?{entries:[]}:await call('get_settings_entry',{section:'hardware'});
  persona=overview.preferences?.doll_persona!==undefined?{persona:overview.preferences.doll_persona}:await call('get_persona');
  const entries=(entry.entries||[]).filter(e=>e.url&&!/^https?:\/\/(127\.0\.0\.1|localhost)(:|\/)/.test(e.url));
  const ip=overview.device_ip;
  if(phone&&ip&&/^(\d{1,3}\.){3}\d{1,3}$/.test(ip)&&!entries.some(e=>e.scope==='device_lan'))
    entries.unshift({url:'http://'+ip+'/#setup_token='+encodeURIComponent(cfg.connection.token),scope:'device_lan',access:'手机与设备在同一家庭网络时可打开；开启网页登录保护时需登录。'});
  const result={overview,channels:(config.channels||[]).map(c=>({...c,mode:mode(c)})),
    port_writes:config.port_state_model==='per_port_v1',presence_source:'saved_installation_config',
    electrical_presence_detection:false,preferences:overview.preferences||{},persona:overview.preferences?.doll_persona||persona.persona||'',
    settings_entries:entries,hotspot:entry.hotspot||{url:'http://192.168.4.1/',access:'仅连接设备热点时使用。'},checked_at:Date.now()};
  await store.write('panel_'+cfg.binding+'.json',result);return result;
}
async function refreshOverview(cfg,cached={}){
  const call=await interaction.connect(cfg.connection.mcp_url,cfg.connection);
  const overview=await call('get_device_overview');
  const result={...cached,overview,preferences:overview.preferences||cached.preferences||{},
    channels:(overview.channels||cached.channels||[]).map(c=>({...c,mode:mode(c)})),
    persona:overview.preferences?.doll_persona??cached.persona??'',checked_at:Date.now(),connection_error:null};
  await store.write('panel_'+cfg.binding+'.json',result);return result;
}
async function updatePort(p) {
  const {call}=await tool();
  if(!Number.isInteger(p.channel)||p.channel<0||p.channel>15)throw Error('请选择实际配置的端口。');
  const changes={};
  if(p.mode!==undefined){if(!['off','simulation','connected'].includes(p.mode))throw Error('请选择关闭、模拟或已接入。');changes.mode=p.mode;}
  if(p.name!==undefined){if(typeof p.name!=='string'||!p.name.trim()||p.name.length>96)throw Error('请输入部位名称。');changes.name=p.name.trim();}
  if(!Object.keys(changes).length)throw Error('没有要修改的字段。');
  const result=await call('update_body_part',{channel:p.channel,changes});
  if(result.updated!==true)throw Error(result.message||'端口修改未确认，请刷新核对，不自动重试。');
  return result;
}
async function persona(p) {
  if(!['chat','doll'].includes(p.source))throw Error('请选择当前聊天或娃娃人设。');
  const changes={persona_source:p.source};
  if(p.text!==undefined){if(typeof p.text!=='string'||p.text.length>4000)throw Error('娃娃人设最多4000字。');changes.doll_persona=p.text;}
  const {call}=await tool(),r=await call('update_companion_preferences',{changes});
  if(r.preferences?.persona_source!==p.source)throw Error('人设来源未确认保存。');
  return {saved:true,source:p.source};
}
async function diagnostics() {
  const {cfg,call}=await tool();
  const overview=await call('get_device_overview');
  return {device:overview.device_id,online:overview.online,last_sync:overview.last_sync,
    channels:overview.channels,values:overview.values,collector_error:overview.collector_error||null,
    job:await store.read('job.json'),continuous_enabled:!!cfg.continuous_enabled,
    recording_scope:cfg.connection.mode==='phone'?'自动同步或互动任务运行时':'设备或采集服务运行时'};
}
async function testSensor() {
  const {call}=await tool();
  const before=await call('get_device_overview');
  let pressed=new Set((before.values||[]).filter(v=>v.active).map(v=>v.channel));
  const deadline=Date.now()+10000;
  while(Date.now()<deadline){
    await Tools.System.sleep(700);
    const overview=await call('get_device_overview');
    if(!overview.online)throw Error('设备当前离线，请检查供电和连接。');
    const values=overview.values||[];
    const hit=values.find(v=>v.active&&v.source==='sensor'&&v.quality==='ok'&&!pressed.has(v.channel));
    if(hit)return {detected:true,channel:hit.channel,source:'sensor',message:(hit.name||'CH'+hit.channel)+'收到一次真实按压，未向聊天发送测试消息。'};
    pressed=new Set(values.filter(v=>v.active).map(v=>v.channel));
  }
  return {detected:false,message:'本次没有观察到新的真实按压。可刷新端口、检查已接入状态；未修改阈值或生成模拟数据。'};
}
exports.panel=panel;exports.updatePort=updatePort;exports.persona=persona;exports.diagnostics=diagnostics;
exports.testSensor=testSensor;
exports.refreshOverview=refreshOverview;
