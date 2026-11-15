// Fault injection through the actual exported tools and Android Files double.
const assert=require('node:assert/strict'),path=require('node:path');
const {fixture}=require('./operit_test_host.cjs');
const settings=path.resolve(__dirname,'../clients/operit/core/settings.js');
let finished=false;
process.on('beforeExit',()=>{if(!finished){console.error('FAIL unresolved storage test');process.exitCode=1;}});
async function main(){
  const f=fixture();await f.prepare();const original=f.cfg();
  const store=f.load(settings);await store.write('settings.json',{...original,continuous_enabled:true,auto_sync_enabled:true,sync_paused:false});
  await store.write('job.json',{id:'running-task',phase:'running',binding:original.binding,worker_deadline:Date.now()+1e12});
  f.disk.set('/managed/settings.json','{"schema":');f.resetModules();
  const restored=await f.invoke('status');
  assert.equal(restored.configured,true);assert.equal(f.cfg().installation,original.installation);
  assert.equal(f.cfg().binding,original.binding);assert.equal(f.cfg().chat.id,original.chat.id);
  assert.equal(restored.continuous_enabled,false);assert.equal(restored.sync_paused,true);
  assert.ok(restored.storage_recovery);assert.equal(f.messages.length,0);
  assert.ok([...f.disk.keys()].some(n=>n.includes('settings_damaged_')));
  await f.invoke('get_panel');await f.invoke('stop');
  console.log('PASS storage: corrupt settings restore identity/binding and pause delivery');

  const job=fixture();await job.prepare();const s=job.load(settings);
  await s.write('settings.json',{...job.cfg(),continuous_enabled:true,auto_sync_enabled:true,sync_paused:false});
  await s.write('job.json',{id:'worker',phase:'running',worker_deadline:Date.now()+1e12});
  job.disk.set('/managed/job.json','{');job.resetModules();await job.invoke('status');
  assert.equal(job.job().phase,'interrupted');assert.equal(job.cfg().continuous_enabled,false);assert.equal(job.cfg().sync_paused,true);
  assert.equal((await job.invoke('run_task',{job_id:'watchdog:'+job.cfg().binding})).listening,false);
  assert.equal(job.messages.length,0);console.log('PASS storage: recovered job cannot restart the watchdog');

  const interrupted=fixture();await interrupted.prepare();const before=interrupted.cfg(),files=interrupted.tools.Files,write=files.write;
  files.write=async(name,text,...rest)=>{
    if(name==='/managed/settings.json'){interrupted.disk.set(name,'{"schema":');return {successful:true};}
    return await write(name,text,...rest);
  };
  await assert.rejects(interrupted.load(settings).write('settings.json',{...before,chat:{id:'other'}}),/JSON|校验/);
  files.write=write;interrupted.resetModules();await interrupted.invoke('status');
  assert.equal(interrupted.cfg().chat.id,before.chat.id);assert.equal(interrupted.cfg().binding,before.binding);
  console.log('PASS storage: interrupted overwrite retains the previous checked state');

  const broken=fixture();await broken.prepare();broken.disk.set('/managed/settings.json','{');
  const backup=JSON.parse(broken.disk.get('/managed/settings_backup.json'));backup.data.chat={id:'tampered'};
  broken.disk.set('/managed/settings_backup.json',JSON.stringify(backup));broken.resetModules();
  assert.equal((await broken.invoke('status')).recovery_required,true);
  assert.equal((await broken.invoke('get_panel')).recovery_required,true);
  assert.equal((await broken.invoke('stop')).stopped,true);
  assert.equal(broken.disk.get('/managed/settings.json'),'{');
  await broken.invoke('setup',{connection_json:JSON.stringify(broken.connection)});
  assert.equal((await broken.invoke('status')).configured,true);assert.equal(broken.cfg().chat,null);
  assert.equal(broken.messages.length,0);console.log('PASS storage: unusable backups leave recovery/import/stop accessible without replay');

  const missing=fixture();await missing.prepare();const identity=missing.cfg().installation;
  missing.disk.delete('/managed/settings.json');missing.resetModules();await missing.invoke('status');
  assert.equal(missing.cfg().installation,identity);
  missing.disk.delete('/managed/settings.json');missing.disk.set('/managed/settings_backup.json','{');missing.resetModules();
  assert.equal((await missing.invoke('status')).recovery_required,true);
  console.log('PASS storage: a missing main file is not mistaken for a new installation');
  for(const text of ['null','{"schema":1,"installation":"invalid"}']){
    const incomplete=fixture();incomplete.disk.set('/managed/settings.json',text);
    assert.equal((await incomplete.invoke('status')).recovery_required,true);
    assert.equal(incomplete.disk.get('/managed/settings.json'),text);
  }
  for(const text of ['{"schema":1}','null','{"schema":1,"data":null}']){
    const invalidBackup=fixture();invalidBackup.disk.set('/managed/settings.json','{');
    invalidBackup.disk.set('/managed/settings_backup.json',text);
    assert.equal((await invalidBackup.invoke('status')).recovery_required,true);
    assert.equal((await invalidBackup.invoke('stop')).stopped,true);
  }
  const concurrent=fixture();await concurrent.prepare();const updates=concurrent.load(settings);
  await Promise.all([updates.updateConfig({reply_prompt:'新的回应方式'}),updates.updateConfig({response_wait_sec:3})]);
  assert.equal(concurrent.cfg().reply_prompt,'新的回应方式');assert.equal(concurrent.cfg().response_wait_sec,3);
  console.log('PASS storage: concurrent partial updates preserve both fields');

  for(const action of ['prompt','stop']){
    const pending=fixture();await pending.prepare();const http=pending.tools.Net.http;
    let arrived,release;const entered=new Promise(resolve=>arrived=resolve);
    pending.tools.Net.http=async request=>{
      const body=JSON.parse(request.body);
      if(body.params?.name==='update_companion_preferences'){
        arrived();await new Promise(resolve=>release=resolve);
        return {statusCode:200,content:JSON.stringify({jsonrpc:'2.0',id:body.id,result:{structuredContent:{
          preferences:{proactive_enabled:true,chat_integration_enabled:true}}}})};
      }
      return await http(request);
    };
    const enabling=pending.invoke('set_experience',{enabled:true});await entered;
    if(action==='prompt'){
      await pending.invoke('set_experience',{reply_prompt:'在请求期间保存的新回应方式'});
      release();await enabling;
      assert.equal(pending.cfg().reply_prompt,'在请求期间保存的新回应方式');
    }else{
      await pending.invoke('stop');const generation=pending.cfg().control_generation;
      release();await assert.rejects(enabling,/已停止/);
      assert.equal(pending.cfg().control_generation,generation);assert.equal(pending.cfg().sync_paused,true);
      assert.equal(pending.cfg().continuous_enabled,false);
      assert.ok([...pending.flows.values()].every(flow=>!flow.enabled));
    }
    console.log('PASS storage: delayed enable preserves later '+action);
  }
  const scheduling=fixture();await scheduling.prepare();
  const create=scheduling.tools.Workflow.create;let arrived,release;
  const entered=new Promise(resolve=>arrived=resolve);
  scheduling.tools.Workflow.create=async(...args)=>{arrived();await new Promise(resolve=>release=resolve);return await create(...args);};
  const creating=scheduling.invoke('check_connection');await entered;
  await scheduling.invoke('stop');const stoppedGeneration=scheduling.cfg().control_generation;
  scheduling.tools.Workflow.create=create;release();await creating;
  assert.equal(scheduling.cfg().control_generation,stoppedGeneration);assert.equal(scheduling.cfg().sync_paused,true);
  assert.ok(scheduling.cfg().workflows.probe,'new disabled workflow ownership is retained after stop');
  assert.ok([...scheduling.flows.values()].every(flow=>!flow.enabled));
  const flows=scheduling.load(path.resolve(__dirname,'../clients/operit/core/workflows.js'));
  await assert.rejects(flows.schedule({...scheduling.cfg(),control_generation:stoppedGeneration-1},'probe',{id:'old-request'}),/已停止/);
  assert.ok([...scheduling.flows.values()].every(flow=>!flow.enabled));
  console.log('PASS storage: workflow creation preserves stop and cannot activate an older request');
  const update=scheduling.tools.Workflow.update;let activating,finishActivation;
  const activationStarted=new Promise(resolve=>activating=resolve);
  scheduling.tools.Workflow.update=async(id,changes)=>{
    if(changes.enabled===true){activating();await new Promise(resolve=>finishActivation=resolve);}
    return await update(id,changes);
  };
  const activation=flows.schedule(scheduling.cfg(),'probe',{id:'before-stop'});await activationStarted;
  await scheduling.invoke('stop');finishActivation();await assert.rejects(activation,/已停止/);
  assert.ok([...scheduling.flows.values()].every(flow=>!flow.enabled));
  assert.equal(scheduling.cfg().sync_paused,true);
  console.log('PASS storage: delayed workflow activation is disabled when stop wins');
  finished=true;
}
main().catch(e=>{console.error(e);process.exitCode=1;});
