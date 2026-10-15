// Phone-only adapter over the existing firmware MCP. It never changes sampling,
// calibration, outputs, time or flash acknowledgements. No server is installed.
const store=require('./settings.js'),mcp=require('./mcp.js');
function now(){return Date.now()/1000;}
function localHost(input) {
  const text=String(input||'').trim().replace(/^http:\/\//,'').replace(/\/$/,'');
  const parts=text.split('.');
  if(parts.length!==4||parts.some(p=>!/^\d{1,3}$/.test(p)||Number(p)>255))throw Error('请输入设备设置页显示的家庭局域网 IP，例如 192.168.1.50。');
  const [a,b]=parts.map(Number);
  if(!(a===10||(a===172&&b>=16&&b<=31)||(a===192&&b===168)))throw Error('仅手机模式需要家庭局域网地址；远程服务器请选择服务器连接。');
  return parts.map(Number).join('.');
}
function identity(status,expected) {
  if(typeof status.device_id!=='string'||!status.device_id||status.device_id.length>128||
      (expected&&status.device_id!==expected))throw Error('设备身份与保存的绑定不符，请重新连接设备，不会读取其他设备。');
  if(status.remote_server?.enabled)throw Error('设备已开启直传服务器。请使用服务器模式，或先在设备设置页关闭直传，再连接手机。');
  return status;
}
async function pair(host,token,prior) {
  const origin='http://'+localHost(host);
  if(!token) {
    const result=await Tools.Net.http({url:origin+'/api/setup',method:'GET',follow_redirects:false,ignore_ssl:false,
      connect_timeout:10000,read_timeout:10000});
    if(result.statusCode!==200)throw Error('无法读取设备连接信息。请确认手机与设备同一 Wi-Fi；如开启了设备登录保护，请在设备设置页取得 MCP 令牌并填入高级选项。');
    const setup=JSON.parse(result.content);
    if(setup.enabled!==true)throw Error('请先在设备设置页开启 MCP。');
    token=setup.token;
  }
  if(typeof token!=='string'||!/^\w{16,256}$/.test(token))throw Error('设备 MCP 令牌格式不正确。');
  const tool=await mcp.connect(origin+'/mcp',token),status=identity(await tool('doll_get_status'));
  const config=await tool('get_channel_config');
  if(!Array.isArray(config.channels))throw Error('设备未返回通道配置，请检查固件。');
  return {schema:1,kind:'ai-doll-device-connection',mode:'phone',mcp_url:origin+'/mcp',token,
    device_id:status.device_id,storage_key:prior?.device_id===status.device_id?prior.storage_key:store.id(),label:status.device_id};
}
function valid(c) {
  if(c.kind!=='ai-doll-device-connection'||c.mcp_url!=='http://'+localHost(c.mcp_url.replace(/^http:\/\//,'').replace(/\/mcp$/,''))+'/mcp'||
    !/^[\w-]+$/.test(c.storage_key)||typeof c.token!=='string'||!/^\w{16,256}$/.test(c.token)||!c.device_id)
    throw Error('手机设备连接配置无效，原文件保留。');
}
async function connect(c) {
  valid(c);
  let remote;
  const native=async(name,args={})=>{
    if(!remote)remote=await mcp.connect(c.mcp_url,c.token);
    return await remote(name,args);
  };
  const prefix='device_'+c.storage_key+'_';
  const read=(name,def)=>store.read(prefix+name+'.json',def),write=(name,value)=>store.write(prefix+name+'.json',value);
  const defaults={chat_integration_enabled:true,proactive_enabled:false,allow_simulation:true,
    tone:'温柔自然',max_characters:160,merge_ms:300,cooldown_ms:1500,muted:false};
  const prefs=async()=>({...defaults,...await read('preferences',{})});
  async function archive(){return await read('events',{schema:1,next_id:1,events:[],seen:[],receipts:[],last_sync:null});}
  async function session(){const s=await read('session');return s&&!s.ended&&s.deadline>now()?s:null;}
  async function status(){return identity(await native('doll_get_status'),c.device_id);}
  async function overview(){
    const s=await status(),channels=await native('get_channel_config'),values=await native('read_channel_values'),a=await archive();
    return {online:true,device_id:s.device_id,firmware:s.firmware,sensor_mode:s.sensor_mode,
      physical_outputs_enabled:s.physical_outputs_enabled,channels:channels.channels,values,
      last_sync:a.last_sync,transport:'phone_device_wifi',history_source:'android_local',
      preferences:await prefs(),host_event_support:'operit_user_reported',
      background_guaranteed:false,recording_scope:'only_while_interaction_runs'};
  }
  async function poll(s,wait=0){
    const end=Math.min(s.deadline,now()+Math.max(0,Math.min(20,wait)));
    do {
      const active=await session();if(!active||active.id!==s.id)return;
      let a=await archive();
      const batch=await native('get_touch_events',{after:Math.max(s.boundary,a.boot===s.boot?a.cursor||0:0),boot_id:s.boot,include_persistent:false});
      if(batch.device_id!==c.device_id)throw Error('设备身份发生变化，请停止后重新连接。');
      if(batch.boot_id!==s.boot||batch.boot_changed){
        const latest=await read('session');if(latest?.id===s.id)await write('session',{...latest,ended:'device_restarted'});
        throw Error('设备已重启，本次互动结束；重新开始后只读取新触摸。');
      }
      if(!Array.isArray(batch.events)||!Number.isInteger(batch.next_cursor)||!Number.isFinite(batch.uptime_ms))throw Error('设备事件格式无效。');
      a=await archive();const day=new Date().toISOString().slice(0,10).replace(/-/g,'');
      const history=await read('history_'+day,{schema:1,events:[]});
      let added=0;
      for(const raw of batch.events){
        if(!Number.isInteger(raw.seq)||raw.seq<=s.boundary||raw.seq>batch.next_cursor||!Number.isFinite(raw.uptime_ms))continue;
        const key=c.device_id+':'+s.boot+':'+raw.seq;
        if(a.events.some(e=>e.event_id===key))continue;
        const age=(batch.uptime_ms-raw.uptime_ms)/1000;
        if(age<0)continue;
        const prior=history.events.find(e=>e.event_id===key);
        const event=prior||{...raw,id:a.next_id++,event_id:key,device_id:c.device_id,boot:s.boot,
          session_id:s.id,at:now()-age,delivery_quality:batch.gap?'offline_replay':'live',
          time_quality:'phone_estimated_from_device_uptime',received_at:now()};
        a.next_id=Math.max(a.next_id,event.id+1);a.events.push(event);if(!prior)history.events.push(event);added++;
      }
      // Daily history is committed first and never automatically removed. The
      // bounded hot index is for fresh-context lookup, not the durable archive.
      if(added)await write('history_'+day,history);
      a.events=a.events.slice(-2000);a.boot=s.boot;a.cursor=batch.next_cursor;a.last_sync=now();
      await write('events',a);
      if(added||now()>=end)return;
      await Tools.System.sleep(700);
    }while(now()<end);
  }
  async function context(args){
    const p=await prefs(),a=await archive(),after=args.after||0,limit=Math.max(1,Math.min(200,args.limit||50));
    const base={chat_id:args.chat_id,preferences:p,persona:'',feedback:{tone:p.tone,max_characters:p.max_characters,language:'zh-CN'},
      events:[],updates:[],receipt_id:null,next_cursor:after,last_sync:a.last_sync,history_source:'android_local'};
    if(!p.chat_integration_enabled||p.muted)return base;
    const selected=a.events.filter(e=>e.id>after&&e.phase==='start'&&e.sensor_type==='pressure'&&e.direction==='input'&&
      e.quality==='ok'&&['sensor','simulation'].includes(e.source)&&(e.source!=='simulation'||p.allow_simulation)&&
      e.delivery_quality==='live'&&e.touch_id&&e.at<=now()+2&&now()-e.at<=30&&
      !a.seen.some(x=>x.chat_id===args.chat_id&&x.boot===e.boot&&(x.touch_id===e.touch_id||
        (e.at>=x.at&&e.at-x.at<=Math.max(p.cooldown_ms,p.merge_ms)/1000)))).slice(0,limit)
      .map(e=>({...e,body_preferences:{feedback_level:'normal',aliases:[],interaction_hint:''}}));
    if(!selected.length)return base;
    const ids=selected.map(e=>e.event_id).join('|');
    let receipt=a.receipts.find(r=>r.chat_id===args.chat_id&&r.ids===ids&&!r.acked);
    if(!receipt){receipt={id:store.id(),chat_id:args.chat_id,ids,events:selected};a.receipts.push(receipt);await write('events',a);}
    return {...base,events:selected,receipt_id:receipt.id,expires_at:Math.min(...selected.map(e=>e.at+30)),next_cursor:selected[selected.length-1].id};
  }
  return async(name,args={})=>{
    if(name==='doll_get_status')return await status();
    if(name==='get_installation_status')return {online:!!await status(),transport:'phone_device_wifi',history_source:'android_local',device_id:c.device_id,
      adapter:'operit_phone',server_required:false,physical_outputs_changed:false};
    if(name==='get_device_overview')return await overview();
    if(name==='get_channel_config')return await native(name);
    if(name==='query_device_history'){
      const a=await archive(),events=a.events.slice(-Math.max(1,Math.min(200,args.limit||20)));
      return {events,history_source:'android_local',scope:'recent_index',last_sync:a.last_sync,
        durable_history:'daily_json_in_plugin_directory',recording_scope:'only_while_interaction_runs'};
    }
    if(name==='get_chat_context')return await context(args);
    if(name==='update_companion_preferences'){
      const changes=args.changes||{},keys=['chat_integration_enabled','proactive_enabled','allow_simulation','muted'];
      if(Object.keys(changes).some(k=>!keys.includes(k)||typeof changes[k]!=='boolean'))throw Error('手机模式仅支持聊天融入、主动回应、模拟与静音开关。');
      const p={...await prefs(),...changes};await write('preferences',p);return {updated:true,preferences:p};
    }
    if(name==='start_interaction'){
      const old=await session();if(old){if(old.chat_id!==args.chat_id)throw Error('另一个聊天正在互动，请先停止。');return old;}
      if(!args.chat_id||args.chat_id==='main'||!Number.isInteger(args.duration_sec)||args.duration_sec<1||args.duration_sec>3600)throw Error('请选择已有聊天和 1～3600 秒互动期限。');
      const p=await prefs();if(!p.proactive_enabled||!p.chat_integration_enabled||p.muted)throw Error('请先开启触摸回应。');
      const st=await status();if(!st.boot_id||!Number.isInteger(st.event_cursor))throw Error('设备未返回本次启动标识或事件边界。');
      const s={id:store.id(),chat_id:args.chat_id,started:now(),deadline:now()+args.duration_sec,boot:st.boot_id,boundary:st.event_cursor};
      await write('session',s);return s;
    }
    if(name==='get_interaction_status')return {active_session:await session()};
    if(name==='get_interaction_device_events'){
      const s=await session();if(!s)return {session_closed:true,events:[],next_cursor:args.after||0};
      if(s.id!==args.session_id||s.chat_id!==args.chat_id)throw Error('会话不属于当前聊天。');
      await poll(s,args.wait_seconds||0);
      const active=await session(),a=await archive();
      const events=a.events.filter(e=>e.session_id===s.id&&e.id>(args.after||0)).slice(0,args.limit||50);
      return {session:s,session_closed:!active,events,next_cursor:Math.max(args.after||0,...events.map(e=>e.id)),collector_error:null};
    }
    if(name==='end_interaction'){
      const s=await read('session');if(!s)return {ended:true};
      if(s.id!==args.session_id||s.chat_id!==args.chat_id)throw Error('不能结束其他聊天的互动。');
      await write('session',{...s,ended:s.ended||'user_ended'});return {ended:true};
    }
    if(name==='acknowledge_chat_context'){
      const a=await archive(),r=a.receipts.find(x=>x.id===args.receipt_id&&x.chat_id===args.chat_id);
      if(!r)throw Error('回执不属于当前聊天或不存在。');
      if(!r.acked){r.acked=true;for(const e of r.events)a.seen.push({chat_id:args.chat_id,boot:e.boot,touch_id:e.touch_id,at:e.at});
        a.seen=a.seen.slice(-2000);a.receipts=a.receipts.filter(x=>!x.acked||x===r);await write('events',a);}
      return {acknowledged:true,display_verified:false};
    }
    throw Error('手机直连不提供此服务器工具：'+name);
  };
}
exports.pair=pair;exports.connect=connect;exports.localHost=localHost;
