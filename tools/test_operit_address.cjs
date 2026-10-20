// Actual package modules; Android storage, workflows and MCP responses are doubles.
const assert=require('node:assert/strict'),path=require('node:path');
const {fixture}=require('./operit_test_host.cjs');
const modulePath=name=>path.resolve(__dirname,'../clients/operit/core/'+name+'.js');
const clone=value=>JSON.parse(JSON.stringify(value));
(async()=>{
  const f=fixture();await f.prepare();await f.invoke('check_connection');
  const cfg=f.cfg();cfg.background_verified=cfg.binding;cfg.duration_sec=900;
  cfg.probe_file='probe_saved.json';f.disk.set('/managed/settings.json',JSON.stringify(cfg));
  f.disk.set('/managed/probe_saved.json',JSON.stringify({phase:'completed',user_confirmed:true}));
  const journalPath='/managed/delivery_'+cfg.binding+'.json';
  const journal={schema:1,chat_id:cfg.chat.id,mcp_url:cfg.connection.mcp_url,session_id:null,
    pending:{phase:'sending',receipt_id:'keep-receipt',event_id:'keep-event'}};
  f.disk.set(journalPath,JSON.stringify(journal));
  f.disk.set('/managed/history_fixture.json','preserved history');
  const priorJournal=f.disk.get(journalPath),flows=JSON.stringify([...f.flows.entries()]);
  const moved=await f.invoke('update_computer_address',{host:' 192.168.1.30 '});
  assert.equal(moved.host,'192.168.1.30');assert.equal(f.cfg().connection.mcp_url,
    cfg.connection.mcp_url.replace('192.168.1.20','192.168.1.30'));
  for(const key of ['installation','chat','binding','workflows','background_verified','duration_sec','probe_file'])
    assert.deepEqual(f.cfg()[key],cfg[key],'preserve '+key);
  assert.equal(f.disk.get(journalPath),priorJournal,'uncertain delivery is not erased or acknowledged');
  assert.equal(f.disk.get('/managed/history_fixture.json'),'preserved history');
  assert.equal(JSON.stringify([...f.flows.entries()]),flows,'idle update does not recreate workflows');
  assert.equal((await f.invoke('status')).connection.computer_host,'192.168.1.30');
  const engine=f.load(modulePath('interaction')),store=f.load(modulePath('settings'));
  assert.equal((await engine.load(store.parameters(f.cfg()))).pending.receipt_id,'keep-receipt');
  await assert.rejects(f.invoke('schedule',{kind:'interaction'}),/尚未确认/);
  assert.equal(f.messages.length,0,'address repair never sends a chat message');
  // A long-unresolved send remains recognisable after repeated DHCP changes.
  for(let i=31;i<49;i++)await f.invoke('update_computer_address',{host:'192.168.1.'+i});
  assert.equal((await engine.load(store.parameters(f.cfg()))).pending.event_id,'keep-event');
  const params=store.parameters(f.cfg()),wrongChat={...params,chat_id:'chat-2'};
  await assert.rejects(engine.load(wrongChat),/another chat/);
  const other=clone(params);other.connection.mcp_url=other.mcp_url.replace('a'.repeat(64),'b'.repeat(64));
  other.mcp_url=other.connection.mcp_url;
  await assert.rejects(engine.load(other),/another chat/,'a different capability cannot inherit send receipts');
  const before=f.disk.get('/managed/settings.json');f.options.networkFailure=true;
  await assert.rejects(f.invoke('update_computer_address',{host:'192.168.1.60'}),/unreachable/);
  assert.equal(f.disk.get('/managed/settings.json'),before);assert.equal(f.disk.get(journalPath),priorJournal);
  f.options.networkFailure=false;f.options.writeFailure=true;
  await assert.rejects(f.invoke('update_computer_address',{host:'192.168.1.61'}),/未保存/);
  assert.equal(f.disk.get('/managed/settings.json'),before);f.options.writeFailure=false;
  for(const host of ['127.0.0.1','0.0.0.0','8.8.8.8','999.1.1.1','192.168.1.20:8775','https://192.168.1.20','192.168.1.20/mcp'])
    await assert.rejects(f.invoke('update_computer_address',{host}),/IPv4/);
  await f.invoke('setup',{connection_json:JSON.stringify({...f.connection,
    mcp_url:'http://192.168.1.60:8775/'+'b'.repeat(64)+'/mcp',previous_mcp_urls:[f.connection.mcp_url]})});
  assert.notEqual(f.cfg().binding,cfg.binding,'a different server creates its own binding');
  assert.equal(f.cfg().connection.previous_mcp_urls,undefined,'imported alias history is never trusted');
  assert.equal(f.disk.get(journalPath),priorJournal,'old ambiguous send stays preserved separately');
  for(const connection of [{...cfg.connection,mode:'server'},{kind:'ai-doll-device-connection',mode:'phone'}])
    assert.throws(()=>store.replaceComputerIP(connection,'192.168.1.50'),/电脑连接/);
  // Already scheduled work is cancelled. The next job reads the saved new URL.
  const scheduled=fixture();await scheduled.prepare();await scheduled.invoke('check_connection');
  await scheduled.invoke('schedule',{kind:'probe'});const oldJob=scheduled.job().id;
  await scheduled.invoke('update_computer_address',{host:'192.168.1.70'});
  assert.equal(scheduled.job().phase,'stopped');assert.ok([...scheduled.flows.values()].every(v=>!v.enabled));
  await assert.rejects(scheduled.invoke('run_task',{job_id:oldJob}),/不属于/);
  assert.equal(scheduled.messages.length,0);
  const wire=scheduled.tools.Net.http,urls=[];
  scheduled.tools.Net.http=async request=>{urls.push(request.url);return wire(request);};
  await scheduled.invoke('recover',{decision:'discard'});
  await scheduled.invoke('schedule',{kind:'probe'});
  await scheduled.invoke('run_task',{job_id:scheduled.job().id});await scheduled.invoke('confirm_probe');
  await scheduled.invoke('check_connection');
  assert.ok(urls.length>0&&urls.every(url=>url.includes('192.168.1.70:8775/')));
  console.log('PASS computer address repair: preserved binding/history/uncertain sends, repeated DHCP, isolation, failed network/write, cancelled old jobs and new workflow configuration. Android and real model remain unverified.');
})().catch(error=>{console.error(error);process.exitCode=1;});
