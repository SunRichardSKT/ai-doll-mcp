// Configuration surface only: all replies stay in the user's existing chat.
async function Screen(ctx) {
  const UI=ctx.UI;
  const [message,setMessage]=ctx.useState('message','选择连接方式，再绑定已有聊天。服务器与仅手机模式都不需要电脑常开。');
  const [chats,setChats]=ctx.useState('chats',[]);
  const [candidate,setCandidate]=ctx.useState('candidate',null);
  const [busy,setBusy]=ctx.useState('busy',false);
  const [binding,setBinding]=ctx.useState('binding','尚未绑定');
  const [loaded,setLoaded]=ctx.useState('loaded',false);
  const [mode,setMode]=ctx.useState('setupMode','import');
  const [host,setHost]=ctx.useState('deviceHost','');
  const [token,setToken]=ctx.useState('deviceToken','');
  const [advanced,setAdvanced]=ctx.useState('advanced',false);
  const [duration,setDuration]=ctx.useState('duration',60);
  let displayBinding=binding,displayMessage=message;
  async function call(name,params={}) {
    // Tools are registered under the subpackage ID. The container owns this UI
    // but has no tools. Operit 1.12.2's resolver can fall back to packageName
    // without the subpackage. Use one exact target, without retrying writes.
    let result=await ctx.callTool('ai_doll_companion:'+name,params);
    // Some host versions return a native envelope, others unwrap its data.
    if (result?.success===false) throw Error(result.error||result.message||'操作未完成');
    if (result?.data!==undefined && !result.configured && !result.saved) result=result.data;
    if (typeof result==='string') {try {result=JSON.parse(result);} catch (_) {throw Error(result);}}
    return result;
  }
  async function action(fn) {
    if (busy) return;
    setBusy(true);
    try {await fn();} catch(e) {setMessage(String(e.message||e));}
    finally {setBusy(false);}
  }
  const button=(text,fn)=>UI.Button({text,enabled:!busy,onClick:()=>action(fn)});
  async function inspect() {
    const r=await call('status');
    setDuration(r.duration_sec||60);
    setBinding(r.chat?.title||'尚未绑定');
    const phases={scheduled:'已安排，等待手机调度',running:'运行中',completed:'已完成',failed:'未完成',
      expired:'启动已过期，请重新开始',interrupted:'上次任务中断，请检查恢复',stopped:'已停止',stopping:'停止待核对'};
    const sources={simulation:'电脑模拟演示',server:'服务器直传，无需电脑',phone:'手机直连家庭设备，无需电脑与服务器',device:'电脑采集'};
    setMessage((r.configured?'连接：'+(sources[r.connection.mode]||'已保存'):'请选择连接方式')+
      '\n后台自检：'+(r.background_user_confirmed?'你已确认收到':'待在原聊天确认')+
      '\n任务：'+(phases[r.job?.phase]||'未启动')+(r.job?.error?'\n'+r.job.error:'')+
      (r.uncertain_delivery?'\n有未确认的发送，请先核对原聊天。':''));
  }
  if (!loaded) {
    try {
      const saved=await call('status');
      setDuration(saved.duration_sec||60);
      displayBinding=saved.chat?.title||'尚未绑定';setBinding(displayBinding);
      displayMessage=saved.configured?'已恢复保存的连接和聊天。可以查看状态、检查连接或开始互动。':message;
      if (saved.uncertain_delivery) displayMessage='存在未确认的发送，请先核对原聊天，再使用恢复按钮。';
      setMessage(displayMessage);
    } catch(e) {displayMessage=String(e.message||e);setMessage(displayMessage);}
    setLoaded(true);
  }
  return UI.LazyColumn({padding:16,spacing:10},[
    UI.Text({text:'AI Doll · 原聊天陪伴',fontSize:22,bold:true}),
    UI.Text({text:'只管理连接与身体互动，沿用原聊天的模型和人设。'}),
    UI.Text({text:displayMessage}),UI.Text({text:'绑定聊天：'+displayBinding}),
    UI.Text({text:'1 · 连接方式',bold:true}),
    button('使用服务器／电脑',async()=>{setMode('import');setMessage('在服务器设备管理页下载 Operit 连接文件，或使用电脑导出的文件。手机导入一次即可。');}),
    button('仅用安卓手机',async()=>{setMode('phone');setMessage('手机与设备连接同一家庭 Wi-Fi。填写设备设置页显示的家庭 IP；不会修改采样、校准或输出开关。');}),
    ...(mode==='phone'?[
      UI.TextField({label:'设备家庭 IP',value:host,placeholder:'例如 192.168.1.50',singleLine:true,onValueChange:setHost}),
      button('连接家庭设备',async()=>{const r=await call('setup_device',{host,token:token||undefined});setToken('');setMessage('已连接 '+r.label+'。下一步选择已有聊天。');}),
      button('高级：设备开启了登录保护',async()=>setAdvanced(!advanced)),
      ...(advanced?[UI.TextField({label:'设备页中的 MCP 令牌',value:token,isPassword:true,singleLine:true,onValueChange:setToken})]:[]),
      UI.Text({text:'家庭 IP 在设备设置页查看；192.168.4.1 仅在连接设备热点时有效。家中路由器可为设备固定租约，减少 IP 变化。'})
    ]:[button('导入服务器／电脑连接',async()=>{
      const selected=await ctx.openFilePicker({picker:'document',mimeTypes:['application/json'],allowMultiple:false});
      if (selected?.cancelled) return;
      const item=selected?.files?.[0];
      if (!item) return;
      if (!item.path) throw Error('文件选择器未提供可读的本地文件，请更新 Operit。');
      const r=await call('setup',{connection_file:item.path});setMessage('连接已保存：'+r.label+'。下一步绑定聊天。');
    })]),
    UI.Text({text:'2 · 绑定原聊天',bold:true}),
    button('选择已有聊天',async()=>{
      const r=await call('list_chats');setChats(r.chats||[]);
      setMessage('选择聊天标题后再确认绑定；当前聊天会标注在列表中。');
      setCandidate(null);
      setChats((r.chats||[]).map(c=>({...c,isCurrent:c.id===r.currentChatId})));
    }),
    ...chats.map(chat=>button((chat.isCurrent?'当前 · ':'')+(chat.title||'未命名聊天'),async()=>{
      setCandidate(chat);setMessage('准备绑定“'+(chat.title||'未命名聊天')+'”，请点击下面的确认按钮。');
    })),
    ...(candidate?[button('确认绑定：'+(candidate.title||'未命名聊天'),async()=>{
      const r=await call('bind_chat',{chat_id:candidate.id});setBinding(r.chat.title);
      setChats([]);setCandidate(null);setMessage('已绑定。先点一键检查，再运行原聊天自检。');
    })]:[]),
    button('一键检查',async()=>{
      const r=await call('check_connection');
      setMessage('文件、聊天与 MCP 连接检查通过，工作流已自动准备。\n设备状态：'+
        (r.overview.online?'在线':'离线或缓存')+'。后台实际回复仍需单独自检。');
    }),
    button('原聊天发送自检',async()=>{const r=await call('schedule',{kind:'probe'});setMessage(r.message);}),
    button('我已看到自检输入和回复',async()=>{await call('confirm_probe');setMessage('已保存你的确认，可以开始有限互动测试。');}),
    UI.Text({text:'3 · 日常互动',bold:true}),
    button('开启触摸回应',async()=>{await call('set_experience',{enabled:true});setMessage('已开启聊天融入与触摸回应。请在已确认的原聊天中开始互动。');}),
    button('关闭触摸主动回应',async()=>{await call('set_experience',{enabled:false});setMessage('已停止互动并关闭主动回应，聊天融入保持开启。');}),
    UI.Text({text:'互动时长：'+(duration===900?'15 分钟':'1 分钟')}),
    ...[[60,'1 分钟测试'],[900,'15 分钟陪伴']].map(([seconds,title])=>button(title,async()=>{
      await call('set_experience',{duration_sec:seconds});setDuration(seconds);setMessage('时长已保存，下次开始生效。');
    })),
    button(duration===60?'开始互动 · 60 秒':'开始互动 · 15 分钟',async()=>{const r=await call('schedule',{kind:'interaction'});setMessage(r.message);}),
    button('停止互动',async()=>{const r=await call('stop');setMessage(r.message);}),
    button('查看状态',inspect),
    button('查看互动记录',async()=>{
      const r=await call('view_history');
      setMessage((r.history_source==='android_local'?'手机已采集的近期记录':'服务器／电脑历史，本页最多 20 条')+'\n'+
        ((r.events||[]).map(e=>(Number.isFinite(e.at)?new Date(e.at*1000).toISOString().slice(0,19).replace('T',' ')+' UTC · ':'')+
          (e.body_part||'未命名部位')+' · '+(e.phase==='start'?'按下':e.phase==='end'?'松开':e.phase||'事件')+
          (e.source==='simulation'?' · 模拟':'' )).join('\n')||'暂时没有记录'));
    }),
    UI.Text({text:'电脑模式需要电脑运行；服务器模式需要服务器运行；仅手机模式需要 Operit 在同一网络内运行。请允许 Operit 后台活动；锁屏与省电限制可能中断互动，到期不会自动续开。'}),
    UI.Text({text:'发送结果不明确时：先在原聊天核对，再选择恢复。不会自动重发。',bold:true}),
    button('确认已收到',async()=>{await call('recover',{decision:'delivered'});await inspect();}),
    button('确认未发送',async()=>{await call('recover',{decision:'not_sent'});await inspect();}),
    button('放弃本次反馈',async()=>{await call('recover',{decision:'discard'});await inspect();})
    ,button('升级：选择旧发送记录（可选）',async()=>{
      const selected=await ctx.openFilePicker({picker:'document',mimeTypes:['application/json'],allowMultiple:false});
      if (selected.cancelled) return;
      if (!selected.files?.[0]?.path) throw Error('未取得可读的旧记录文件。');
      const r=await call('import_legacy_state',{legacy_file:selected.files[0].path});
      setMessage(r.uncertain_delivery?'旧记录已保留导入。请先核对原聊天后恢复，未自动重发。':'旧记录已导入，原文件保留。');
    })
  ]);
}
exports.default=Screen;
