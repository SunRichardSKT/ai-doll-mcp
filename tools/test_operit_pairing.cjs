// Source modules with explicit Android/network doubles. No real pairing occurs.
const assert=require('node:assert/strict');
const {fixture}=require('./operit_test_host.cjs');
const clean=value=>JSON.parse(JSON.stringify(value));
const connection={schema:1,kind:'ai-doll-device-connection',mode:'phone',device_id:'fixture-pairing-device',
 mcp_url:'http://192.168.1.25/mcp',hostname:'ai-doll-000000000001.local',token:'fixture_pairing_token_225',label:'摸头娃娃 🐱'};
function phoneFixture({home='192.168.1.25',wrongIP=false}={}){
 const f=fixture(),requests=[];
 f.options.tool=async(name)=>name==='doll_get_status'?{device_id:connection.device_id,device_name:connection.label,ip:home,hostname:connection.hostname,
  boot_id:'fixture-boot',event_cursor:0,remote_server:{enabled:false}}:name==='get_channel_config'?{channels:[]}:{};
 const http=f.tools.Net.http;
 f.tools.Net.http=async p=>{requests.push(p);if(p.method==='GET')return {statusCode:200,content:JSON.stringify(p.url.endsWith('/api/setup')?
  {token:connection.token,enabled:true}:{device_id:wrongIP&&p.url.startsWith('http://192.168.1.25/')?'other-device':connection.device_id,
   hostname:connection.hostname,ip:home})};return http(p);};
 return {...f,requests,pairing:f.load(require('node:path').resolve(__dirname,'../clients/operit/core/pairing.js'))};
}
(async()=>{
 const f=phoneFixture(),pair=f.pairing;
 const code=pair.encode(connection);assert.ok(code.startsWith('AIDOLL1:'));
 assert.deepEqual(clean(pair.parse(code)),connection,'UTF-8 labels survive compact connection codes');
 const encoded=JSON.stringify({...connection,chat_id:'do-not-import',workflow:'never-run',storage_key:'injected-directory'});
 assert.deepEqual(clean(pair.parse(encoded)),connection,'only connection fields enter settings');
 assert.throws(()=>pair.parse('AIDOLL1:a'),/连接码/);
 assert.throws(()=>pair.parse({...connection,mcp_url:'http://example.com/mcp'}),/局域网/);
 assert.throws(()=>pair.parse({...connection,hostname:'other.local'}),/固定名称/);
 assert.throws(()=>pair.parse({...connection,token:'short'}),/凭据/);
 assert.throws(()=>pair.parse({...connection,schema:42}),/版本/);
 const candidate=await pair.readHotspot();assert.equal(candidate.connected_to_home,true);
 assert.equal(JSON.stringify(candidate).includes(connection.token),false,'credentials are not returned to the UI tool result');
 const draft=JSON.parse(f.disk.get('/managed/pairing_draft.json'));assert.equal(draft.connection.token,connection.token);
 const prior={...connection,storage_key:'existing_history'};
 const saved=await pair.finish({candidate_id:candidate.candidate_id},prior);
 assert.equal(saved.storage_key,'existing_history');assert.equal(saved.device_id,connection.device_id);
 await assert.rejects(pair.finish({candidate_id:'wrong'},prior),/过期/);
 assert.equal(f.disk.has('/managed/settings.json'),false,'candidate inspection never commits settings');
 const locked=phoneFixture();locked.tools.Net.http=async()=>({statusCode:401,content:''});
 await assert.rejects(locked.pairing.readHotspot(),/导出连接文件/,'protected hotspot does not assume native HTTP shares a WebView login cookie');
 assert.equal(locked.disk.has('/managed/pairing_draft.json'),false);
 const unconfigured=phoneFixture({home:'0.0.0.0'}),pending=await unconfigured.pairing.readHotspot();
 assert.equal(pending.connected_to_home,false);await assert.rejects(unconfigured.pairing.finish({candidate_id:pending.candidate_id}),/家庭 Wi-Fi/);
 const restored=phoneFixture();restored.disk.set('/managed/pairing_draft.json',unconfigured.disk.get('/managed/pairing_draft.json'));
 const restoredHTTP=restored.tools.Net.http;restored.tools.Net.http=async p=>{if(p.url.startsWith('http://192.168.4.1'))throw Error('hotspot closed');return restoredHTTP(p);};
 assert.equal((await restored.pairing.finish({candidate_id:pending.candidate_id},prior)).storage_key,'existing_history','fixed hostname finishes the draft after the hotspot closes');
 const occupied=phoneFixture({wrongIP:true});
 const recovered=await occupied.pairing.finish(connection,prior);assert.equal(recovered.device_id,connection.device_id);
 assert.equal(occupied.requests.some(p=>p.method==='POST'&&p.url==='http://192.168.1.25/mcp'),false,'wrong old IP receives no paired credential');
 const occupiedHTTP=occupied.tools.Net.http;
 occupied.tools.Net.http=async p=>{if(p.url.includes('.local'))throw Error('hostname unavailable');return occupiedHTTP(p);};
 await assert.rejects(occupied.pairing.finish(connection,prior),/不是待配对/,'a later hostname timeout does not hide an identity mismatch');
 const server={schema:1,kind:'ai-doll-operit-connection',mode:'server',mcp_url:'https://fixture.invalid/fixture/mcp',label:'服务器',
  server_instance_id:'server-instance',pairing_id:'pairing-id',expected_device_id:'expected-device'};
 const s=fixture({tool:async()=>({server_instance_id:'different',pairing_id:'pairing-id',device_id:'expected-device'})});
 const module=s.load(require('node:path').resolve(__dirname,'../clients/operit/core/pairing.js'));
 await assert.rejects(module.finish(server),/服务器安装/);
 s.options.tool=async()=>({server_instance_id:'server-instance',pairing_id:'pairing-id',expected_device_id:'wrong-device',online:false});
 await assert.rejects(module.finish(server),/不同设备/,'server expected_device_id is checked even without a device_id field');
 s.options.tool=async()=>({server_instance_id:'server-instance',pairing_id:'pairing-id',expected_device_id:'expected-device',online:false});
 assert.deepEqual(clean(await module.finish(server)),server,'offline hardware does not invalidate the verified server connection');
 const legacy={...server};delete legacy.server_instance_id;delete legacy.pairing_id;delete legacy.expected_device_id;
 assert.deepEqual(clean(await module.finish(legacy)),server,'old connection JSON learns the stable IDs returned by the server');
 await s.invoke('setup',{connection_json:JSON.stringify(server)});await s.invoke('bind_chat',{chat_id:'chat-1'});
 const before=s.cfg();before.continuous_enabled=true;before.background_verified=before.binding;
 s.disk.set('/managed/settings.json',JSON.stringify(before));s.disk.set('/managed/delivery_'+before.binding+'.json',JSON.stringify({seen:['keep']}));
 const moved={...server,mcp_url:'https://moved.fixture.invalid/new-path/mcp'};
 await s.invoke('setup',{connection_json:JSON.stringify(moved)});
 assert.equal(s.cfg().connection.mcp_url,moved.mcp_url);assert.equal(s.cfg().binding,before.binding);
 assert.equal(s.cfg().chat.id,'chat-1');assert.equal(s.cfg().continuous_enabled,true);
 assert.equal(s.cfg().background_verified,before.binding);assert.equal(s.messages.length,0);
 assert.deepEqual(JSON.parse(s.disk.get('/managed/delivery_'+before.binding+'.json')),{seen:['keep']});
 const committed=s.disk.get('/managed/settings.json');s.options.tool=async()=>{throw Error('network unavailable');};
 await assert.rejects(s.invoke('setup',{connection_json:JSON.stringify({...moved,mcp_url:'https://unreachable.fixture.invalid/new-path/mcp'})}),/network unavailable/);
 assert.equal(s.disk.get('/managed/settings.json'),committed,'failed candidate validation never replaces the usable connection');
 s.options.tool=async()=>({server_instance_id:'new-server-instance',pairing_id:'new-pairing-id',expected_device_id:'new-device'});
 const different={...server,server_instance_id:'new-server-instance',pairing_id:'new-pairing-id',expected_device_id:'new-device'};
 await assert.rejects(s.invoke('setup',{connection_json:JSON.stringify(different)}),/停止当前陪伴/,'different installation cannot silently replace an active companion');
 assert.equal(s.disk.get('/managed/settings.json'),committed);
 const stopped=s.cfg();stopped.continuous_enabled=false;s.disk.set('/managed/settings.json',JSON.stringify(stopped));
 await s.invoke('setup',{connection_json:JSON.stringify(different)});
 assert.notEqual(s.cfg().binding,before.binding);assert.equal(s.cfg().chat,null,'a newly paired server asks the user to select a chat again');
 assert.equal(s.cfg().continuous_enabled,false);assert.equal(s.cfg().background_verified,false);
 assert.deepEqual(JSON.parse(s.disk.get('/managed/delivery_'+before.binding+'.json')),{seen:['keep']},'old receipts remain archived under their previous binding');
 console.log('PASS: pairing UTF-8/allowlist, private hotspot drafts, family verification, wrong-IP recovery, server identity and cancellation-safe settings');
})().catch(error=>{console.error(error.stack||error);process.exitCode=1});
