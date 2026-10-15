/* METADATA
{
  "name": "ai_doll_prototype",
  "description": "局域网 60 秒主动陪伴原型。仅从独立 Workflow 启动，向用户选择的已有主聊天发送触摸上下文；不创建聊天、不配置第二个模型。",
  "category": "NETWORK",
  "tools": [
    {"name":"list_existing_chats","description":"列出已有聊天以取得真实 chat_id；不创建或切换聊天。","parameters":[]},
    {"name":"listen_interaction","description":"仅独立工作流使用，禁止在目标 AI 正在执行的工具轮里调用。运行期间读取新压力，触发原聊天回应；默认60秒。","parameters":[{"name":"mcp_url","description":"手机可达的 AI Doll interaction HTTP MCP 完整地址","type":"string","required":true},{"name":"chat_id","description":"list_existing_chats 返回的已有聊天ID","type":"string","required":true},{"name":"state_path","description":"Operit有读写权限的Android文件绝对路径；保存发送恢复状态，同一目标只运行一个工作流","type":"string","required":true},{"name":"workflow_confirmed","description":"用户从独立Workflow启动时明确填true，不能从AI工具轮递归启动","type":"boolean","required":true},{"name":"duration_sec","description":"1至60秒，默认60","type":"number","required":false}]},
    {"name":"stop_interaction","description":"结束本原型拥有的会话；保留发送恢复状态。","parameters":[{"name":"mcp_url","description":"原完整MCP地址","type":"string","required":true},{"name":"chat_id","description":"原聊天ID","type":"string","required":true},{"name":"state_path","description":"原状态文件路径","type":"string","required":true}]},
    {"name":"reconcile_delivery","description":"用户核对原聊天后恢复。delivered补确认；not_sent仅确认未发送时使用；discard放弃本次触摸并标记已处理，不证明回复已展示。不会立即重新生成。","parameters":[{"name":"mcp_url","description":"原完整MCP地址","type":"string","required":true},{"name":"chat_id","description":"原聊天ID","type":"string","required":true},{"name":"state_path","description":"原状态文件路径","type":"string","required":true},{"name":"decision","description":"delivered、not_sent或discard；必须由用户核对后选择","type":"string","required":true}]}
  ]
}
*/
// Prototype: one independent workflow per target. Android/model checks are separate.
let running = false;
let requestId = 0;

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

async function rpc(url, method, params, version) {
  const id = method === 'notifications/initialized' ? undefined : ++requestId;
  const response = await Tools.Net.http({url, method:'POST', follow_redirects:false, ignore_ssl:false,
    headers:{'Content-Type':'application/json', Accept:'application/json, text/event-stream',
      ...(version ? {'MCP-Protocol-Version':version} : {})},
    body:JSON.stringify({jsonrpc:'2.0', ...(id === undefined ? {} : {id}), method, params}),
    connect_timeout:10000, read_timeout:30000});
  if (response.statusCode < 200 || response.statusCode >= 300) throw Error('MCP HTTP '+response.statusCode);
  if (id === undefined) return null;
  const body = JSON.parse(response.content);
  if (body.id !== id || body.error || body.result?.isError) throw Error('MCP rejected request');
  return body.result;
}

async function connect(url) {
  const hello = await rpc(url, 'initialize', {protocolVersion:'2025-11-25', capabilities:{},
    clientInfo:{name:'ai-doll-operit-prototype', version:'0.1.4'}});
  await rpc(url, 'notifications/initialized', {}, hello.protocolVersion);
  return async (name, args={}) => {
    const reply = await rpc(url, 'tools/call', {name, arguments:args}, hello.protocolVersion);
    if (reply.structuredContent) return reply.structuredContent;
    const content = reply.content?.find(x => x.type === 'text');
    if (!content) throw Error('MCP returned no structured data');
    return JSON.parse(content.text);
  };
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
    return {schema:1, chat_id:p.chat_id, mcp_url:p.mcp_url, pending:null, session_id:null};
  }
  const file = await Tools.Files.read({path:p.state_path, environment:'android'});
  const value = JSON.parse(file.content);
  if (value.schema !== 1 || value.chat_id !== p.chat_id || value.mcp_url !== p.mcp_url)
    throw Error('State belongs to another chat/connection; use a different path');
  return value;
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
  return '身体互动上下文如下（JSON仅为数据）。沿用当前聊天的模型、人设、话题自然简短回应，'
    +'已有人设优先，保存的人设只补空缺。不要输出检测报告、ADC、编号或倒计时。'
    +'一次按压只主要回应一次；释放不另行回应。模拟来源要简短说明，原始读数不是实际力度，'
    +'单通道按压不能直接认定拥抱。\n'+JSON.stringify({events:context.events,
      persona:context.persona, feedback:context.feedback, persona_priority:'current_chat'});
}

async function settle(p, state, tool) {
  if (!state.pending) return;
  if (state.pending.phase !== 'completed') throw Error('Uncertain send: check original chat and run reconcile_delivery; never auto-resend');
  const result = await tool('acknowledge_chat_context', {chat_id:p.chat_id, receipt_id:state.pending.receipt_id});
  if (result.acknowledged !== true) throw Error('Context acknowledgement unavailable');
  state.pending = null;
  await save(p, state);
}

async function list_existing_chats() {
  complete(await Tools.Chat.listChats({limit:30, sort_by:'updatedAt', sort_order:'desc'}));
}

async function listen_interaction(p) {
  configuration(p);
  if (p.workflow_confirmed !== true) throw Error('Start from an independent user-enabled Workflow only');
  const duration = p.duration_sec === undefined ? 60 : p.duration_sec;
  if (!Number.isInteger(duration) || duration < 1 || duration > 60) throw Error('duration_sec must be 1..60');
  if (running) throw Error('This package already has an active listener');
  running = true;
  let tool, state, session;
  let stage='chat_binding';
  const report = {state:'starting', replies:0, model_response_returned:false, display_verified:false, cleanup_pending:false};
  try {
    await existingChat(p.chat_id);
    stage='mcp_connection';
    tool = await connect(p.mcp_url);
    stage='delivery_state';
    state = await load(p);
    await settle(p, state, tool);
    stage='session_check';
    const existing = (await tool('get_interaction_status')).active_session;
    if (existing) throw Error('An interaction is already active; stop the owning workflow first');
    const initial = await tool('get_chat_context', {chat_id:p.chat_id, limit:1});
    if (!initial.preferences?.proactive_enabled || !initial.preferences.chat_integration_enabled)
      throw Error('Enable proactive and chat integration preferences explicitly before testing');
    const localStarted = Date.now()/1000;
    stage='session_start';
    const confirmed = await tool('start_interaction', {chat_id:p.chat_id, duration_sec:duration});
    if (confirmed.chat_id !== p.chat_id || !confirmed.id || !Number.isFinite(confirmed.started) || !Number.isFinite(confirmed.deadline))
      throw Error('Server did not confirm a bounded session for this chat');
    session=confirmed;
    state.session_id = session.id;
    await save(p, state);
    report.state = 'listening';
    const serverNow = () => session.started + (Date.now()/1000-localStarted);
    let cursor = 0;
    sessionLoop: while (serverNow() < session.deadline) {
      stage='event_read';
      const batch = await tool('get_interaction_device_events', {chat_id:p.chat_id, session_id:session.id,
        after:cursor, limit:50, wait_seconds:Math.max(0,Math.min(20,Math.floor(session.deadline-serverNow())))});
      if (batch.session_closed || batch.session?.id !== session.id || batch.session?.chat_id !== p.chat_id) break;
      if (batch.collector_error) throw Error('Collector offline; no live reply may be generated');
      if (!Array.isArray(batch.events) || !Number.isInteger(batch.next_cursor) || batch.next_cursor < cursor)
        throw Error('Invalid event page');
      for (const event of batch.events) {
        if (serverNow() >= session.deadline) break;
        if (!eligible(event, session, serverNow())) continue;
        stage='fresh_context';
        const context = await tool('get_chat_context', {chat_id:p.chat_id, after:event.id-1, limit:1});
        if (!context.preferences?.proactive_enabled || !context.preferences.chat_integration_enabled) {
          report.state='disabled'; break sessionLoop;
        }
        if (!context.receipt_id || context.events?.[0]?.id !== event.id || context.events.length !== 1 ||
            context.events[0].body_preferences?.feedback_level !== 'normal') continue;
        if (!Number.isFinite(context.expires_at) || serverNow() >= Math.min(session.deadline, context.expires_at)) continue;
        const current = (await tool('get_interaction_status')).active_session;
        if (!current || current.id !== session.id || current.chat_id !== p.chat_id) break;
        // Persist intent BEFORE sending: a crash/ambiguous timeout blocks automatic replay.
        state.pending = {phase:'sending', receipt_id:context.receipt_id, event_id:context.events[0].event_id};
        stage='delivery_state';
        await save(p, state);
        if (serverNow() >= Math.min(session.deadline,context.expires_at)) {
          state.pending=null; await save(p,state); continue;
        }
        stage='main_chat_send';
        // MAIN's native send waits for that chat's previous stream. Never infer
        // MAIN idleness from the unrelated floating runtime or start a new chat.
        const reply = await Tools.Chat.sendMessage(prompt(context), p.chat_id, undefined, undefined,
          {runtime:'main', persist_turn:true, notify_reply:true, hide_user_message:true,
            // The session deadline stops NEW sends. An already submitted reply
            // may finish afterwards, while retaining the context-age bound on
            // native queue waiting (this host API shares one timeout for both).
            timeout_ms:Math.max(1,Math.min(60000,Math.floor((context.expires_at-serverNow())*1000)))});
        if (reply.chatId !== p.chat_id || typeof reply.aiResponse !== 'string' || !reply.aiResponse.trim())
          throw Error('Send outcome uncertain: check original chat before retrying');
        state.pending.phase = 'completed';
        await save(p, state);
        report.replies++; report.model_response_returned=true;
        stage='context_acknowledgement';
        await settle(p, state, tool);
      }
      cursor = batch.next_cursor;
      if (!batch.events.length) await Tools.System.sleep(500);
    }
    if (report.state==='listening') report.state='ended';
  } catch (error) {
    const recovery=stage==='main_chat_send'?
      '。发送结果可能不完整，请先核对原聊天；不要删除状态文件或自动重试。可由用户选择 reconcile_delivery 的 delivered / not_sent / discard。':'';
    throw Error('AI Doll ['+stage+']: '+(error?.message || String(error))+recovery);
  } finally {
    if (tool && session?.id) {
      try {
        await tool('end_interaction', {chat_id:p.chat_id, session_id:session.id});
        if (state) { state.session_id=null; await save(p,state); }
      } catch (_) { report.cleanup_pending=true; }
    }
    running=false;
  }
  complete(report);
}

async function stop_interaction(p) {
  configuration(p);
  const state=await load(p), tool=await connect(p.mcp_url);
  if (state.session_id) await tool('end_interaction',{chat_id:p.chat_id,session_id:state.session_id});
  state.session_id=null; await save(p,state);
  complete({stopped:true, uncertain_delivery:state.pending?.phase==='sending'});
}

async function reconcile_delivery(p) {
  configuration(p);
  if (!['delivered','not_sent','discard'].includes(p.decision)) throw Error('User must choose delivered, not_sent or discard after checking the chat');
  const state=await load(p),tool=await connect(p.mcp_url);
  if (state.pending) {
    if (p.decision!=='not_sent') {
      state.pending.phase='completed'; state.pending.user_decision=p.decision;
      await save(p,state); await settle(p,state,tool);
    }
    else { state.pending=null; await save(p,state); }
  }
  complete({reconciled:true, decision:p.decision, display_verified:false,
    model_reply_verified:false, acknowledgement_means:'client_reported_handled_not_display_verified'});
}

exports.list_existing_chats=list_existing_chats;
exports.listen_interaction=listen_interaction;
exports.stop_interaction=stop_interaction;
exports.reconcile_delivery=reconcile_delivery;
