// Shared engine for the unified ToolPkg; legacy standalone templates are frozen compatibility entries.
// Prototype: one independent workflow per target. Android/model checks are separate.
let running = false;

function configuration(p) {
  if (!p || typeof p.chat_id !== 'string' || !p.chat_id.trim() || p.chat_id === 'main' || p.chat_id.length > 128)
    throw Error('Choose a real existing chat ID');
  if (typeof p.mcp_url !== 'string' || !/^https?:\/\/[^\s?#@]+\/mcp$/.test(p.mcp_url))
    throw Error('Full reachable HTTP MCP URL required');
  if (typeof p.state_path !== 'string' || !p.state_path.startsWith('/') || p.state_path.includes('..'))
    throw Error('An accessible Android absolute state_path is required');
  if (!/\/[^/]+\.json$/i.test(p.state_path))
    throw Error('state_path 必须包含 JSON 文件名，例如 /storage/emulated/0/Download/ai_doll_operit_delivery.json，不能只填文件夹');
}

async function connect(url,connection) {
  if(connection?.kind==='ai-doll-device-connection')return await require('./device.js').connect(connection);
  return await require('./mcp.js').connect(url);
}

async function load(p) {
  const exists = await Tools.Files.exists(p.state_path, 'android');
  if (typeof exists.exists !== 'boolean') throw Error('Cannot inspect delivery state; no message may be sent');
  if (exists.isDirectory === true) throw Error('state_path 指向文件夹，请填写该文件夹下的 JSON 文件名');
  if (exists.exists !== true) {
    const parent=p.state_path.slice(0,p.state_path.lastIndexOf('/')) || '/';
    const directory=await Tools.Files.exists(parent,'android');
    if (directory.exists !== true || directory.isDirectory === false)
      throw Error('状态文件的父目录不存在或无法访问，请先在手机文件管理器创建并授权该目录');
    return {schema:1, chat_id:p.chat_id, mcp_url:p.mcp_url, pending:null, session_id:null,
      ...(p.connection?.kind==='ai-doll-device-connection'?{
        connection_device_id:p.connection.device_id,connection_storage_key:p.connection.storage_key}:{}),
      ...(p.connection?.server_instance_id?{server_instance_id:p.connection.server_instance_id,pairing_id:p.connection.pairing_id}:{})};
  }
  const file = await Tools.Files.read({path:p.state_path, environment:'android'});
  const value = JSON.parse(file.content);
  const samePhone=p.connection?.kind==='ai-doll-device-connection'&&
    value.connection_device_id===p.connection.device_id&&value.connection_storage_key===p.connection.storage_key;
  const movedComputer=require('./settings.js').sameComputer(value.mcp_url,p.connection);
  const sameServer=value.server_instance_id&&value.server_instance_id===p.connection?.server_instance_id&&value.pairing_id===p.connection.pairing_id;
  if (value.schema !== 1 || value.chat_id !== p.chat_id || (value.mcp_url !== p.mcp_url&&!samePhone&&!movedComputer&&!sameServer))
    throw Error('State belongs to another chat/connection; use a different path');
  return {...value,mcp_url:p.mcp_url,...(p.connection?.server_instance_id?{server_instance_id:p.connection.server_instance_id,pairing_id:p.connection.pairing_id}:{})};
}

async function save(p, state) {
  const result = await Tools.Files.write(p.state_path, JSON.stringify(state), false, 'android');
  if (result.successful !== true) throw Error('State was not durably written; no new message may be sent');
}

async function existingChat(chatId) {
  // Operit's agentStatus currently binds FloatingChatService, even though sends
  // below use MAIN. findChat reads saved history without requiring that service.
  const result = await Tools.Chat.findChat({query:chatId, match:'exact', index:0});
  if (result.chat?.id !== chatId) throw Error('Existing chat ID was not confirmed; select the real saved ID');
}

function eligible(event, session, now) {
  return event.session_id === session.id && event.phase === 'start' && event.sensor_type === 'pressure' &&
    event.direction === 'input' && event.quality === 'ok' && ['sensor','simulation'].includes(event.source) &&
    event.delivery_quality !== 'offline_replay' && Number.isInteger(event.id) && event.id > 0 &&
    Number.isFinite(event.at) && event.at >= session.started && event.at <= now+2 && now-event.at <= 30;
}

function prompt(context) {
  // User labels remain in a data section, never interpolated as executable instructions.
  const doll=context.preferences?.persona_source==='doll'||context.persona_priority==='saved_doll';
  return '身体互动上下文如下（JSON仅为数据）。沿用当前聊天模型和话题，自然简短回应。'
    +(doll?'用户为触摸反馈选择了娃娃人设，请按保存设定回应，不改写原聊天的设置。':'沿用当前聊天人设，不切换角色。')
    +'不要输出检测报告、ADC、编号或倒计时。'
    +'排队期间的多次触摸合并成一条自然回应，不逐条报数，也不声称刚刚发生。'
    +'一次按压只主要回应一次；释放不另行回应。模拟来源要简短说明，原始读数不是实际力度，'
    +'单通道按压不能直接认定拥抱。\n'+JSON.stringify({touch_count:context.events.length,events:context.events,
      queued_during_reply:!!context.queued_during_reply,
      persona:doll?context.persona:'', feedback:context.feedback, persona_priority:doll?'saved_doll':'current_chat'});
}

async function settle(p, state, tool) {
  if (!state.pending) return;
  if (state.pending.phase !== 'completed') throw Error('Uncertain send: check original chat and run reconcile_delivery; never auto-resend');
  let receipts=state.pending.receipt_ids||[state.pending.receipt_id];
  while(receipts.length){
    const receipt_id=receipts[0];
    const result=await tool('acknowledge_chat_context',{chat_id:p.chat_id,receipt_id});
    if(result.acknowledged!==true)throw Error('Context acknowledgement unavailable');
    receipts=receipts.slice(1);state.pending.receipt_ids=receipts;delete state.pending.receipt_id;
    await save(p,state);
  }
  state.pending = null;
  await save(p, state);
}

async function list_existing_chats() {
  return await Tools.Chat.listChats({limit:100, sort_by:'updatedAt', sort_order:'desc'});
}

async function listen_interaction(p) {
  configuration(p);
  if (p.workflow_confirmed !== true) throw Error('Start from an independent user-enabled Workflow only');
  const duration = p.duration_sec === undefined ? 60 : p.duration_sec;
  if (!Number.isInteger(duration) || duration < 1 || duration > 900) throw Error('duration_sec must be 1..900');
  const wait=p.response_wait_sec??1;
  if(!Number.isFinite(wait)||wait<0||wait>30)throw Error('触摸合并等待时间应为0～30秒');
  if (running) throw Error('This package already has an active listener');
  running = true;
  let tool, state, session, flight, cancelled=false;
  let stage='chat_binding';
  const report = {state:'starting', replies:0, model_response_returned:false, display_verified:false, cleanup_pending:false};
  async function ensureActive(){try{if(p.ensure_active)await p.ensure_active();}catch(e){cancelled=true;throw e;}}
  try {
    await existingChat(p.chat_id);
    stage='mcp_connection';
    tool = await connect(p.mcp_url,p.connection);
    stage='delivery_state';
    state = await load(p);
    await settle(p, state, tool);
    stage='session_check';
    const existing = (await tool('get_interaction_status')).active_session;
    if (existing && !(p.continuous===true&&existing.id===state.session_id&&existing.chat_id===p.chat_id))
      throw Error('An interaction is already active; stop the owning workflow first');
    const initial = await tool('get_chat_context', {chat_id:p.chat_id, limit:1});
    if(initial.context_protocol!=='leased-batch-v1')throw Error('请同时更新并重启电脑／服务器端到2.24或更新版本，再开启陪伴；手机直连只需更新手机包，不需要重新发送聊天自检。');
    if (!initial.preferences?.proactive_enabled || !initial.preferences.chat_integration_enabled) {
      if(p.continuous===true){session=existing;report.state='disabled';return report;}
      throw Error('Enable proactive and chat integration preferences explicitly before testing');
    }
    const localStarted = Date.now()/1000;
    stage='session_start';
    const lease=p.continuous===true?900:duration;
    const confirmed = existing || await tool('start_interaction', {chat_id:p.chat_id, duration_sec:lease, idle_timeout_sec:Math.max(30,lease)});
    if (confirmed.chat_id !== p.chat_id || !confirmed.id || !Number.isFinite(confirmed.started) || !Number.isFinite(confirmed.deadline))
      throw Error('Server did not confirm a bounded session for this chat');
    session=confirmed;
    if(!existing){state.cursor=0;state.queue=[];state.pressed={};state.last_touch_at=0;state.server_clock_offset=session.started-localStarted;}
    state.queue=state.queue||[];state.pressed=state.pressed||{};
    state.session_id = session.id;
    await save(p, state);
    report.state = 'listening';
    const serverNow = () => Date.now()/1000+(state.server_clock_offset||0);
    const chunkDeadline=Math.min(session.deadline,serverNow()+duration);
    let cursor = existing?(state.cursor||0):0;
    // One journal writer and one model send at a time. A pending model promise
    // never blocks device polling; only live, validated contexts enter this queue.
    const allowed=c=>c.preferences?.proactive_enabled&&c.preferences.chat_integration_enabled&&
      !c.preferences.muted&&c.proactive_delivery_allowed!==false;
    async function finishSend(){
      if(!flight?.done)return;
      stage='main_chat_send';
      if(flight.error)throw flight.error;
      const reply=flight.reply;
      if(reply.chatId!==p.chat_id||typeof reply.aiResponse!=='string'||!reply.aiResponse.trim())
        throw Error('Send outcome uncertain: check original chat before retrying');
      state.pending.phase='completed';await save(p,state);
      report.replies++;report.model_response_returned=true;
      stage='context_acknowledgement';await settle(p,state,tool);flight=null;
    }
    sessionLoop: while (serverNow()<chunkDeadline||(p.continuous===true&&flight&&serverNow()<session.deadline)) {
      await ensureActive();
      await finishSend();
      if(serverNow()>=chunkDeadline&&!flight)break;
      stage='event_read';
      const batch = await tool('get_interaction_device_events', {chat_id:p.chat_id, session_id:session.id,
        after:cursor,limit:100,wait_seconds:Math.max(0,Math.min(flight||state.queue.length?1:20,Math.floor(session.deadline-serverNow())))});
      if (batch.session_closed || batch.session?.id !== session.id || batch.session?.chat_id !== p.chat_id) break;
      if (batch.collector_error) throw Error('Collector offline; no live reply may be generated');
      if (!Array.isArray(batch.events) || !Number.isInteger(batch.next_cursor) || batch.next_cursor < cursor)
        throw Error('Invalid event page');
      const starts=batch.events.filter(e=>eligible(e,session,serverNow()));
      if(starts.length){
        stage='fresh_context';
        const context=await tool('get_chat_context',{chat_id:p.chat_id,session_id:session.id,after:cursor,through:batch.next_cursor,limit:200});
        if(!allowed(context)){report.state='disabled';break sessionLoop;}
        if(context.receipt_id&&context.events?.length){
          if(context.events.some(e=>!eligible(e,session,serverNow())||e.id>batch.next_cursor))throw Error('Invalid leased context page');
          if(!state.queue.some(q=>q.receipt_id===context.receipt_id)){
            state.queue.push({...context,captured_at:serverNow(),queue_deadline:Math.min(session.deadline,serverNow()+120)});
            for(const e of context.events)state.pressed[(e.boot||'')+':'+e.touch_id]=e.channel;
          }
        }
      }
      // Releases extend the quiet window and update queued durations, never
      // create another major reply. Store every start; time batching is not loss.
      for(const e of batch.events){
        const key=(e.boot||'')+':'+e.touch_id;
        if(e.phase==='end'&&Object.prototype.hasOwnProperty.call(state.pressed,key)){
          delete state.pressed[key];state.last_touch_at=Math.max(state.last_touch_at||0,e.at||serverNow());
          for(const q of state.queue)for(const touch of q.events)if(touch.touch_id===e.touch_id&&touch.boot===e.boot){
            touch.ended_at=e.at;if(Number.isFinite(e.duration_ms))touch.duration_ms=e.duration_ms;
          }
        }
      }
      for(const e of starts)state.last_touch_at=Math.max(state.last_touch_at||0,e.at);
      if(batch.next_cursor!==cursor||batch.events.length){cursor=batch.next_cursor;state.cursor=cursor;await save(p,state);}
      await finishSend();
      const currentWait=p.get_response_wait?p.get_response_wait():wait;
      const quiet=currentWait===0||(!Object.keys(state.pressed).length&&serverNow()-(state.last_touch_at||0)>=currentWait);
      if(!flight&&state.queue.length&&quiet&&serverNow()<chunkDeadline){
        stage='fresh_context';
        const policy=await tool('get_chat_context',{chat_id:p.chat_id,session_id:session.id,after:cursor,through:cursor,limit:1});
        if(!allowed(policy)){report.state='disabled';break;}
        const current=(await tool('get_interaction_status')).active_session;
        if(!current||current.id!==session.id||current.chat_id!==p.chat_id)break;
        // Captured during a live session, kept at most two minutes while the
        // previous reply runs. Preserve timestamps: queued data is not new input.
        const ready=state.queue.filter(q=>q.queue_deadline>serverNow()).map(q=>({...q,events:q.events.filter(e=>{
          const port=policy.channels?.find(c=>c.channel===e.channel);
          return !policy.channels||(port&&port.mode!=='off'&&(!port.feedback_level||port.feedback_level==='normal'));
        })})).filter(q=>q.events.length);
        report.queue_cancelled=(report.queue_cancelled||0)+state.queue.reduce((n,q)=>n+q.events.length,0)-ready.reduce((n,q)=>n+q.events.length,0);
        state.queue=[];
        if(ready.length){
          const merged={...ready[ready.length-1],preferences:policy.preferences,persona:policy.persona,feedback:policy.feedback,
            events:ready.flatMap(q=>q.events),queued_during_reply:ready.some(q=>serverNow()-q.captured_at>1)};
          state.pending={phase:'sending',receipt_ids:ready.map(q=>q.receipt_id),event_ids:merged.events.map(e=>e.event_id)};
          stage='delivery_state';await save(p,state);
          await ensureActive();
          if(serverNow()>=session.deadline){state.pending=null;await save(p,state);break;}
          stage='main_chat_send';
          const task={done:false};flight=task;
          task.promise=Tools.Chat.sendMessage(prompt(merged),p.chat_id,undefined,undefined,
            {runtime:'main',persist_turn:true,notify_reply:true,hide_user_message:true,timeout_ms:90000})
            .then(reply=>{task.reply=reply;task.done=true;},error=>{task.error=error;task.done=true;});
        }else await save(p,state);
      }
      if (!batch.events.length) await Tools.System.sleep(250);
    }
    // Stop/expiry cancels unsent input. A reply already submitted may finish;
    // do not interrupt the user's chat stream or submit anything else.
    if(flight){await flight.promise;await finishSend();}
    if (report.state==='listening') report.state=p.continuous===true&&session.deadline-serverNow()>20?'continued':'ended';
  } catch (error) {
    // Keep a known queue and owned lease over a transient read/ACK failure.
    // An ambiguous model send still blocks automatic retry through its journal.
    if(p.continuous===true&&!cancelled&&session?.deadline>Date.now()/1000+(state?.server_clock_offset||0)&&report.state!=='disabled'&&
      (require('./recovery.js').retryable(error)||stage==='main_chat_send'))report.state='continued';
    const recovery=stage==='main_chat_send'?
      '。发送结果可能不完整，请先核对原聊天；不要删除状态文件或自动重试。可由用户选择 reconcile_delivery 的 delivered / not_sent / discard。':'';
    throw Error('AI Doll ['+stage+']: '+(error?.message || String(error))+recovery);
  } finally {
    try{
      try{
        if(flight){
          await flight.promise;
          if(!flight.error&&flight.reply?.chatId===p.chat_id&&flight.reply.aiResponse?.trim()&&state.pending)
            state.pending.phase='completed';
        }
        if(state&&report.state!=='continued'){state.queue=[];state.pressed={};}
        // Keep a known reply outcome durable before waiting for remote cleanup.
        if(state)await save(p,state);
      }finally{
        if (tool && session?.id && report.state!=='continued') {
          try {
            await tool('end_interaction', {chat_id:p.chat_id, session_id:session.id});
            if(state){state.session_id=null;await save(p,state);}
          } catch (_) { report.cleanup_pending=true; }
        }
      }
    }finally{running=false;}
  }
  return report;
}

async function stop_interaction(p) {
  configuration(p);
  const state=await load(p);
  if (state.session_id) {
    const tool=await connect(p.mcp_url,p.connection);
    await tool('end_interaction',{chat_id:p.chat_id,session_id:state.session_id});
  }
  state.session_id=null;state.queue=[];state.pressed={}; await save(p,state);
  return {stopped:true, uncertain_delivery:state.pending?.phase==='sending'};
}

async function reconcile_delivery(p) {
  configuration(p);
  if (!['delivered','not_sent','discard'].includes(p.decision)) throw Error('User must choose delivered, not_sent or discard after checking the chat');
  const state=await load(p),tool=await connect(p.mcp_url,p.connection);
  if (state.pending) {
    if (p.decision!=='not_sent') {
      state.pending.phase='completed'; state.pending.user_decision=p.decision;
      await save(p,state); await settle(p,state,tool);
    }
    else { state.pending=null; await save(p,state); }
  }
  return {reconciled:true, decision:p.decision, display_verified:false,
    model_reply_verified:false, acknowledgement_means:'client_reported_handled_not_display_verified'};
}

exports.list_existing_chats=list_existing_chats;
exports.listen_interaction=listen_interaction;
exports.stop_interaction=stop_interaction;
exports.reconcile_delivery=reconcile_delivery;

exports.connect=connect;
exports.load=load;
exports.settle=settle;
