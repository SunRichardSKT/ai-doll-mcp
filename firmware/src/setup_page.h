#pragma once
static const char SETUP_PAGE[] PROGMEM=R"HTML(<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="referrer" content="no-referrer"><title>给娃娃联网</title><style>
:root{color-scheme:light dark}[hidden]{display:none!important}body{font:16px system-ui;margin:0 auto;padding:22px;max-width:520px;background:#f3f1e9;color:#263e33}section{background:#fff;border-radius:18px;padding:20px;margin:16px 0}h1{font-size:26px}h2{font-size:19px}input,select,button,a.action{font:inherit;box-sizing:border-box;width:100%;padding:12px;margin:6px 0;border:1px solid #b7c8bd;border-radius:10px}input,select{background:#fff;color:#263e33}button,a.action{background:#2b6249;color:#fff}button:disabled{opacity:.5}a.action{display:block;text-align:center;text-decoration:none}a{color:#2b6249}small{display:block;color:#52675c;line-height:1.6}#error{color:#a1372a}p{line-height:1.65}#entry{font-size:14px}input[type=checkbox]{width:auto}label:has(input[type=checkbox]){display:flex;align-items:center;min-height:48px;gap:8px}#advanced,#openIP{display:inline-block;min-height:48px;box-sizing:border-box;padding:12px 0}@media(prefers-color-scheme:dark){body{background:#131b17;color:#edf3ee}section{background:#202c25}input,select{background:#142019;color:#edf3ee;border-color:#65776b}small{color:#becfc2}a{color:#a5d5b6}#error{color:#ffb7ae}}
body{box-sizing:border-box;padding-top:max(22px,env(safe-area-inset-top));padding-bottom:max(24px,env(safe-area-inset-bottom));padding-left:max(16px,env(safe-area-inset-left));padding-right:max(16px,env(safe-area-inset-right))}button,input:not([type=checkbox]),select,a.action{min-height:48px}button{touch-action:manipulation}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #839f8d;outline-offset:2px}#scanHint,#joinResult{line-height:1.65;overflow-wrap:anywhere}#joinResult:not(:empty){padding:14px;border:1px solid #b7c8bd;border-radius:12px;background:#e8f0e9}#joinResult[data-tone=warning],#scanHint[data-tone=warning]{color:#705315}#joinResult[data-tone=error],#scanHint[data-tone=error]{color:#a1372a}#joinResult[data-tone=success],#scanHint[data-tone=success]{color:#245d3e}button.secondary{background:transparent;color:#2b6249}#wifiForm:focus-within{padding-bottom:min(30vh,300px)}@media(prefers-color-scheme:dark){body{background:#131b17;color:#edf3ee}section{background:#202c25}input,select{background:#142019;color:#edf3ee;border-color:#65776b}small{color:#becfc2}a,button.secondary{color:#a5d5b6}#joinResult:not(:empty){background:#25382b;border-color:#65776b}#joinResult[data-tone=warning],#scanHint[data-tone=warning]{color:#f0d48d}#joinResult[data-tone=error],#scanHint[data-tone=error],#error{color:#ffb7ae}#joinResult[data-tone=success],#scanHint[data-tone=success]{color:#b1e0c2}}</style><h1>给娃娃联网</h1><p id="progress" role="status">正在读取设备…</p><p id="error" role="alert"></p><small>iPhone若弹窗未出现，可在Safari打开 http://192.168.4.1/setup。切换Wi-Fi需在系统设置中完成。</small>
<section><h2>1 · 连接家庭Wi-Fi</h2><button id="scan" disabled>查找附近的Wi-Fi</button><small id="scanHint" role="status">只查找2.4 GHz网络；手机提示此热点没有互联网时，请选择继续连接。</small><select id="networks" aria-label="附近Wi-Fi"><option value="">也可手动输入名称</option></select><form id="wifiForm"><label for="ssid">Wi-Fi名称（2.4 GHz）</label><input id="ssid" maxlength="32" autocomplete="off" required><label for="password">Wi-Fi密码</label><input id="password" type="password" maxlength="63" autocomplete="off"><label><input id="showPassword" type="checkbox">显示密码</label><button id="join" disabled>保存并连接</button></form><p id="joinResult" role="status" aria-live="polite"></p><button id="checkWifi" type="button" class="secondary" hidden>检查连接状态</button><small>开放网络的密码留空。已有传感器设置与历史保留。</small></section>
<section><h2>2 · 保存入口，再切回家庭Wi-Fi</h2><p id="connection">设备联网后，这里会显示家庭地址。</p><label for="entry">设备固定入口</label><input id="entry" readonly aria-label="设备固定入口"><button id="copyEntry" disabled>复制设备入口</button><small id="copyNote">入口含配对信息，仅自己保管。可先保存，再切换网络；无需记住IP。</small><a id="openDevice" class="action" hidden>我已切回家庭Wi-Fi，打开设备</a><p id="familyIP"></p><a id="openIP" hidden>固定名称打不开时，尝试家庭IP</a></section>
<p><a id="advanced" href="/settings">更多设备设置</a></p><script src="/wifi-feedback.js"></script><script>
const $=id=>document.getElementById(id),fragment=new URLSearchParams(location.hash.slice(1));
let token=fragment.get('setup_token')||'',expected=fragment.get('device_id'),last=null,ready=false,polling=false;
let connectionLost=false;const wifiFeedback=createWifiFeedback(api,s=>show(s));
if(token)history.replaceState(null,'',location.pathname);
async function api(path,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),4500);
 try{const r=await fetch(path,{method:body?'POST':'GET',cache:'no-store',headers:{'Content-Type':'application/json','X-Setup-Token':path==='/api/identity'?'':token},body:body?JSON.stringify(body):undefined,signal:controller.signal});
  if(r.status===401||r.status===403)throw Error('访问权限未确认，请使用保存的完整入口，或重新连接娃娃临时热点。');
  const d=await r.json();if(!r.ok||d.error)throw Error(d.error||'操作未完成');return d;
 }finally{clearTimeout(timer);}
}
function address(host,id){const q=new URLSearchParams({setup_token:token,device_id:id});return 'http://'+host+'/setup#'+q;}
function show(s){
 last=s;ready=wifiFeedback.matches(s);const fixed=/^ai-doll-[a-f0-9]{12}\.local$/.test(s.hostname||'')?s.hostname:null;
 const ip=ready&&/^(\d{1,3}\.){3}\d{1,3}$/.test(s.ip||'')&&s.ip!=='0.0.0.0'?s.ip:null;
 const link=(fixed||ip)?address(fixed||ip,s.device_id):'';
 $('entry').value=link;$('copyEntry').disabled=!link;
 $('openDevice').hidden=!link||!ready;$('openDevice').href=link;
 $('openIP').hidden=!ip;if(ip)$('openIP').href=address(ip,s.device_id);
 $('familyIP').textContent=ip?'家庭IP：'+ip:'';
 $('advanced').href='/settings#setup_token='+encodeURIComponent(token);
 $('connection').textContent=ready?'设备已接入 '+s.ssid+'。现在到iPhone设置切回家庭Wi-Fi，再打开下方入口。':wifiFeedback.connecting?'正在连接家庭Wi-Fi。页面暂时失联时请等候后刷新，不必重复保存密码。':'先保存固定入口，再完成家庭Wi-Fi连接。';
 $('progress').textContent=ready?'已联网 · '+(s.device_name||s.device_id):wifiFeedback.connecting?'连接中 · 请查看下方进度':'设备已就绪';
 wifiFeedback.observe(s);
}
async function refresh(){
 if(polling||document.hidden)return;polling=true;
 try{const s=await api('/api/status');show(s);if(connectionLost){$('error').textContent='';connectionLost=false;}}
 catch(e){connectionLost=true;wifiFeedback.disconnected();$('progress').textContent='页面暂时失联';if(last?.wifi_connected)$('connection').textContent='上次确认已接入 '+last.ssid+'。若手机已切换网络，请打开保存的设备入口。';$('error').textContent=e.name==='AbortError'||e instanceof TypeError?'请确认手机当前连接的Wi-Fi。配网时可重新连接娃娃热点；若已切回家庭Wi-Fi，请打开保存的设备入口。':e.message;}
 finally{polling=false;}
}
$('showPassword').onchange=()=>{$('password').type=$('showPassword').checked?'text':'password';};
$('networks').onchange=()=>{if($('networks').value)$('ssid').value=$('networks').value;};
$('copyEntry').onclick=async()=>{const input=$('entry');input.focus();input.select();input.setSelectionRange(0,input.value.length);
 try{if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(input.value);else if(!document.execCommand('copy'))throw Error();$('copyNote').textContent='入口已复制。请保存到自己的备忘录，再切回家庭Wi-Fi。';}
 catch(_){$('copyNote').textContent='链接已选中，请长按复制并保存到自己的备忘录。';}
};
(async()=>{try{const identity=await api('/api/identity');if(expected&&expected!==identity.device_id)throw Error('设备身份与保存的入口不符，请重新配对。');
 const cfg=await api('/api/setup');token=cfg.token;await refresh();
 }catch(e){$('error').textContent=e.message;$('progress').textContent='需要检查连接';$('checkWifi').hidden=false;$('checkWifi').textContent='重新读取设备';$('checkWifi').onclick=()=>location.reload();return;}
 const timer=setInterval(refresh,2500);window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});document.addEventListener('visibilitychange',refresh);
})();
</script></html>)HTML";
