const assert=require('node:assert/strict');
const {fixture}=require('./operit_test_host.cjs');
(async()=>{
 let writes=0,prefs={persona_source:'chat',doll_persona:''};
 const ports=[{channel:0,name:'头',type:'pressure',mode:'connected',enabled:true,mux_port:0,options:{press_threshold:699,release_threshold:295}},
  {channel:1,name:'手',type:'pressure',mode:'off',enabled:false,mux_port:1,options:{press_threshold:900,release_threshold:200}}];
 const f=fixture({tool:async(name,a)=>{
  if(name==='get_device_overview')return {online:true,device_id:'fixture',device_ip:'192.168.1.50',port_state_model:'per_port_v1',channels:ports,values:[],preferences:prefs};
  if(name==='get_channel_config')return {channels:ports,port_state_model:'per_port_v1'};
  if(name==='get_persona')return {persona:'旧保存的人设'};
  if(name==='get_settings_entry')return {entries:[{url:'http://127.0.0.1:8768/companion',scope:'computer'}]};
  if(name==='update_body_part'){writes++;Object.assign(ports.find(c=>c.channel===a.channel),a.changes);return {updated:true};}
  if(name==='update_companion_preferences'){prefs={...prefs,...a.changes};return {preferences:prefs};}
  return {ok:true};
 }});
 await f.prepare();const before=JSON.stringify(ports[1]);
 const p=await f.invoke('get_panel');assert.equal(p.channels.length,2);assert.equal(p.channels[1].mode,'off');
 assert.equal(f.calls.filter(c=>c.method==='tools/call').length,2,'setup and panel each read one tool; channels, persona and settings are reused');
 assert.equal(p.settings_entries.length,1);assert.equal(p.settings_entries[0].url,'http://192.168.1.50/');
 assert.equal(p.electrical_presence_detection,false,'installation state is not electrical detection');assert.equal(writes,0);
 await f.invoke('update_port',{channel:0,name:'头顶',mode:'simulation'});
 assert.equal(ports[0].mode,'simulation');assert.equal(ports[0].name,'头顶');assert.equal(ports[0].options.press_threshold,699);
 assert.equal(JSON.stringify(ports[1]),before);
 await assert.rejects(f.invoke('update_port',{channel:0,mode:'unknown'}));assert.equal(writes,1);
 await f.invoke('set_persona_source',{source:'doll',text:'保存的娃娃角色'});assert.equal(prefs.persona_source,'doll');
 await f.invoke('set_persona_source',{source:'chat'});assert.equal(prefs.doll_persona,'保存的娃娃角色','switching back never deletes saved persona');
 const binding=f.cfg().binding;await f.invoke('diagnostics');assert.equal(f.cfg().binding,binding);assert.equal(f.messages.length,0);
 console.log('PASS controls: all ports, partial writes, persona retention, reachable settings links, no diagnostic side effects. Device is a double.');
})().catch(e=>{console.error(e);process.exitCode=1;});
