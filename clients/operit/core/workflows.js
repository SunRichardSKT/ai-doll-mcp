const store=require('./settings.js');
function description(cfg,kind) { return 'AI Doll managed:'+cfg.installation+':'+kind; }
function nodes(kind, jobId, scheduledAt) {
  return [
    {id:'ai_doll_trigger',type:'trigger',name:'AI Doll 后台启动',position:{x:60,y:80},
      triggerType:scheduledAt?'schedule':'manual',triggerConfig:scheduledAt?
        {schedule_type:'specific_time',specific_time:scheduledAt,repeat:'false',enabled:'true'}:{}},
    {id:'ai_doll_execute',type:'execute',name:kind==='probe'?'原聊天连接自检':'身体互动',
      position:{x:360,y:80},actionType:'ai_doll_companion:run_task',actionConfig:{job_id:jobId||''}}
  ];
}
const connections=[{sourceNodeId:'ai_doll_trigger',targetNodeId:'ai_doll_execute',condition:'on_success'}];
function owned(cfg,kind,value) {
  if (!value || value.id!==cfg.workflows[kind] || value.description!==description(cfg,kind))
    throw Error('已保存的工作流归属不符，未修改其他工作流。');
}
function nodeType(node) {
  // Kotlin's default serializer omits type="trigger"/"execute"; the sealed
  // class discriminator remains. Never infer an action from its display name.
  const classes={TriggerNode:'trigger',ExecuteNode:'execute'};
  const inferred=classes[String(node.__type||'').split('.').pop()];
  if (node.type && inferred && node.type!==inferred) return '';
  return node.type || inferred || '';
}
function staticValue(value) {
  if (typeof value==='string') return value;
  if (value && typeof value.value==='string' && !value.nodeId &&
      (!value.__type || String(value.__type).split('.').pop()==='StaticValue')) return value.value;
  return null;
}
function normalize(value) {
  return {...value,nodes:Array.isArray(value.nodes)?value.nodes.map(item=>{
    const n=item||{};
    return {...n,type:nodeType(n),
      ...(nodeType(n)==='trigger'?{triggerType:n.triggerType||'manual',triggerConfig:n.triggerConfig||{}}:{})};
  }):null};
}
function problem(value) {
  if (!Array.isArray(value.nodes) || !Array.isArray(value.connections)) return '缺少节点或连线';
  const trigger=value.nodes.find(n=>n.type==='trigger'),exec=value.nodes.find(n=>n.type==='execute');
  if (value.nodes.length!==2 || !trigger || !exec || !trigger.id || !exec.id || trigger.id===exec.id)
    return '需要一个触发节点和一个执行节点';
  if (exec.actionType!=='ai_doll_companion:run_task' || exec.jsCode ||
      staticValue(exec.actionConfig?.job_id)===null) return '执行工具或任务参数不匹配';
  if (!['manual','schedule'].includes(trigger.triggerType)) return '触发方式不匹配';
  if (value.connections.length!==1 || !value.connections.some(c=>c&&c.sourceNodeId===trigger.id&&
      c.targetNodeId===exec.id&&c.condition==='on_success')) return '触发与执行节点未正确连接';
  return '';
}
function verify(cfg,kind,raw) {
  owned(cfg,kind,raw);
  const value=normalize(raw),reason=problem(value);
  if (reason) throw Error('AI Doll 工作流核对失败：'+reason+'。请停止任务后点击一键检查。');
  return value;
}
async function ensure(cfg,kind) {
  if (cfg.workflows[kind]) {
    const raw=await Tools.Workflow.get(cfg.workflows[kind]);
    owned(cfg,kind,raw);
    if (!problem(normalize(raw))) return verify(cfg,kind,raw);
    // Repair only the persisted, installation-owned ID, while idle. Keep chat,
    // connection, receipts and workflow identity; do not create duplicates.
    await store.noRunningJob();
    await Tools.Workflow.update(raw.id,{nodes:nodes(kind),connections,enabled:false});
    const repaired=verify(cfg,kind,await Tools.Workflow.get(raw.id));
    if (repaired.enabled!==false) throw Error('工作流修复后未确认停用，未安排后台任务。');
    return repaired;
  }
  const created=await Tools.Workflow.create('AI Doll · '+(kind==='probe'?'连接自检':'身体互动'),
    description(cfg,kind),nodes(kind),connections,false);
  if (!created.id) throw Error('宿主没有返回工作流编号。');
  // Save ownership before rereading: failed readback must not create duplicates.
  cfg.workflows[kind]=created.id;
  await store.write('settings.json',cfg);
  return verify(cfg,kind,await Tools.Workflow.get(created.id));
}
function localTime(epoch) {
  const d=new Date(epoch), pad=n=>String(n).padStart(2,'0');
  return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())+' '+
    pad(d.getHours())+':'+pad(d.getMinutes())+':'+pad(d.getSeconds());
}
async function schedule(cfg,kind,job) {
  const flow=await ensure(cfg,kind);
  // trigger() waits for the whole task. Schedule one bounded native WorkManager
  // job instead, so the UI control returns without recursively waiting on chat.
  const at=localTime(Date.now()+(job.delay_ms||10000));
  await Tools.Workflow.update(flow.id,{nodes:nodes(kind,job.id,at),connections,enabled:true});
  const confirmed=verify(cfg,kind,await Tools.Workflow.get(flow.id));
  if (confirmed.enabled!==true || !confirmed.nodes.some(n=>n.type==='trigger'&&n.triggerType==='schedule'&&
      n.triggerConfig?.specific_time===at&&n.triggerConfig?.repeat==='false'&&n.triggerConfig?.enabled==='true') ||
      !confirmed.nodes.some(n=>n.type==='execute'&&staticValue(n.actionConfig?.job_id)===job.id))
    throw Error('后台任务安排未确认。');
  return {workflow_id:flow.id,scheduled_at:at,state:'scheduled',listening:false};
}
async function watchdog(cfg) {
  const flow=await ensure(cfg,'watchdog');
  const list=nodes('watchdog','watchdog:'+cfg.binding);
  list[0].triggerType='schedule';
  list[0].triggerConfig={schedule_type:'interval',interval_ms:'900000',repeat:'true',enabled:'true'};
  await Tools.Workflow.update(flow.id,{nodes:list,connections,enabled:true});
  const saved=verify(cfg,'watchdog',await Tools.Workflow.get(flow.id));
  if(saved.enabled!==true||saved.nodes[0].triggerConfig?.repeat!=='true')throw Error('常开恢复任务未确认。');
}
async function disable(cfg) {
  const errors=[];
  for (const kind of Object.keys(cfg.workflows)) {
    try{
      const flow=await Tools.Workflow.get(cfg.workflows[kind]);
      owned(cfg,kind,flow);
      await Tools.Workflow.update(flow.id,{enabled:false});
    }catch(error){errors.push(kind+': '+String(error.message||error));}
  }
  if(errors.length)throw Error('部分后台任务未确认停止：'+errors.join('；'));
}
exports.ensure=ensure; exports.schedule=schedule; exports.disable=disable;
exports.watchdog=watchdog;
