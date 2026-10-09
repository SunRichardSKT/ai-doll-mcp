/* Archive controls use the existing authenticated local API, never device ACKs. */
(()=>{
 const el=id=>document.getElementById(id);
 const call=(name,arguments={})=>api('/companion/tool',{name,arguments});
 let preview=null,busy=false;
 const result=text=>{el('historyManagementResult').textContent=text;};
 function invalidate(){preview=null;el('deleteApproval').checked=false;el('confirmHistoryDelete').disabled=true;el('deletionPreview').textContent='先预览将删除的范围。';}
 function filters(){
  const f={time_scope:el('manageTimeScope').value};
  for(const [id,key] of [['manageFrom','start_date'],['manageTo','end_date'],['manageBody','body_part'],['manageType','sensor_type'],['manageSource','source']])
   if(el(id).value)f[key]=el(id).value;
  return f;
 }
 function countText(p){const c=p.counts;return `将删除 ${c.events} 条事件，其中 ${c.unknown_time_events} 条时间未知；涉及 ${c.pressure_gestures} 次压力记录。为删除完整按下/释放，额外包含 ${c.expanded_events} 条记录。相关会话的 ${c.related_deliveries} 条推送和 ${c.related_replies} 条回复也会删除。`;}
 async function run(action){if(busy)return;busy=true;for(const b of el('historyManagement').querySelectorAll('button'))b.disabled=true;
  try{await action();}catch(e){result(e.message);}finally{busy=false;for(const b of el('historyManagement').querySelectorAll('button'))b.disabled=false;el('confirmHistoryDelete').disabled=!preview||!el('deleteApproval').checked;}}
 function download(content,type,name){const url=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);}
 async function exportFile(format){
  const f=filters(),records=[];let after=0,max_id=null,count=0,csv='';
  do{const p=await call('export_history',{filters:f,format,after,limit:500,max_id});
   if(max_id===null)max_id=p.max_id;count+=p.count;
   if(format==='json')records.push(...p.records);else csv+=csv?p.content.slice(p.content.indexOf('\n')+1):p.content;
   if(!p.has_more)break;if(p.next_cursor<=after)throw Error('导出游标未前进，请重试');after=p.next_cursor;
   result(`正在导出，已读取 ${count} 条…`);
  }while(true);
  const stamp=new Date().toISOString().slice(0,10);
  if(format==='json')download(JSON.stringify({schema_version:1,timezone:'Asia/Shanghai',filters:f,max_id,records},null,2),'application/json',`ai-doll-history-${stamp}.json`);
  else download('\ufeff'+csv,'text/csv;charset=utf-8',`ai-doll-history-${stamp}.csv`);
  result(`已导出 ${count} 条记录到下载文件。文件包含互动数据，请自行决定分享范围。`);
 }
 async function statistics(){const s=await call('get_history_statistics',{filters:filters()});
  el('historyStatistics').textContent=`${s.events} 条事件 · ${s.pressure_starts} 次压力开始 · ${s.completed} 次已完成压力记录 · 已完成总时长 ${(s.duration_ms/1000).toFixed(1)} 秒 · ${s.unknown_time_events} 条时间未知`;
  const groups=el('historyGroups');groups.replaceChildren();
  const types={pressure:'压力',temperature:'温度',vibration:'震动命令'},sources={simulation:'模拟',sensor:'真实输入',actuator:'真实输出命令'};
  for(const [title,items,names] of [['类型',s.by_type,types],['部位',s.by_body_part,{}],['来源',s.by_source,sources]]){
   const line=document.createElement('p');line.textContent=title+'：'+items.map(x=>`${names[x.label]??x.label??'未标记'} ${x.events} 条`).join('、');groups.append(line);
  }
  el('historyDays').replaceChildren();for(const day of s.daily){const li=document.createElement('li');li.textContent=`${day.date}：${day.events} 条`;el('historyDays').append(li);}
 }
 async function retention(){const p=await call('get_history_retention');el('retentionEnabled').checked=p.enabled;el('retentionDays').value=p.days;el('retentionUnknown').checked=p.include_unknown;
  el('retentionStatus').textContent=p.maintenance_error||(!p.enabled?'自动删除已关闭。':`自动删除已启用：保留 ${p.days} 天。`)+(p.last_run?` 上次清理删除 ${p.last_run.counts.events} 条。`:'');}
 el('exportHistoryJson').onclick=()=>run(()=>exportFile('json'));el('exportHistoryCsv').onclick=()=>run(()=>exportFile('csv'));
 el('queryHistoryStats').onclick=()=>run(statistics);
 el('previewHistoryDelete').onclick=()=>run(async()=>{
  invalidate();const f=filters();if(!f.start_date&&!f.end_date&&!f.body_part&&!f.sensor_type&&!f.source&&!el('manageAllRecords').checked)throw Error('没有筛选条件时，请明确勾选“允许全部日期范围”。');
  preview=await call('preview_history_deletion',{filters:f,all_records:el('manageAllRecords').checked});el('deletionPreview').textContent=countText(preview)+' 预览两分钟内有效，新增相关记录后需重新预览。';
 });
 el('deleteApproval').onchange=()=>{el('confirmHistoryDelete').disabled=!preview||!el('deleteApproval').checked;};
 el('confirmHistoryDelete').onclick=()=>run(async()=>{
  if(!preview||!el('deleteApproval').checked)throw Error('请先预览并确认范围');
  const p=await call('delete_history',{preview_token:preview.preview_token,confirmed:true});invalidate();result(`已删除 ${p.counts.events} 条事件。设置和防止补传复活的最少标识保留。`);await statistics();el('query').click();
 });
 el('cancelHistoryDelete').onclick=invalidate;
 for(const id of ['manageFrom','manageTo','manageBody','manageType','manageSource','manageAllRecords'])el(id).addEventListener('change',invalidate);
 el('manageTimeScope').onchange=()=>{const unknown=el('manageTimeScope').value==='unknown';if(unknown){el('manageFrom').value='';el('manageTo').value='';}el('manageFrom').disabled=unknown;el('manageTo').disabled=unknown;invalidate();};
 el('previewRetention').onclick=()=>run(async()=>{const p=await call('preview_history_retention',{days:Number(el('retentionDays').value),include_unknown:el('retentionUnknown').checked});el('retentionPreview').textContent=countText(p);});
 el('saveRetention').onclick=()=>run(async()=>{
  const enabled=el('retentionEnabled').checked,days=Number(el('retentionDays').value),include_unknown=el('retentionUnknown').checked;
  if(enabled){const p=await call('preview_history_retention',{days,include_unknown});el('retentionPreview').textContent=countText(p);
   if(!window.confirm(`启用自动删除并保留 ${days} 天？\n${countText(p)}\n启用后下一轮采集就可能清理，此后每小时检查；删除不能撤销。`))return;
  }
  await call('set_history_retention',{enabled,days,include_unknown,confirmed:enabled});await retention();result('保留设置已保存。');
 });
 const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 el('manageFrom').value=today;el('manageTo').value=today;
 retention().catch(e=>result(e.message));
})();
