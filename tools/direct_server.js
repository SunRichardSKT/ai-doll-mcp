'use strict';
const el=id=>document.getElementById(id);
async function api(path,data){
  const response=await fetch(path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'操作失败');return result;
}
function notice(text,error=false){el('notice').textContent=text;el('notice').className=error?'danger':''}
function connected(on){el('connectPanel').hidden=on;el('workspace').hidden=!on}
async function serverSettings(){
  const info=await api('/api/server');el('serverURL').value=info.server_url||location.origin;
  el('quickSetup').hidden=!info.local_setup;
  el('serverAddress').textContent=info.server_url||location.origin;
}
async function devices(){
  const result=await api('/api/devices');connected(true);el('devices').replaceChildren();
  await serverSettings();
  for(const device of result.devices){
    const row=document.createElement('div');row.className='device';
    const info=document.createElement('div'),name=document.createElement('strong'),state=document.createElement('div'),link=document.createElement('a');
    name.textContent=device.label;state.className='muted';state.textContent=(device.online?'在线':'等待设备上传')+(device.hardware_id?' · '+device.hardware_id:'');
    link.href='/d/'+encodeURIComponent(device.id)+'/companion';link.textContent='通道、模拟、历史与人设 →';
    info.append(name,state,link);row.append(info);
    if(device.mcp_url){
      const label=document.createElement('p'),address=document.createElement('input'),copy=document.createElement('button');
      label.textContent='MCP 连接地址（Streamable HTTP，无需账号）：';
      address.value=device.mcp_url;address.readOnly=true;address.setAttribute('aria-label','MCP 连接地址');
      copy.textContent='复制 MCP 地址';copy.className='secondary';
      copy.onclick=async()=>{try{await navigator.clipboard.writeText(address.value);notice('MCP 地址已复制。')}catch{address.select();notice('请复制选中的 MCP 地址。')}};
      info.append(label,address,copy);
      const operit=document.createElement('a');operit.href='/d/'+encodeURIComponent(device.id)+'/operit-connection.json';
      operit.textContent='下载 Operit 连接文件';operit.download='AI_Doll_Operit_Connection.json';
      const note=document.createElement('p');note.className='muted';
      note.textContent='安卓手机：先安装本页工具包，再导入此设备连接。设备直接上传服务器，电脑无需运行。';
      info.append(note,operit);
      const showPairing=document.createElement('button'),pairing=document.createElement('div');
      showPairing.textContent='连接 Operit：文件、连接码或二维码';showPairing.className='secondary';
      showPairing.onclick=async()=>{showPairing.disabled=true;try{
        const connection=await api('/d/'+encodeURIComponent(device.id)+'/operit-connection.json');
        AIDollPairing.render(pairing,connection);
      }catch(error){notice(error.message,true)}finally{showPairing.disabled=false}};
      info.append(showPairing,pairing);
    }
    const latest=document.createElement('span');latest.className='muted';latest.textContent=device.last_sync?'最后同步 '+new Date(device.last_sync*1000).toLocaleString():'尚未同步';row.append(latest);el('devices').append(row);
  }
  if(!result.devices.length)el('devices').textContent='还没有设备，请先生成连接配置。';
}
el('connectForm').addEventListener('submit',async event=>{event.preventDefault();try{await api('/api/connect',{token:el('adminToken').value});el('adminToken').value='';await devices();notice('已连接服务器管理界面。')}catch(error){notice(error.message,true)}});
el('pairForm').addEventListener('submit',async event=>{event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;try{const result=await api('/api/pairings',{label:el('deviceLabel').value});el('pairConfig').textContent=JSON.stringify({server_url:result.server_url||location.origin,device_token:result.device_token},null,2);el('pairResult').hidden=false;await devices();notice('连接配置已生成，请在设备设置页保存。')}catch(error){notice(error.message,true)}finally{button.disabled=false}});
el('copyPair').onclick=async()=>{try{await navigator.clipboard.writeText(el('pairConfig').textContent);notice('连接配置已复制。')}catch{notice('请手动选中并复制连接配置。')}};
el('refreshDevices').onclick=()=>devices().catch(error=>notice(error.message,true));
el('disconnect').onclick=async()=>{try{await api('/api/disconnect',{});connected(false);el('pairResult').hidden=true;el('pairConfig').textContent='';notice('已断开。')}catch(error){notice(error.message,true)}};
el('quickPairForm').addEventListener('submit',async event=>{
  event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;
  notice('正在读取设备并保存连接设置…');
  try{
    await api('/api/local-pair',{host:el('deviceIP').value,label:el('quickDeviceLabel').value,
      username:el('deviceUsername').value,password:el('devicePassword').value});
    el('devicePassword').value='';await devices();notice('设备已确认保存。收到首次上传后，下方会显示在线。');
  }catch(error){notice(error.message,true)}finally{button.disabled=false}
});
el('saveServerURL').onclick=async()=>{try{await api('/api/server/configure',{server_url:el('serverURL').value});await serverSettings();notice('地址已保存。已配对设备若需要切换地址，再点一次“连接设备”即可。')}catch(error){notice(error.message,true)}};
el('stopServer').onclick=async()=>{try{await api('/api/server/stop',{});notice('服务端已停止。下次双击 AI_Doll_Server.cmd 即可重新启动。')}catch(error){notice(error.message,true)}};
(async()=>{
  const fragment=new URLSearchParams(location.hash.slice(1)),token=fragment.get('connect');
  if(token){history.replaceState(null,'',location.pathname+location.search);try{await api('/api/connect',{token})}catch(error){notice(error.message,true)}}
  try{await devices()}catch{connected(false)}
})();
