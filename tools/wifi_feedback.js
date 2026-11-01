// Shared by the lightweight setup page and full device settings; no external assets.
function createWifiFeedback(api,onStatus){
 const el=id=>document.getElementById(id),scan=el('scan'),join=el('join'),hint=el('scanHint'),result=el('joinResult'),check=el('checkWifi');
 let scanning=false,saving=false,started=null,target='',last=null,scanStarted=0,offline=false;
 function message(node,text,tone='info'){node.textContent=text;node.dataset.tone=tone;node.setAttribute('role',tone==='error'?'alert':'status');}
 function matches(s){return !!s.wifi_connected&&(!target||s.ssid===target);}
 function render(){
  const elapsed=started===null?0:Math.max(0,Math.floor((Date.now()-started)/1000)),waiting=started!==null&&!matches(last||{})&&elapsed<30;
  scan.disabled=scanning||saving||waiting;join.disabled=scanning||saving||waiting;
  scan.textContent=scanning?'正在查找附近网络…':'查找附近的Wi-Fi';
  join.textContent=saving?'正在保存网络…':waiting?'正在连接 · '+elapsed+'秒':started!==null&&!matches(last||{})?'修改后重新连接':'保存并连接';
  scan.setAttribute('aria-busy',String(scanning));join.setAttribute('aria-busy',String(saving||waiting));
  if(scanning)message(hint,'正在查找2.4 GHz网络 · 已等待'+Math.floor((Date.now()-scanStarted)/1000)+'秒。请保持连接娃娃热点，通常需要几秒。');
  if(offline){message(result,'暂时无法读取设备状态，不能据此确认联网成功。若已切回家庭Wi-Fi，请打开保存的设备入口；否则重新连接娃娃热点后检查。','warning');check.hidden=false;return;}
  if(saving)return;
  if(started!==null){
   if(matches(last||{})){message(result,'已连接 '+last.ssid+'。家庭IP：'+last.ip+'。先保存设备入口，再到手机系统设置切回家庭Wi-Fi。','success');check.hidden=true;}
   else if(elapsed>=30){message(result,'等待较久，设备仍会自动重试。请核对Wi-Fi名称、密码及2.4 GHz网络，靠近路由器后可修改并重连。','warning');check.hidden=false;}
   else message(result,(last?.wifi_associated&&last?.ssid===target?'已连上路由器，正在获取家庭IP。':'设备正在尝试连接 '+target+'。')+' 已等待'+elapsed+'秒，请先留在当前页面，不要重复保存。');
  }
 }
 async function read(){try{const s=await api('/api/status');onStatus(s);}catch(_){disconnected();}}
 function disconnected(){offline=true;if(started!==null){message(result,'暂时无法读取设备状态，不能据此确认联网成功。若已切回家庭Wi-Fi，请打开保存的设备入口；否则重新连接娃娃热点后检查。','warning');check.hidden=false;}}
 scan.onclick=async()=>{
  if(scan.disabled)return;scanning=true;scanStarted=Date.now();render();
  try{let r=await api('/api/scan',{start:true});for(let i=0;r.scanning&&i<35;i++){await new Promise(resolve=>setTimeout(resolve,800));r=await api('/api/scan',{start:false});}
   if(r.scanning)throw Error('查找超时。可以重试，或手动填写2.4 GHz Wi-Fi名称。');
   const networks=el('networks');networks.replaceChildren(new Option('选择Wi-Fi，或手动输入',''));
   for(const n of r.networks)networks.add(new Option(n.ssid+(n.secure===false?' · 无密码':''),n.ssid));
   message(hint,r.networks.length?'找到 '+r.networks.length+' 个网络。请选择家庭Wi-Fi，再填写密码；未找到的网络也可手动输入。':'没有找到网络。请靠近路由器重试；隐藏网络可手动输入名称，仅支持2.4 GHz。',r.networks.length?'success':'warning');
  }catch(e){message(hint,e.name==='AbortError'?'设备暂未响应，请确认仍连接娃娃热点后重新查找，也可手动输入名称。':e.message,'error');}
  finally{scanning=false;render();}
 };
 async function submit(e){
  e?.preventDefault();if(join.disabled)return;
  const name=el('ssid').value,password=el('password').value,bytes=s=>new TextEncoder().encode(s).length;
  if(!name||bytes(name)>32){message(result,'请填写1～32字节的Wi-Fi名称。','error');el('ssid').setAttribute('aria-invalid','true');el('ssid').focus();return;}
  if(password&&(bytes(password)<8||bytes(password)>63)){message(result,'Wi-Fi密码至少8字节，最多63字节；开放网络请留空。','error');el('password').setAttribute('aria-invalid','true');el('password').focus();return;}
  el('ssid').removeAttribute('aria-invalid');el('password').removeAttribute('aria-invalid');document.activeElement?.blur();saving=true;offline=false;target=name;started=null;render();message(result,'正在把网络信息保存到娃娃，请稍候…');
  try{await api('/api/wifi',{ssid:name,password});el('password').value='';started=Date.now();last=null;message(result,'网络信息已保存，正在尝试联网；这还不代表连接成功。');}
  catch(e){message(result,'保存结果尚未确认。请检查当前网络，再点击“检查连接状态”，不要连续重复提交。','warning');check.hidden=false;}
  finally{saving=false;render();}if(started!==null)await read();
 }
 const form=el('wifiForm');if(form)form.onsubmit=submit;else join.onclick=submit;
 check.onclick=async()=>{check.disabled=true;try{await read();}finally{check.disabled=false;}};
 const timer=setInterval(()=>{if(!document.hidden)render();},1000);window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
 for(const input of [el('ssid'),el('password')])input.addEventListener('focus',()=>setTimeout(()=>{if(document.activeElement===input)input.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});},250));
 return {observe(s){offline=false;last=s;if(target&&matches(s)&&started===null&&!saving)started=Date.now();render();},get connecting(){return started!==null&&!matches(last||{});},disconnected,matches};
}
