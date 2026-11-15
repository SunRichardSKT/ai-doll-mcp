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
      label.textContent='设备专用 MCP 连接地址（含私密访问路径）：';
      address.value=device.mcp_url;address.readOnly=true;address.setAttribute('aria-label','MCP 连接地址');
      copy.textContent='复制 MCP 地址';copy.className='secondary';
      copy.onclick=async()=>{try{await navigator.clipboard.writeText(address.value);notice('MCP 地址已复制。')}catch{address.select();notice('请复制选中的 MCP 地址。')}};
      info.append(label,address,copy);
      const clientLabel=document.createElement('label'),client=document.createElement('select'),guide=document.createElement('p');
      clientLabel.textContent='选择 AI 客户端';client.setAttribute('aria-label','选择 AI 客户端');guide.className='muted';
      for(const [value,title] of [['','请选择'],['chatgpt','ChatGPT'],['claude','Claude 网页／手机'],['deepseek','DeepSeek DSH'],['gemini_app','Gemini 网页／手机'],['gemini','Gemini CLI'],['operit','Operit'],['other','其他 MCP 客户端']])client.add(new Option(title,value));
      clientLabel.append(client);info.append(clientLabel,guide);
        const clientConfig=document.createElement('pre'),copyClient=document.createElement('button');
        copyClient.textContent='复制所选客户端配置';clientConfig.style.whiteSpace='pre-wrap';clientConfig.style.overflowWrap='anywhere';
        info.append(clientConfig,copyClient);
        copyClient.onclick=()=>navigator.clipboard.writeText(clientConfig.textContent).then(()=>notice('配置已复制')).catch(e=>notice(e.message,true));
      const operit=document.createElement('a');operit.href='/d/'+encodeURIComponent(device.id)+'/operit-connection.json';
      operit.textContent='下载 Operit 连接文件';operit.download='AI_Doll_Operit_Connection.json';
      const note=document.createElement('p');note.className='muted';
      note.textContent='安卓手机：先安装本页工具包，再导入此设备连接。设备直接上传服务器，电脑无需运行。';
      const phone=document.createElement('div');phone.append(note,operit);phone.hidden=true;info.append(phone);
      const showPairing=document.createElement('button'),pairing=document.createElement('div');
      showPairing.textContent='连接 Operit：文件、连接码或二维码';showPairing.className='secondary';
      showPairing.onclick=async()=>{showPairing.disabled=true;try{
        const connection=await api('/d/'+encodeURIComponent(device.id)+'/operit-connection.json');
        AIDollPairing.render(pairing,connection);
      }catch(error){notice(error.message,true)}finally{showPairing.disabled=false}};
      phone.append(showPairing,pairing);
      client.onchange=()=>{
        phone.hidden=client.value!=='operit';
        const url=new URL(device.mcp_url),cloud=['chatgpt','claude','gemini_app'].includes(client.value);
        clientConfig.hidden=copyClient.hidden=!['deepseek','gemini'].includes(client.value);
          clientConfig.textContent=JSON.stringify(client.value==='deepseek'?[{id:'ai-doll-mcp',name:'@deepseek-ai/dsh-mcp-client',config:{serverName:'ai_doll',transport:'streamable-http',url:url.href}}]:{mcpServers:{ai_doll:{httpUrl:url.href}}},null,2);
          guide.textContent=client.value==='chatgpt'?'在 ChatGPT Plugins 添加自定义 MCP，选择 Server URL，粘贴上方完整地址，选择无需身份验证；创建后安装并在聊天中启用。':
          client.value==='claude'?'在 Claude 连接器设置中添加自定义远程连接，粘贴上方完整地址，选择无需登录，在聊天中启用。此连接由 Claude 云端发起。':
          client.value==='deepseek'?'DeepSeek DSH：在当前 profile 的 MCP 设置添加 ai_doll，transport 选 streamable-http，url 填上方完整私密地址。亦可将原生 dsh-mcp-client 条目合并到 cordis.patch.yml。':
            client.value==='gemini_app'?'在 Gemini 网页 Settings → Connected Apps → Custom apps 添加上方公网 HTTPS MCP 地址，连接后用 @ 选择应用，手机 App 也可使用。当前需美国地区、18岁以上个人账号、英文界面和开启 Keep Activity。没有入口可用 Gemini CLI；开发者可按官方 Gemini Apps Developer Mode 指南添加。':
            client.value==='gemini'?'Gemini CLI：在 .gemini/settings.json 的 mcpServers 添加 ai_doll，httpUrl 填上方完整地址；重开 CLI，用 /mcp 检查连接。':
          client.value==='operit'?'下载工具包和此设备的连接文件，在手机导入，再选择聊天；自动同步与主动回复分别控制。':
          client.value==='other'?'支持远程 MCP 的客户端使用完整地址；Claude 桌面版本机连接可从 Windows 管理中心生成配置。':'选择应用后显示接入步骤。';
        if(cloud&&(url.protocol!=='https:'||client.value==='claude'&&url.port&&url.port!=='443'))guide.textContent+=' 当前地址不满足此云端连接要求，请先配置公网 HTTPS'+(client.value==='claude'?' 443':'')+'地址；局域网地址供本地客户端使用。';
        if(cloud)guide.textContent+=' 添加后实际调用 get_installation_status 和 doll_get_status，核对设备。';
      };
      client.onchange();
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
