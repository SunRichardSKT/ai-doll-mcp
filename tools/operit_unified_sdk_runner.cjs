// Real local MCP, simulated device, and explicit Android/model doubles.
const assert=require('node:assert/strict');
const {fixture}=require('./operit_test_host.cjs');
const url=process.argv[2];
(async()=>{
  const f=fixture({realTime:true});
  f.tools.Net.http=async p=>{
    const r=await fetch(p.url,{method:p.method,headers:p.headers,body:p.body,redirect:'manual'});
    return {statusCode:r.status,content:await r.text()};
  };
  await f.invoke('setup',{connection_json:JSON.stringify({...f.connection,mcp_url:url})});
  await f.invoke('bind_chat',{chat_id:'operit-sdk-chat'});
  await f.invoke('check_connection');
  if(new URL(url).hostname!=='127.0.0.1'){
    // Only the stale phone-side address is a fixture. Candidate probing uses
    // the actual MCP HTTP service with its persisted private path and port.
    const saved=f.cfg(),binding=saved.binding,workflowIds=JSON.stringify(saved.workflows);
    const old=new URL(url);old.hostname=old.hostname==='192.168.254.254'?'192.168.254.253':'192.168.254.254';
    saved.connection.mcp_url=old.toString();f.disk.set('/managed/settings.json',JSON.stringify(saved));
    const journalPath='/managed/delivery_'+binding+'.json';
    f.disk.set(journalPath,JSON.stringify({schema:1,chat_id:saved.chat.id,mcp_url:old.toString(),pending:null,session_id:null}));
    await f.invoke('update_computer_address',{host:new URL(url).hostname});
    assert.equal(f.cfg().connection.mcp_url,url);assert.equal(f.cfg().binding,binding);
    assert.equal(JSON.stringify(f.cfg().workflows),workflowIds);
    assert.equal(f.messages.length,0,'DHCP repair only probes MCP; it does not send to chat');
  }
  const settings=f.cfg();settings.duration_sec=5;
  f.disk.set('/managed/settings.json',JSON.stringify(settings));
  // First prove only host return semantics using the visible diagnostic path.
  await f.invoke('schedule',{kind:'probe'});await f.invoke('run_task',{job_id:f.job().id});await f.invoke('confirm_probe');
  await f.invoke('schedule',{kind:'interaction'});
  const result=await f.invoke('run_task',{job_id:f.job().id});
  assert.equal(result.replies,1);assert.equal(result.model_response_returned,true);assert.equal(result.display_verified,false);
  assert.equal(f.messages.length,2);assert.ok(f.messages[1].text.includes('simulation'));
  assert.equal(f.messages[1].flags.hide_user_message,true);
  const journal=JSON.parse(f.disk.get('/managed/delivery_'+f.cfg().binding+'.json'));
  assert.equal(journal.pending,null);assert.equal(journal.session_id,null);
  assert.equal(f.flows.size,2);
  console.log('PASS actual unified package + SDK HTTP + demo archive + host doubles. No actual Android/model/display proof.');
})().catch(e=>{console.error(e);process.exitCode=1;});
