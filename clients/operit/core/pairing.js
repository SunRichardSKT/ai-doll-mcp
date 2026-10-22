// Connection text is data. A pending hotspot credential stays in private storage.
const store=require('./settings.js');
const PREFIX='AIDOLL1:',MAX_TEXT=16384;
const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
function utf8(text){return encodeURIComponent(text).replace(/%([0-9A-F]{2})/g,(_,hex)=>String.fromCharCode(parseInt(hex,16)));}
function encode(value){
 const bytes=utf8(JSON.stringify(parse(value)));let out='';
 for(let i=0;i<bytes.length;i+=3){const a=bytes.charCodeAt(i),b=bytes.charCodeAt(i+1),c=bytes.charCodeAt(i+2);
  out+=alphabet[a>>2]+alphabet[((a&3)<<4)|(Number.isNaN(b)?0:b>>4)]+
   (Number.isNaN(b)?'=':alphabet[((b&15)<<2)|(Number.isNaN(c)?0:c>>6)])+(Number.isNaN(c)?'=':alphabet[c&63]);}
 return PREFIX+out.replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
}
function decode(text){
 let input=text.slice(PREFIX.length);if(!input||!/^[A-Za-z0-9_-]+$/.test(input)||input.length%4===1)throw Error('连接码格式不正确。');
 input=input.replace(/-/g,'+').replace(/_/g,'/');let bits=0,value=0,bytes='';
 for(const char of input){value=(value<<6)|alphabet.indexOf(char);bits+=6;if(bits>=8){bits-=8;bytes+=String.fromCharCode((value>>bits)&255);}}
 if(bits&&(value&((1<<bits)-1)))throw Error('连接码内容不完整。');
 try{return decodeURIComponent(Array.from(bytes,char=>'%'+char.charCodeAt(0).toString(16).padStart(2,'0')).join(''));}
 catch(_){throw Error('连接码不是有效的 UTF-8 文本。');}
}
function field(value,name,limit=128){
 if(typeof value!=='string'||!value||value.length>limit||/[\x00-\x1f\x7f]/.test(value))throw Error('连接中的'+name+'无效。');return value;
}
function phoneHost(url){
 if(typeof url!=='string'||!/^http:\/\/[^/?#@]+\/mcp$/.test(url))throw Error('手机直连需要设备局域网 MCP 地址。');
 return require('./device.js').localHost(url.slice(7,-4));
}
function parse(input){
 let value=input;
 if(typeof value==='string'){
  value=value.trim();if(!value||value.length>MAX_TEXT)throw Error('连接内容为空或过长。');
  try{value=JSON.parse(value.startsWith(PREFIX)?decode(value):value);}catch(e){if(e.message?.includes('连接码'))throw e;throw Error('未识别连接内容，请选择 AI Doll 连接文件或连接码。');}
 }
 if(!value||value.schema!==1)throw Error('不支持的连接文件版本，原连接保持。');
 const label=typeof value.label==='string'?value.label.slice(0,80):'AI Doll';
 if(value.kind==='ai-doll-device-connection'){
  phoneHost(value.mcp_url);
  if(typeof value.token!=='string'||!/^\w{16,256}$/.test(value.token))throw Error('设备连接凭据格式不正确。');
  const result={schema:1,kind:value.kind,mode:'phone',mcp_url:value.mcp_url,token:value.token,
   device_id:field(value.device_id,'设备身份'),label};
  if(value.hostname!==undefined){if(!/^ai-doll-[a-f0-9]{12}\.local$/.test(value.hostname))throw Error('设备固定名称格式不正确。');result.hostname=value.hostname;}
  return result;
 }
 if(value.kind!=='ai-doll-operit-connection'||typeof value.mcp_url!=='string'||
   !/^https?:\/\/[^\s?#@]+\/[^\s?#]*mcp$/.test(value.mcp_url))throw Error('请选择设备或服务器提供的 AI Doll 连接文件。');
 const result={schema:1,kind:value.kind,mode:['simulation','server'].includes(value.mode)?value.mode:'device',mcp_url:value.mcp_url,label};
 for(const name of ['server_instance_id','pairing_id','expected_device_id'])if(value[name]!=null)result[name]=field(value[name],name);
 return result;
}
async function httpJson(url){
 const response=await Tools.Net.http({url,method:'GET',follow_redirects:false,ignore_ssl:false,connect_timeout:1800,read_timeout:1800});
 if(response.statusCode!==200)throw Error(response.statusCode===401?'设备已开启登录保护。请在热点设置页登录并导出连接文件／二维码，或在高级入口填写已有设备令牌。':'尚未读到热点设备，请先连接娃娃热点并保持该 Wi-Fi。');
 try{return JSON.parse(response.content);}catch(_){throw Error('设备没有返回有效的连接信息。');}
}
async function readHotspot(){
 const origin='http://192.168.4.1',identity=await httpJson(origin+'/api/identity'),setup=await httpJson(origin+'/api/setup');
 if(setup.enabled!==true)throw Error('请在设备设置页开启 MCP，然后重新读取。');
 const home=identity.ip&&identity.ip!=='0.0.0.0'&&identity.ip!=='192.168.4.1'?identity.ip:null;
 const connection=parse({schema:1,kind:'ai-doll-device-connection',mode:'phone',device_id:identity.device_id,
  hostname:identity.hostname,mcp_url:'http://'+(home||'192.168.4.1')+'/mcp',token:setup.token,label:identity.device_name||identity.device_id});
 const tool=await require('./mcp.js').connect(origin+'/mcp',connection.token),status=await tool('doll_get_status');
 if(status.device_id!==connection.device_id)throw Error('热点设备身份发生变化，请重新读取。');
 if(status.remote_server?.enabled)throw Error('该设备已开启直传服务器，请导入服务器连接，或先在设备设置页关闭直传。');
 const current=status.ip&&status.ip!=='0.0.0.0'&&status.ip!=='192.168.4.1'?status.ip:home;
 if(current){require('./device.js').localHost(current);connection.mcp_url='http://'+current+'/mcp';}
 connection.label=String(status.device_name||connection.label).slice(0,80);
 const draft={schema:1,id:store.id(),created_at:Date.now(),connection,home_ip:current||null};
 await store.write('pairing_draft.json',draft);
 return {candidate_id:draft.id,label:connection.label,device_id:connection.device_id,hostname:connection.hostname||null,
  home_ip:draft.home_ip,connected_to_home:!!draft.home_ip,setup_url:origin+'/'};
}
async function finish(input,prior){
 let connection;
 if(input?.candidate_id){
  const draft=await store.read('pairing_draft.json');
  if(!draft||draft.id!==input.candidate_id||Date.now()-draft.created_at>15*60*1000)throw Error('配对草稿已过期，请连接设备热点重新读取。');
  if(!draft.home_ip)throw Error('设备尚未连接家庭 Wi-Fi。请完成配网后再次读取热点设备，再切回家庭网络。');
  connection=parse(draft.connection);
 }else connection=parse(input);
 if(connection.kind==='ai-doll-device-connection'){
  const device=require('./device.js'),candidates=[...new Set([phoneHost(connection.mcp_url),connection.hostname].filter(Boolean))];let failure,identityFailure;
  for(const host of candidates){try{
   // Inspect the public identity before sending this paired device's credential.
   const identity=await httpJson('http://'+host+'/api/identity');
   if(identity.device_id!==connection.device_id){identityFailure=Error('此地址不是待配对的设备，原连接保持。');continue;}
   const result=await device.pair(host,connection.token,prior);
   if(result.device_id!==connection.device_id){identityFailure=Error('设备身份发生变化，请重新配对。');continue;}
   return result;
  }catch(e){failure=e;}}
  const reason=identityFailure||failure;
  throw Error('尚未核对到家庭设备。请将手机切回与娃娃互通的家庭 Wi-Fi，再点击完成配对。'+(reason?' '+reason.message:''));
 }
 const tool=await require('./mcp.js').connect(connection.mcp_url),status=await tool('get_installation_status');
 for(const name of ['server_instance_id','pairing_id'])if(connection[name]&&status[name]!==connection[name])throw Error('服务器安装或设备配对身份不符，原连接保持。');
 const deviceId=status.expected_device_id||status.device_id;
 if(connection.expected_device_id&&deviceId&&deviceId!==connection.expected_device_id)throw Error('服务器返回了不同设备，原连接保持。');
 // Learn the stable installation/pairing identifiers when upgrading an older
 // connection file. A run_id changes on restart and cannot identify a server.
 if(connection.mode==='server')for(const name of ['server_instance_id','pairing_id']){
  if(status[name]!=null)connection[name]=field(status[name],name);
 }
 if(connection.mode==='server'&&deviceId)connection.expected_device_id=field(deviceId,'设备身份');
 return connection;
}
exports.parse=parse;exports.encode=encode;exports.readHotspot=readHotspot;exports.finish=finish;
