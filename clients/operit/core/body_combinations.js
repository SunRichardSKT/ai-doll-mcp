// Same rule format as the desktop core. Replaying releases prevents sequential taps becoming a hug.
function validate(rules){
 if(!Array.isArray(rules)||rules.length>16)throw Error('最多设置16个部位组合。');
 const result=[];
 for(const r of rules){
  if(!r||typeof r!=='object'||Object.keys(r).some(k=>!['name','channels','window_ms'].includes(k)))throw Error('组合只支持 name、channels、window_ms。');
  const name=typeof r.name==='string'?r.name.trim():'',channels=r.channels,window=r.window_ms??1500;
  if(typeof r.name!=='string'||!name||[...r.name].length>40)throw Error('组合名称应为1～40字。');
  if(!Array.isArray(channels)||channels.length<2||channels.length>8||channels.some(c=>!Number.isInteger(c)||c<0||c>15)||new Set(channels).size!==channels.length)throw Error('每个组合选择2～8个不同通道。');
  if(!Number.isInteger(window)||window<100||window>10000)throw Error('组合按下间隔应为100～10000毫秒。');
  const item={name,channels:[...channels].sort((a,b)=>a-b),window_ms:window};
  if(result.some(x=>x.name===name||JSON.stringify(x.channels)===JSON.stringify(item.channels)))throw Error('组合名称与通道组合不能重复。');
  result.push(item);
 }
 return result;
}
function recognize(events,rules,selected){
 const active=new Map(),matches=[],selectedIds=selected?new Set(selected.map(e=>e.event_id??e.id)):null;
 const rows=events.filter(e=>(e.sensor_type||'pressure')==='pressure'&&e.quality==='ok'&&['sensor','simulation'].includes(e.source)&&(e.direction||'input')==='input'&&(e.delivery_quality||'live')==='live'&&Number.isFinite(e.at)).slice().sort((a,b)=>a.at-b.at||(a.id||0)-(b.id||0));
 for(const e of rows){
  const scope=JSON.stringify([e.device_id??null,e.boot??null,e.source??null,e.session_id??null]);
  if(!active.has(scope))active.set(scope,new Map());const held=active.get(scope);
  if(e.phase==='end'){if(held.get(e.channel)?.touch_id===e.touch_id)held.delete(e.channel);continue;}
  if(e.phase!=='start')continue;
  for(const [c,old] of held){if(old.ended_at!=null&&old.ended_at<=e.at)held.delete(c);}
  held.set(e.channel,e);
  for(const r of rules){
   if(!r.channels.includes(e.channel)||!r.channels.every(c=>held.has(c)))continue;
   const members=r.channels.map(c=>held.get(c));
   if((e.at-Math.min(...members.map(x=>x.at)))*1000>r.window_ms)continue;
   if(selectedIds&&!selectedIds.has(e.event_id??e.id))continue;
   matches.push({name:r.name,channels:r.channels,event_ids:members.map(x=>x.event_id??x.id),trigger_event_id:e.event_id??e.id,at:e.at,source:e.source,interpretation:'user_defined_combination'});
  }
 }
 return matches;
}
exports.validate=validate;exports.recognize=recognize;
