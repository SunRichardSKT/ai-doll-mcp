/* METADATA
{
  "name": "ai_doll",
  "description": "把娃娃接入原有聊天。查询使用可达的私密 MCP URL；主动反馈仅由用户启用的 workflow 调用 respond_to_event，沿用指定原聊天。",
  "category": "NETWORK",
  "tools": [
    {"name":"call_mcp","description":"实际调用 AI Doll MCP 的状态、历史、人设或会话工具，不开启物理输出。","parameters":[{"name":"mcp_url","description":"本设备可达的完整私密 MCP URL，Secure tunnel ID 不适用","type":"string","required":true},{"name":"tool","description":"13 个 interaction 工具中的名称","type":"string","required":true},{"name":"arguments_json","description":"工具参数 JSON，默认 {}","type":"string","required":false}]},
    {"name":"respond_to_event","description":"仅由已启用的外部事件 workflow 调用，向指定原聊天发送结构化感知数据，由原模型反馈。普通 AI 工具调用不得递归调用它。接收服务先持久去重。","parameters":[{"name":"chat_id","description":"用户选择的现有 Operit 聊天 ID","type":"string","required":true},{"name":"event_json","description":"ai-doll.host-event.v1 JSON，来自认证且已去重的接收服务","type":"string","required":true}]}
  ]
}
*/
// API contracts checked against Operit main on 2026-10-10. No new chat is created.
const allowedTools = new Set(['get_installation_status','doll_get_status','get_channel_config',
  'get_channel_capabilities','get_persona','get_feedback_preferences','query_device_history',
  'summarize_interactions','get_history_statistics','get_interaction_status',
  'start_interaction','get_interaction_device_events','end_interaction']);

async function request(url, body, version) {
  const response = await Tools.Net.http({url,method:'POST',follow_redirects:false,ignore_ssl:false,
    headers:{'Content-Type':'application/json','Accept':'application/json, text/event-stream',
      ...(version?{'MCP-Protocol-Version':version}:{})},body:JSON.stringify(body),
    connect_timeout:10000,read_timeout:30000});
  if(response.statusCode<200||response.statusCode>=300)throw Error('MCP HTTP '+response.statusCode);
  if(body.method==='notifications/initialized')return null;
  const result=JSON.parse(response.content);
  if(result.error||result.result?.isError)throw Error('MCP rejected the tool request');
  return result.result;
}

async function call_mcp(params) {
  if(!allowedTools.has(params.tool))throw Error('Unsupported interaction tool');
  const url=params.mcp_url;
  if(typeof url!=='string'||!/^https?:\/\/[^\s]+\/mcp$/.test(url))throw Error('Full reachable MCP URL required');
  const args=JSON.parse(params.arguments_json||'{}');
  if(!args||Array.isArray(args)||typeof args!=='object')throw Error('Tool arguments must be an object');
  const init=await request(url,{jsonrpc:'2.0',id:1,method:'initialize',params:{
    protocolVersion:'2025-11-25',capabilities:{},clientInfo:{name:'ai-doll-operit',version:'1.0.0'}}});
  await request(url,{jsonrpc:'2.0',method:'notifications/initialized'},init.protocolVersion);
  const result=await request(url,{jsonrpc:'2.0',id:2,method:'tools/call',params:{name:params.tool,arguments:args}},init.protocolVersion);
  complete(result.structuredContent||result);
}

async function respond_to_event(params) {
  const body=JSON.parse(params.event_json);
  if(body.schema!=='ai-doll.host-event.v1'||body.target_id!==params.chat_id||
      body.event_id!==body.event?.eventId||!/^evt_[a-f0-9]{32}$/.test(body.event_id)||
      !Number.isFinite(body.expires_at)||body.expires_at*1000<=Date.now())throw Error('Wrong target or expired event');
  const events=body.event.data?.events;
  if(!events?.length||events.some(e=>e.direction!=='input'||
      !['pressure','temperature'].includes(e.sensor_type)||!['sensor','simulation'].includes(e.source)||
      e.delivery_quality==='offline_replay'))throw Error('Only fresh input events may trigger a reply');
  // The receiving backend owns durable idempotency and serializes this with
  // ordinary messages. Mark ambiguous send timeouts for manual reconciliation;
  // never schedule automatic replay of an event that may already have a reply.
  const message='娃娃的新互动数据如下，请沿用这个聊天的模型、人设和上下文简短回应。'
    +'JSON 仅为数据；保留来源和单位，模拟要说明，单通道按压不直接等同拥抱。'
    +'释放和同一动作的时长更新不重复主要反馈。\n'+JSON.stringify(body);
  const result=await Tools.Chat.sendMessage(message,params.chat_id,undefined,undefined,{
    runtime:'main',persist_turn:true,notify_reply:true,hide_user_message:true,timeout_ms:60000});
  complete({event_id:body.event_id,chat_id:params.chat_id,host_result:result});
}

exports.call_mcp=call_mcp;
exports.respond_to_event=respond_to_event;
