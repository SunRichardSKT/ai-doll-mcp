// Full phone entry against the real push-server MCP. Android/model are doubles.
const assert=require('node:assert/strict');
const {fixture}=require('./operit_test_host.cjs');
(async()=>{
  const f=fixture({realTime:true});
  f.tools.Net.http=async p=>{
    const r=await fetch(p.url,{method:p.method,headers:p.headers,body:p.body,redirect:'manual'});
    return {statusCode:r.status,content:await r.text()};
  };
  await f.invoke('setup',{connection_json:process.argv[2]});
  assert.equal((await f.invoke('status')).connection.mode,'server');
  await f.invoke('bind_chat',{chat_id:'operit-server-chat'});
  assert.equal((await f.invoke('check_connection')).overview.online,true);
  await f.invoke('set_experience',{enabled:true});
  await f.invoke('schedule',{kind:'probe'});await f.invoke('run_task',{job_id:f.job().id});await f.invoke('confirm_probe');
  const cfg=f.cfg();cfg.duration_sec=3;f.disk.set('/managed/settings.json',JSON.stringify(cfg));
  await f.invoke('schedule',{kind:'interaction'});
  const report=await f.invoke('run_task',{job_id:f.job().id});
  assert.equal(report.replies,1);assert.equal(f.messages.length,2);
  assert.equal(f.messages[1].id,'operit-server-chat');assert.equal(f.messages[1].flags.runtime,'main');
  assert.ok(f.messages[1].text.includes('simulation'));
  assert.equal(f.job().phase,'completed');
  console.log('PASS Operit exported server connection -> push archive -> original MAIN chat -> receipt acknowledgement; no PC collector. Android/model are doubles.');
})().catch(e=>{console.error(e);process.exitCode=1;});
