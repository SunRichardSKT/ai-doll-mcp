// Fault injection through the actual exported tools and Android Files double.
const assert=require('node:assert/strict'),path=require('node:path');
const {fixture}=require('./operit_test_host.cjs');
const settings=path.resolve(__dirname,'../clients/operit/core/settings.js');
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
}
main().catch(e=>{console.error(e);process.exitCode=1;});
