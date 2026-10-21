// Native Operit settings. Writes only follow explicit user actions.
async function Screen(ctx) {
 const UI=ctx.UI,colors=ctx.MaterialTheme?.colorScheme||{};
 const [page,setPage]=ctx.useState('page','home'),[message,setMessage]=ctx.useState('message','首次连接后绑定原聊天，之后从这里开关陪伴。');
 const [busy,setBusy]=ctx.useState('busy',false),[loaded,setLoaded]=ctx.useState('loaded',false);
 const [savedState,setState]=ctx.useState('status',{}),[savedPanel,setPanel]=ctx.useState('panel',{});
 let state=savedState,panel=savedPanel;
 const [duration,setDuration]=ctx.useState('duration',60),[continuous,setContinuous]=ctx.useState('continuous',false);
 const [mode,setMode]=ctx.useState('setupMode','import'),[host,setHost]=ctx.useState('deviceHost','');
 const [computerHost,setComputerHost]=ctx.useState('computerHost',''),[token,setToken]=ctx.useState('deviceToken','');
 const [advanced,setAdvanced]=ctx.useState('advanced',false),[developer,setDeveloper]=ctx.useState('developer',false);
 const [chats,setChats]=ctx.useState('chats',[]),[candidate,setCandidate]=ctx.useState('candidate',null);
 const [names,setNames]=ctx.useState('names',{}),[personaText,setPersonaText]=ctx.useState('personaText','');
 const [waitText,setWaitText]=ctx.useState('responseWait','1');
 const [historyDate,setHistoryDate]=ctx.useState('historyDate',''),[history,setHistory]=ctx.useState('history',{events:[]});
 const [diagnostic,setDiagnostic]=ctx.useState('diagnostic',''),[webUrl,setWebUrl]=ctx.useState('webUrl','');
 async function call(name,params={}) {
  let r=await ctx.callTool('ai_doll_companion:'+name,params);
  if(r?.success===false)throw Error(r.error||r.message||'操作未完成');
  if(r?.data!==undefined&&!r.configured&&!r.saved)r=r.data;
  if(typeof r==='string'){try{r=JSON.parse(r);}catch(_){throw Error(r);}}
  return r;
 }
 async function action(fn){if(busy)return;setBusy(true);try{await fn();}catch(e){setMessage(String(e.message||e));}finally{setBusy(false);}}
 const text=(value,extra={})=>UI.Text({text:value,color:colors.onSurface,fontSize:14,...extra});
 const title=value=>text(value,{fontSize:20,fontWeight:'bold'});
 const note=value=>text(value,{color:colors.onSurfaceVariant,fontSize:13});
 const button=(label,fn,enabled=true)=>UI.Button({text:label,enabled:!busy&&enabled,onClick:()=>action(fn),fillMaxWidth:true});
 const row=children=>UI.Row({spacing:8,fillMaxWidth:true,verticalAlignment:'CenterVertically'},children);
 const card=(heading,children)=>UI.Card({containerColor:colors.surfaceContainer,contentColor:colors.onSurface,fillMaxWidth:true},[
  UI.Column({padding:16,spacing:10,fillMaxWidth:true},[title(heading),...children])]);
 async function refresh(withPanel=true,live=true){
  const s=await call('status',{refresh:live&&!withPanel});state=s;
  if(s.panel){panel=s.panel;setPanel(panel);}
  if(s.configured&&withPanel){panel=await call('get_panel');setPanel(panel);s.connection_state=panel.overview?.online?'online':'device_offline';}
  setState(s);setDuration(s.duration_sec||60);setContinuous(!!s.continuous);setWaitText(String(s.response_wait_sec??1));
  setComputerHost(s.connection?.computer_host||'');if(s.connection?.mode==='phone')setMode('phone');
  if(s.connection?.device_host)setHost(s.connection.device_host);
  setPersonaText(panel.persona||'');return s;
 }
 async function onEnter(){
  // Operit dispatches the root onLoad once for each opened page instance.
  try{await refresh(false,true);}catch(e){setMessage(String(e.message||e));}
 }
 if(!loaded){try{await refresh(false,false);}catch(e){setMessage(String(e.message||e));}setLoaded(true);}
 async function go(value){
  setPage(value);
  if(['body','persona','device'].includes(value))await refresh();
  else if(['home','settings'].includes(value))await refresh(false,true);
 }
 async function loadHistory(append=false,date=historyDate){
  setPage('history');
  const previous=append?history:{events:[]};setHistory({...previous,loading:true,error:null});
  try{const r=await call('view_history',{...(date?{date}:{}),after:append?history.next_cursor||0:0,limit:50});
   setHistory({...r,events:[...previous.events,...r.events],loading:false});
  }catch(e){setHistory({...previous,loading:false,error:String(e.message||e)});throw e;}
 }
 const phases={scheduled:'等待手机启动',running:'正在陪伴',handoff:'正在续接',completed:'本次已结束',expired:'手机未及时启动，等待恢复',
  interrupted:'手机任务已暂停',failed:'需要检查连接',stopped:'已关闭',stopping:'停止待核对'};
 const source={device:'电脑采集',simulation:'电脑模拟',server:'服务器直传',phone:'手机直连'};
 const active=state.job?.kind==='interaction'&&['scheduled','running','handoff'].includes(state.job?.phase),on=active||!!state.continuous_enabled;
 const ports=panel.channels||[];
 async function toggle(enabled){
  if(!enabled){const r=await call('set_experience',{enabled:false});await refresh(false);setMessage(r.message||'已关闭触摸主动回复。');return;}
  await call('set_experience',{enabled:true,continuous,duration_sec:duration});
  const r=await call('schedule',{kind:'interaction'});await refresh(false);
  setMessage(r.message+(continuous?' 常开会自动续接，直到你关闭。':''));
 }
 async function stopTasks(){const r=await call('stop');await refresh(false);setMessage(r.message);}
 async function pickConnection(){
  const r=await ctx.openFilePicker({picker:'document',mimeTypes:['application/json'],allowMultiple:false});
  if(r?.cancelled)return;if(!r?.files?.[0]?.path)throw Error('文件选择器未提供可读文件。');
  const saved=await call('setup',{connection_file:r.files[0].path});await refresh();setMessage('连接已保存：'+saved.label+'。请选择原聊天。');
 }
 async function check(){
  const r=await call('check_connection');await refresh(false,false);
  setMessage('连接、原聊天、存储和工作流检查通过。设备'+(r.overview.online?'在线。':'当前离线，需检查供电与网络。')+
   ' 可以直接开启陪伴；发送诊断消息仅用于排查。');
 }
 async function chooseDuration(c,seconds){
  await call('set_experience',{continuous:c,...(seconds?{duration_sec:seconds}:{})});setContinuous(c);if(seconds)setDuration(seconds);
  setMessage(c?'已选择常开，开启后自动续接，直到关闭。':'已选择限时，下次开启生效。');
 }
 async function touchTest(){setMessage('请现在按压已接入的传感器，正在等待真实输入……');const r=await call('test_sensor');setMessage(r.message);await refresh();}
 if(page==='web')return UI.Column({fillMaxSize:true,spacing:8},[
  button('返回 AI Doll 设置',()=>go('device')),button('停止后台任务',stopTasks),note('设备局域网页需要手机与设备网络互通。'),
  UI.WebView({url:webUrl,javaScriptEnabled:true,allowFileAccess:false,allowContentAccess:false,fillMaxWidth:true,weight:1})]);
 let content=[];
 if(page==='home')content=[
  card('连接与聊天',[
   text(state.configured?'✓ 已保存连接':'请先连接设备或导入电脑／服务器连接'),
   ...(!state.configured?[button('设置设备连接',()=>go('connection'))]:[]),
   text(state.chat?'回复到：'+state.chat.title:'尚未选择原聊天'),
   ...(!state.chat?[button('选择原聊天',()=>go('chat'))]:[]),
   note('保存连接并绑定聊天后即可开启。进入面板自动检查连接，不会向聊天发送测试消息。'),
   button('一键检查',check),button('发送诊断消息（可选）',()=>go('tests'))
  ]),
  card('原聊天陪伴',[
   text('回复到：'+(state.chat?.title||'尚未绑定聊天')),text('人设：'+(panel.preferences?.persona_source==='doll'?'娃娃人设':'跟随当前聊天')),
   row([text('触摸主动回复',{weight:1,fontSize:17}),UI.Switch({checked:on,enabled:!busy&&(on||!!state.configured&&!!state.chat),onCheckedChange:v=>action(()=>toggle(v))})]),
   text((phases[state.job?.phase]||'尚未开启')+(state.continuous_enabled?' · 常开已启用':'')),
   ...(state.queued_touches?[note('上一条回复进行中，'+state.queued_touches+'次触摸正在排队，随后合并回应。')]:[]),
   note(continuous?'常开：不设自动结束时间，可随时关闭。':'限时：'+(duration===900?'15分钟':'1分钟')+'，到期结束。'),
   button('触摸合并：停止按压后 '+(state.response_wait_sec??1)+' 秒',()=>go('batching')),
   button('陪伴方式：'+(continuous?'常开':duration===900?'15分钟':'1分钟测试'),()=>go('duration')),
   ...(state.uncertain_delivery?[note('上次发送结果待核对，已暂停继续发送。'),button('核对原聊天的发送结果',()=>go('recovery'))]:[]),
   button('刷新状态',()=>refresh())
  ]),
  card('常用操作',[button('试摸一下',touchTest),
   button('身体与传感器 · '+ports.filter(c=>c.mode==='connected').length+' 路已接入',()=>go('body')),
   button('查看互动记录',()=>loadHistory())])
 ];
 else if(page==='settings')content=[card('设置',[
  button('身体与传感器',()=>go('body')),button('人设与反馈',()=>go('persona')),button('对话窗口绑定',()=>go('chat')),
  button('设备与连接',()=>go('connection')),button('触摸合并与等待',()=>go('batching')),button('一键检查',check),button('测试与帮助',()=>go('tests')),
  row([text('开发者选项',{weight:1}),UI.Switch({checked:developer,enabled:!busy,onCheckedChange:v=>setDeveloper(v)})]),
  ...(developer?[button('进入开发者工具',()=>go('developer'))]:[])
 ])];
 else if(page==='duration')content=[card('陪伴方式',[
  button('常开，直到我关闭',()=>chooseDuration(true)),button('15 分钟陪伴',()=>chooseDuration(false,900)),button('1 分钟测试',()=>chooseDuration(false,60)),
  note('常开自动续接后台任务，不必反复开始。手机暂停Operit时会中断，恢复任务会继续检查，不补发过期触摸。')
 ])];
 else if(page==='batching')content=[card('触摸合并与等待',[
  note('每次按压都会保存。AI正在思考时继续收集；回复完成后，将之后的多次触摸合并到下一条回应。'),
  UI.TextField({label:'停止按压后等待（秒）',value:waitText,singleLine:true,onValueChange:setWaitText}),
  button('保存等待时间',async()=>{if(!waitText.trim())throw Error('请输入0～30秒。');const r=await call('set_experience',{response_wait_sec:Number(waitText)});setState({...state,response_wait_sec:r.response_wait_sec});setMessage('已保存，运行中的任务会在几秒内使用新设置。');}),
  note('默认1秒，可设0～30秒，支持小数。0为立即触发；大于0时等待松开并安静相应时间。连续按压只合并回复，不删除触摸记录。')
 ])];
 else if(page==='history')content=[
  card('互动记录',[
   UI.TextField({label:'日期（可选，YYYY-MM-DD）',value:historyDate,singleLine:true,onValueChange:setHistoryDate}),
   button('按日期查询',()=>loadHistory(false)),button('查看近期记录',async()=>{setHistoryDate('');await loadHistory(false,'');}),
   note(history.loading?'正在读取记录……':history.error?'读取失败：'+history.error:history.events.length?'已显示'+history.events.length+'条记录。':'没有找到记录；可换日期查询。'),
   ...(history.scope==='recent_index'?[note('当前为手机近期索引。按日期查询可读取已经归档的记录，设备离线也可查看。')]:[])
  ]),
  ...history.events.map((e,i)=>card((e.body_part||'未命名部位')+' · '+({start:'按下',end:'松开',summary:'持续按压'}[e.phase]||e.sensor_type||'事件'),[
   text(Number.isFinite(e.at)?new Date(e.at*1000).toLocaleString():'时间未确认'),
   note('CH'+(e.channel??'?')+' · '+(e.source==='simulation'?'模拟测试':e.source==='sensor'?'真实传感器':e.source||'来源未知')+
    (Number.isFinite(e.duration_ms)?' · 持续 '+(e.duration_ms/1000).toFixed(2)+' 秒':''))
  ])),
  ...(history.has_more?[button('加载下一页',()=>loadHistory(true))]:[])
 ];
 else if(page==='body')content=[
  card('身体与传感器',[note('“已接入”是内核保存的安装状态，不是凭读数判断。修改保留校准与其他端口。'),
   ...(!panel.port_writes?[note('当前固件不支持直接修改端口三态。可先打开设备设置，或升级固件后在此操作。')]:[]),
   button('刷新端口与读数',()=>refresh()),button('打开设备设置',()=>go('device'))]),
  ...ports.filter(c=>c.direction!=='output'&&c.type!=='vibration').map(c=>{
   const v=(panel.overview?.values||[]).find(x=>x.channel===c.channel);
   return card('CH'+c.channel+(c.mux_port!==undefined?' · J'+(c.mux_port+1):'')+' · '+({off:'关闭',simulation:'模拟',connected:'已接入'}[c.mode]||'待核对'),[
    UI.TextField({label:'对应部位',value:names[c.channel]??c.name,singleLine:true,onValueChange:value=>setNames({...names,[c.channel]:value})}),
    button('保存 CH'+c.channel+' 部位',async()=>{await call('update_port',{channel:c.channel,name:names[c.channel]??c.name});await refresh();setMessage('部位已保存，旧历史名称保持原样。');},panel.port_writes),
    ...[['off','关闭'],['connected','已接入'],['simulation','模拟（开发者）']].map(([m,label])=>button((c.mode===m?'✓ ':'')+label,
     async()=>{await call('update_port',{channel:c.channel,mode:m});await refresh();setMessage('CH'+c.channel+' 已设为'+label+'，重启后保留。');},
     panel.port_writes&&(m!=='simulation'||developer))),
    note(c.mode==='off'?'不采样、不触发回复。':c.mode==='simulation'?'只接受明确标记的模拟测试。':v?.active&&v.source==='sensor'&&v.quality==='ok'?'当前有真实按压。':'按一下可验证端口是否有响应。')
   ]);
  })
 ];
 else if(page==='persona')content=[card('触摸反馈的人设',[
  button((panel.preferences?.persona_source!=='doll'?'✓ ':'')+'跟随当前聊天（默认）',async()=>{await call('set_persona_source',{source:'chat'});await refresh();setMessage('触摸反馈跟随当前聊天人设。');}),
  UI.TextField({label:'娃娃人设',value:personaText,minLines:4,maxLines:10,singleLine:false,onValueChange:setPersonaText}),
  button('保存并使用娃娃人设',async()=>{if(!personaText.trim())throw Error('请先填写娃娃人设。');await call('set_persona_source',{source:'doll',text:personaText});await refresh();setMessage('娃娃人设已保存，仅用于身体互动反馈。');}),
  note('沿用原模型与话题，不改写原聊天的设置。不同连接各自保存娃娃人设。')
 ])];
 else if(page==='chat')content=[card('回复到哪个聊天',[
  text('当前：'+(state.chat?.title||'尚未绑定')),
  button('选择已有聊天',async()=>{const r=await call('list_chats');setChats((r.chats||[]).map(c=>({...c,isCurrent:c.id===r.currentChatId})));setCandidate(null);setMessage('选择聊天标题后确认绑定。');}),
  ...chats.map(c=>button((c.isCurrent?'当前 · ':'')+(c.title||'未命名聊天'),async()=>setCandidate(c))),
  ...(candidate?[button('确认绑定：'+candidate.title,async()=>{await call('bind_chat',{chat_id:candidate.id});setChats([]);setCandidate(null);await refresh(false);setMessage('已绑定，可直接回陪伴首页开启；发送诊断为可选。');})]:[]),
  button('原聊天发送自检',async()=>{const r=await call('schedule',{kind:'probe'});setMessage(r.message);}),
  button('我已看到自检输入和回复',async()=>{await call('confirm_probe');await refresh(false,false);setMessage('已记录诊断确认；陪伴无需此步骤。');})
 ])];
 else if(page==='connection')content=[card('设备与连接',[
  button('使用服务器／电脑',async()=>setMode('import')),button('仅用安卓手机',async()=>setMode('phone')),
  ...(mode==='phone'?[
   UI.TextField({label:'设备家庭 IP',value:host,placeholder:'IP 或设备设置页的固定 .local 名称',singleLine:true,onValueChange:setHost}),
   note('新版固件保存固定的 .local 连接名；家庭 IP 变化后优先按这个名称重连。手机无法解析时仍可填写当前 IP。'),
   button('连接家庭设备',async()=>{const r=await call('setup_device',{host,token:token||undefined});setToken('');await refresh();setMessage('已连接 '+r.label);}),
   button('高级：设备开启了登录保护',async()=>setAdvanced(!advanced)),
   ...(advanced?[UI.TextField({label:'设备页中的MCP令牌',value:token,isPassword:true,singleLine:true,onValueChange:setToken})]:[])
  ]:[button('导入服务器／电脑连接',pickConnection)]),
  ...(state.connection?.computer_host&&mode!=='phone'?[
   UI.TextField({label:'电脑 IP（电脑重启后可修改）',value:computerHost,singleLine:true,onValueChange:setComputerHost}),
   button('检查并保存电脑 IP',async()=>{const r=await call('update_computer_address',{host:computerHost});await refresh();setMessage(r.message);})
  ]:[]),
  button('设备状态与设置网页',()=>go('device')),note('电脑IP与设备IP不同。192.168.4.1仅在连接设备热点时有效。')
 ])];
 else if(page==='device')content=[card('设备状态与设置',[
  text('设备：'+(panel.overview?.device_id||'尚未读取')),text('状态：'+(panel.overview?.online?'在线':'离线或尚未确认')),
  text('设备家庭IP：'+(panel.overview?.device_ip||'暂无已确认地址')),
  ...(panel.overview?.device_hostname?[text('固定连接名：'+panel.overview.device_hostname)]:[]),
  text('已接入 '+ports.filter(c=>c.mode==='connected').length+' 路 · 模拟 '+ports.filter(c=>c.mode==='simulation').length+' 路'),
  ...(panel.settings_entries||[]).map(e=>button('打开'+(e.scope==='device_lan'?'设备设置页':'服务设置页'),async()=>{setWebUrl(e.url);setPage('web');})),
  ...(panel.settings_entries||[]).map(e=>note(e.access||'')),
  button('设备热点设置（需先连接热点）',async()=>{setWebUrl('http://192.168.4.1/');setPage('web');}),button('刷新状态',()=>refresh())
 ])];
 else if(page==='tests')content=[card('测试与帮助',[
  button('试摸一下',touchTest),button('一键检查',check),
  button('原聊天发送自检',async()=>{const r=await call('schedule',{kind:'probe'});setMessage(r.message);}),
  button('我已看到自检输入和回复',async()=>{await call('confirm_probe');await refresh(false);setMessage('确认已保存。');}),
  button('核对上次发送结果',()=>go('recovery')),note('发送自检为可选诊断，不需要测试或手动确认即可开启陪伴。真实输入测试不发送聊天，模拟在开发者选项。')
 ])];
 else if(page==='recovery')content=[card('核对原聊天',[
  note('请先查看原聊天。结果不明时不自动重发。'),
  ...[['delivered','确认已收到'],['not_sent','确认未发送'],['discard','放弃本次反馈']].map(([decision,label])=>
   button(label,async()=>{const r=await call('recover',{decision});await refresh(false,false);setMessage(r.message);}))
 ])];
 else if(page==='developer'&&developer)content=[card('开发者工具',[
  button('读取实时数值、端口与任务诊断',async()=>setDiagnostic(JSON.stringify(await call('diagnostics'),null,2))),
  button('模拟测试与硬件高级设置（设备页）',()=>go('device')),
  button('升级：选择旧发送记录（可选）',async()=>{
   const r=await ctx.openFilePicker({picker:'document',mimeTypes:['application/json'],allowMultiple:false});if(r?.cancelled)return;
   if(!r?.files?.[0]?.path)throw Error('未取得旧记录文件。');await call('import_legacy_state',{legacy_file:r.files[0].path});setMessage('旧记录已导入，原文件保留。');
  }),text(diagnostic||'只读诊断。开发者选项开启后，可在端口页选择模拟。',{fontFamily:'monospace',fontSize:12})
 ])];
 const connectionLabels={unconfigured:'尚未配置连接',checking:'正在检查连接',stale:'上次状态，正在重新检查',unreachable:'当前连接不可达',online:'● 在线',device_offline:'服务已连接 · 设备离线'};
 return UI.LazyColumn({key:'ai-doll-settings',onLoad:onEnter,padding:16,spacing:12,fillMaxSize:true,background:colors.background},[
  title('AI Doll'),note((connectionLabels[state.connection_state]||'正在检查连接')+' · '+(source[state.connection?.mode]||'尚未连接')),
  row(['陪伴','设置'].map((name,i)=>UI.Button({text:name,enabled:!busy,onClick:()=>action(()=>go(i?'settings':'home')),weight:1}))),
  button('停止后台任务',stopTasks),
  ...(!['home','settings'].includes(page)?[button('返回设置',()=>go('settings'))]:[]),
  ...(message?[text(message)]:[]),...content,
  note('常开依赖Operit后台运行。手机暂停时如实显示暂停，不把开关已开当作持续收到事件。')
 ]);
}
exports.default=Screen;

