'use strict';
const el=id=>document.getElementById(id);
async function api(path,data){
  const response=await fetch(path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'操作失败');return result;
}
function notice(text,error=false){el('notice').textContent=text;el('notice').className=error?'danger':''}
function connected(on){el('connectPanel').hidden=on;el('workspace').hidden=!on}
async function devices(){
  const result=await api('/api/devices');connected(true);el('devices').replaceChildren();
  for(const device of result.devices){
    const row=document.createElement('div');row.className='device';
    const info=document.createElement('div'),name=document.createElement('strong'),state=document.createElement('div'),link=document.createElement('a');
    name.textContent=device.label;state.className='muted';state.textContent=(device.online?'在线':'等待设备上传')+(device.hardware_id?' · '+device.hardware_id:'');
    link.href='/d/'+encodeURIComponent(device.id)+'/companion';link.textContent='通道、模拟、历史与人设 →';
    info.append(name,state,link);row.append(info);
    const latest=document.createElement('span');latest.className='muted';latest.textContent=device.last_sync?'最后同步 '+new Date(device.last_sync*1000).toLocaleString():'尚未同步';row.append(latest);el('devices').append(row);
  }
  if(!result.devices.length)el('devices').textContent='还没有设备，请先生成连接配置。';
}
el('connectForm').addEventListener('submit',async event=>{event.preventDefault();try{await api('/api/connect',{token:el('adminToken').value});el('adminToken').value='';await devices();notice('已连接服务器管理界面。')}catch(error){notice(error.message,true)}});
el('pairForm').addEventListener('submit',async event=>{event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;try{const result=await api('/api/pairings',{label:el('deviceLabel').value});el('pairConfig').textContent=JSON.stringify({server_url:result.server_url||location.origin,device_token:result.device_token},null,2);el('pairResult').hidden=false;await devices();notice('连接配置已生成，请在设备设置页保存。')}catch(error){notice(error.message,true)}finally{button.disabled=false}});
el('copyPair').onclick=async()=>{try{await navigator.clipboard.writeText(el('pairConfig').textContent);notice('连接配置已复制。')}catch{notice('请手动选中并复制连接配置。')}};
el('refreshDevices').onclick=()=>devices().catch(error=>notice(error.message,true));
el('disconnect').onclick=async()=>{try{await api('/api/disconnect',{});connected(false);el('pairResult').hidden=true;el('pairConfig').textContent='';notice('已断开。')}catch(error){notice(error.message,true)}};
devices().catch(()=>connected(false));
