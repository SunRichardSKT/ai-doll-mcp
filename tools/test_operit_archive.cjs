// Actual phone archive/worker modules. Files, ESP32 and Android are doubles.
const assert=require('node:assert/strict'),path=require('node:path');
const {fixture}=require('./operit_test_host.cjs');
const modulePath=n=>path.resolve(__dirname,'../clients/operit/core/'+n+'.js');
const clone=v=>JSON.parse(JSON.stringify(v));
const tests=[];const test=(name,fn)=>tests.push([name,fn]);
let finished=require.main!==module;if(require.main===module)process.on('beforeExit',()=>{if(!finished){console.error('FAIL unresolved archive test');process.exitCode=1;}});
async function phone(options={}){
  const f=fixture(),store=f.load(modulePath('settings'));
  const c={schema:1,kind:'ai-doll-device-connection',mode:'phone',mcp_url:'http://192.168.1.50/mcp',
    device_id:'archive-test-device',storage_key:'archive_test',token:'fixture_archive_token_123456',label:'测试'};
  const cfg=await store.config();Object.assign(cfg,{connection:c,binding:'fixture-binding',chat:{id:'chat-1',title:'原聊天'},auto_sync_enabled:false});await store.write('settings.json',cfg);
  const state={boot:'boot-new',device:c.device_id,epoch:'epoch-a',uptime:100000,seq:0,events:[],persistent:[],lease:null,delivered:0,acks:[],calls:[],clock:true};
  const raw=(seq,change={})=>({seq,uptime_ms:state.uptime,phase:'start',touch_id:'touch-'+seq,channel:0,body_part:'头顶',source:'sensor',
    sensor_type:'pressure',direction:'input',quality:'ok',value:2500,unit:'adc_raw',...change});
  function emit(change={}){const event=raw(++state.seq,change);state.events.push(event);return event;}
  function backlog(count=48,boot='boot-old'){state.persistent=Array.from({length:count},(_,i)=>({storage_id:i+1,boot_id:boot,event:raw(i+1)}));}
  const storage=()=>({available:true,storage_epoch:state.epoch,pending_records:state.persistent.length,lost_records:0,clock_synced:state.clock,
    archive_lease_supported:!options.legacy});
  f.tools.Net.http=async p=>{
    if(p.method==='GET')return {statusCode:200,content:JSON.stringify(p.url.endsWith('/api/identity')?
      {device_id:state.device,ip:'192.168.1.50'}:{enabled:true,token:c.token})};
    const wire=JSON.parse(p.body);
    if(wire.method==='notifications/initialized')return {statusCode:202,content:''};
    let data;
    if(wire.method==='initialize')data={protocolVersion:'2025-11-25'};
    else {
      const {name,arguments:a}=wire.params;state.calls.push({name,args:clone(a)});
      if(options.beforeCall)await options.beforeCall(name,a,state,f);
      if(name==='doll_get_status')data={device_id:state.device,boot_id:state.boot,event_cursor:state.seq,uptime_ms:state.uptime,
        ip:'192.168.1.50',archive_lease_supported:!options.legacy};
      else if(name==='get_channel_config')data={port_state_model:'per_port_v1',channels:[{channel:0,name:'头顶',mode:'connected'}]};
      else if(name==='read_channel_values')data={values:[]};
      else if(name==='get_touch_events'){
        const persistent=a.include_persistent?clone(state.persistent.slice(0,24)):[];
        if(a.include_persistent&&!options.legacy){assert.equal(a.archive_lease_id,state.lease,'persistent read must hold the right lease');state.delivered=persistent.at(-1)?.storage_id||0;}
        data={device_id:state.device,boot_id:state.boot,uptime_ms:state.uptime,next_cursor:state.seq,event_storage:storage(),events:state.events.filter(e=>e.seq>a.after),
          ...(a.include_persistent?{persistent_events:persistent,storage_cursor:persistent.at(-1)?.storage_id||0,storage_has_more:state.persistent.length>24}:{})};
        if(options.mutateBatch&&a.include_persistent)options.mutateBatch(data);
      }else if(name==='acquire_archive_lease'){
        if(options.occupied)throw Error('MCP 调用未完成：Archive occupied by another collector');
        state.lease=state.lease||'a'.repeat(32);data={lease_id:state.lease,boot_id:state.boot,expires_in_sec:90};
      }else if(name==='renew_archive_lease'){
        assert.equal(a.lease_id,state.lease);data={lease_id:state.lease,boot_id:state.boot,expires_in_sec:90};
      }else if(name==='release_archive_lease'){
        assert.equal(a.lease_id,state.lease);state.lease=null;data={released:true};
      }else if(name==='acknowledge_events'){
        assert.equal(a.archive_lease_id,state.lease);assert.equal(a.storage_epoch,state.epoch);assert.equal(a.boot_id,state.boot);
        assert.ok(a.storage_cursor<=state.delivered);state.acks.push(clone(a));
        state.persistent=state.persistent.filter(e=>e.storage_id>a.storage_cursor);
        if(options.ackLost){options.ackLost=false;throw Error('network lost after accepted ACK');}
        data={acknowledged:true,pending_records:state.persistent.length};
      }else if(name==='set_device_time'){state.clock=true;data={clock_synced:true};}
      else throw Error('unexpected '+name);
    }
    return {statusCode:200,content:JSON.stringify({jsonrpc:'2.0',id:wire.id,result:wire.method==='initialize'?data:{structuredContent:data}})};
  };
  return {f,store,c,state,raw,emit,backlog,options,tool:await f.load(modulePath('device')).connect(c),archive:f.load(modulePath('archive')).create(c)};
}
test('256 records page without starving live input; cross-boot unknown time',async()=>{
  const p=await phone();p.backlog(256);
  let reported=(await p.tool('_sync_records')).added;p.emit();
  for(let i=0;i<11;i++)reported+=(await p.tool('_sync_records')).added;
  const history=await p.tool('query_device_history',{limit:200});
  const second=await p.tool('query_device_history',{after:history.next_cursor,limit:200});
  assert.equal(history.events.length+second.events.length,257);assert.equal(p.state.persistent.length,0);assert.equal(p.state.acks.length,11);
  assert.equal(reported,257,'sync progress includes newly archived backlog without counting duplicates');
  const all=[...history.events,...second.events],live=all.find(e=>e.boot==='boot-new');
  assert.equal(live.delivery_quality,'live');assert.equal(live.body_part,'头顶');
  const unknown=await p.tool('query_device_history',{date:'unknown',limit:200});assert.equal(unknown.events.length,200);
  assert.ok(unknown.events.every(e=>e.at===null&&e.time_quality==='unknown'&&e.delivery_quality==='offline_replay'));
  assert.ok(p.state.calls.filter(x=>x.name==='get_touch_events').every((x,i,a)=>!x.args.include_persistent||i>0&&!a[i-1].args.include_persistent),'each backlog page follows a live read');
});
test('deduplicate RAM/flash and retain original source/name',async()=>{
  const p=await phone();await p.tool('_sync_records');const event=p.emit({source:'simulation',body_part:'发生时名称'});
  p.state.persistent=[{storage_id:1,boot_id:p.state.boot,event:clone(event)}];await p.tool('_sync_records');
  assert.equal((await p.archive.query()).events.length,1);assert.equal((await p.archive.query()).events[0].source,'simulation');
  await p.tool('_sync_records');assert.equal((await p.archive.query()).events.length,1);
});
test('legacy copies only first 24 and throttles without ACK',async()=>{
  const p=await phone({legacy:true});p.backlog(48);await p.tool('_sync_records');
  for(let i=0;i<3;i++)await p.tool('_sync_records');
  assert.equal(p.state.calls.filter(x=>x.name==='get_touch_events'&&x.args.include_persistent).length,1);
  p.f.advance(10001);await p.tool('_sync_records');assert.equal((await p.archive.query()).events.length,24);
  assert.equal(p.state.acks.length,0);assert.equal(p.state.persistent.length,48);assert.equal((await p.tool('get_record_sync_status')).compatibility_copy_only,true);
});
test('archive write/commit/index readback failures never ACK',async()=>{
  for(const target of ['segment_','commit_','events.json','sync.json']){
    const p=await phone();p.backlog(24);const write=p.f.tools.Files.write;
    p.f.tools.Files.write=async(name,text,...args)=>{
      if(name.includes(target)&&(!name.endsWith('events.json')||JSON.parse(text).events.length>0)&&(!name.endsWith('sync.json')||JSON.parse(text).storage_cursor))return {successful:false};
      return write(name,text,...args);
    };
    await assert.rejects(p.tool('_sync_records'),/保存|校验/);assert.equal(p.state.acks.length,0,target);
    p.f.tools.Files.write=write;await p.tool('_sync_records');assert.equal(p.state.acks.length,1,target+' safely retries');assert.equal((await p.archive.query()).events.length,24);
  }
});
test('lost ACK response keeps a committed archive and retries next page',async()=>{
  const p=await phone({ackLost:true});p.backlog(48);await assert.rejects(p.tool('_sync_records'),/network lost/);
  assert.equal((await p.archive.query()).events.length,24);assert.equal(p.state.persistent.length,24);
  await p.tool('_sync_records');assert.equal((await p.archive.query()).events.length,48);assert.equal(p.state.persistent.length,0);
});
test('readback corruption never ACK; committed segments rebuild corrupt hot index',async()=>{
  const p=await phone();p.backlog(24);const read=p.f.tools.Files.read;let corrupt=true;
  p.f.tools.Files.read=async arg=>corrupt&&arg.path.includes('_segment_')?{content:'{}'}:read(arg);
  await assert.rejects(p.tool('_sync_records'),/校验/);assert.equal(p.state.acks.length,0);corrupt=false;
  await p.tool('_sync_records');p.f.disk.set('/managed/device_archive_test_events.json','{');
  p.f.resetModules();const archive=p.f.load(modulePath('archive')).create(p.c);assert.equal((await archive.query()).events.length,24);
});
test('uncommitted segments are ignored after process restart',async()=>{
  const p=await phone();p.backlog(24);const write=p.f.tools.Files.write;
  p.f.tools.Files.write=async(name,...rest)=>name.includes('_commit_')?{successful:false}:write(name,...rest);
  await assert.rejects(p.tool('_sync_records'));
  p.f.resetModules();assert.equal((await p.f.load(modulePath('archive')).create(p.c).query()).events.length,0);
});
test('receipts survive corrupt/missing event index and a concurrent ingest',async()=>{
  const p=await phone();await p.tool('_sync_records');p.emit();await p.tool('_sync_records');
  const context=await p.tool('get_chat_context',{chat_id:'chat-1'});assert.ok(context.receipt_id);
  p.emit({touch_id:'second'});
  await Promise.all([p.tool('_sync_records'),p.tool('acknowledge_chat_context',{chat_id:'chat-1',receipt_id:context.receipt_id})]);
  p.f.disk.set('/managed/device_archive_test_events.json','{');p.f.resetModules();
  const tool=await p.f.load(modulePath('device')).connect(p.c);
  assert.equal((await tool('query_device_history')).events.length,2);
  assert.equal((await tool('acknowledge_chat_context',{chat_id:'chat-1',receipt_id:context.receipt_id})).acknowledged,true);
  p.f.disk.delete('/managed/device_archive_test_events.json');p.f.resetModules();
  const archive=p.f.load(modulePath('archive')).create(p.c);assert.equal((await archive.index()).receipts[0].acked,true);
});

test('opening history during collection preserves newly committed live context',async()=>{
  const p=await phone();await p.tool('_sync_records');p.emit();await p.tool('_sync_records');
  p.f.resetModules();
  const archive=p.f.load(modulePath('archive')).create(p.c),tool=await p.f.load(modulePath('device')).connect(p.c);
  const gate=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
  const reading=gate(),continueRead=gate(),continueWrite=gate();
  const read=p.f.tools.Files.read,write=p.f.tools.Files.write;let heldRead=false,heldWrite=false;
  p.f.tools.Files.read=async arg=>{
    const result=await read(arg);
    if(!heldRead&&arg.path.includes('_segment_')){heldRead=true;reading.resolve();await continueRead.promise;}
    return result;
  };
  const history=archive.query();await reading.promise;
  p.f.advance(86400000);p.state.uptime+=86400000;p.emit();
  p.f.tools.Files.write=async(name,...args)=>{
    const result=await write(name,...args);
    if(!heldWrite&&name.includes('_history_')){heldWrite=true;await continueWrite.promise;}
    return result;
  };
  const sync=tool('_sync_records');
  // Let collection progress while Android's earlier history read is suspended.
  await new Promise(setImmediate);continueRead.resolve();await history;
  continueWrite.resolve();await sync;
  assert.deepEqual(Array.from((await tool('get_chat_context',{chat_id:'chat-1'})).events,e=>e.seq),[2],
    'an earlier history snapshot must not replace newly committed live input');
  assert.deepEqual(Array.from((await archive.query()).events,e=>e.seq),[1,2]);
});

test('acknowledged receipts retain retry identity without duplicate event bodies',async()=>{
  const p=await phone();await p.tool('_sync_records');let last;
  for(let i=0;i<20;i++){
    p.f.advance(2000);p.state.uptime+=2000;p.emit();await p.tool('_sync_records');
    last=await p.tool('get_chat_context',{chat_id:'chat-1'});
    assert.ok(last.receipt_id);
    await p.tool('acknowledge_chat_context',{chat_id:'chat-1',receipt_id:last.receipt_id});
  }
  const saved=await p.archive.index();assert.equal(saved.receipts.length,20);
  assert.ok(saved.receipts.every(r=>r.acked&&!r.events&&r.ids&&r.chat_id==='chat-1'));
  assert.equal((await p.archive.query()).events.length,20,'compacting receipts does not delete history');
  p.f.resetModules();const resumed=await p.f.load(modulePath('device')).connect(p.c);
  assert.equal((await resumed('acknowledge_chat_context',{chat_id:'chat-1',receipt_id:last.receipt_id})).acknowledged,true);
  assert.equal((await resumed('get_chat_context',{chat_id:'chat-1'})).events.length,0);
});
test('missing delivery metadata blocks replay instead of inventing empty receipts',async()=>{
  const p=await phone();await p.tool('_sync_records');p.emit();await p.tool('_sync_records');
  p.f.disk.delete('/managed/device_archive_test_events.json');p.f.disk.delete('/managed/device_archive_test_receipt_state.json');p.f.resetModules();
  const tool=await p.f.load(modulePath('device')).connect(p.c);
  const context=await tool('get_chat_context',{chat_id:'chat-1'});assert.equal(context.delivery_recovery_required,true);assert.equal(context.events.length,0);
  assert.equal((await tool('query_device_history')).events.length,1);
});
test('parseable invalid hot index restores receipt backup instead of accepting malformed arrays',async()=>{
  for(const field of ['events','seen','receipts']){
    const p=await phone();await p.tool('_sync_records');p.emit();await p.tool('_sync_records');
    const context=await p.tool('get_chat_context',{chat_id:'chat-1'});await p.tool('acknowledge_chat_context',{chat_id:'chat-1',receipt_id:context.receipt_id});
    const file='/managed/device_archive_test_events.json',value=JSON.parse(p.f.disk.get(file));value[field]={invalid:true};p.f.disk.set(file,JSON.stringify(value));p.f.resetModules();
    const tool=await p.f.load(modulePath('device')).connect(p.c);
    assert.equal((await tool('query_device_history')).events.length,1);assert.equal((await tool('get_chat_context',{chat_id:'chat-1'})).events.length,0);
    assert.equal((await tool('acknowledge_chat_context',{chat_id:'chat-1',receipt_id:context.receipt_id})).acknowledged,true);
  }
});
test('other collector lease does not suppress realtime collection',async()=>{
  const p=await phone({occupied:true});p.backlog(48);await p.tool('_sync_records');p.emit();
  const result=await p.tool('_sync_records');assert.equal(result.added,1);assert.equal(result.sync.lease_owner,'another_collector');assert.equal(p.state.acks.length,0);
  assert.equal((await p.archive.query()).events[0].delivery_quality,'live');
  p.options.occupied=false;await p.tool('_sync_records');assert.equal(p.state.acks.length,1);
});
test('stop during delayed lease acquire blocks ACK and releases acquired lease',async()=>{
  let resolveAcquired,entered;const gate=new Promise(r=>entered=r);
  const p=await phone({beforeCall:async name=>{if(name==='acquire_archive_lease'){entered();await new Promise(r=>resolveAcquired=r);}}});p.backlog(24);
  const work=p.tool('_sync_records');await gate;const stop=p.tool('_stop_record_sync');resolveAcquired();
  await assert.rejects(work,/停止/);await stop;assert.equal(p.state.acks.length,0);assert.equal(p.state.lease,null);
});
test('stop after disk commit but before ACK retains records and device copy',async()=>{
  const p=await phone();p.backlog(24);const write=p.f.tools.Files.write;let entered,resolveDisk,paused=false;
  const gate=new Promise(r=>entered=r);
  p.f.tools.Files.write=async(name,text,...args)=>{
    const result=await write(name,text,...args);
    if(!paused&&name.endsWith('_sync.json')&&JSON.parse(text).storage_cursor){paused=true;entered();await new Promise(r=>resolveDisk=r);}
    return result;
  };
  const work=p.tool('_sync_records');await gate;const stop=p.tool('_stop_record_sync');resolveDisk();
  await assert.rejects(work,/停止/);await stop;assert.equal(p.state.acks.length,0);assert.equal(p.state.persistent.length,24);assert.equal((await p.archive.query()).events.length,24);
});
test('boot/epoch mismatch and malformed page cursors never ACK',async()=>{
  for(const mutate of [b=>{b.boot_id='other-boot';},b=>{b.storage_cursor=999;},b=>{b.event_storage.storage_epoch='';}]){
    const p=await phone({mutateBatch:mutate});p.backlog(24);await assert.rejects(p.tool('_sync_records'));assert.equal(p.state.acks.length,0);
  }
});
test('simultaneous record reads share one collection flight',async()=>{
  const p=await phone();p.backlog(24);const results=await Promise.all([p.tool('_sync_records'),p.tool('_sync_records'),p.tool('_sync_records')]);
  assert.equal(p.state.calls.filter(x=>x.name==='acknowledge_events').length,1);assert.equal(results[0].sync.last_ack_cursor,results[2].sync.last_ack_cursor);
});
test('same identity after DHCP reuses the adapter and collection flight',async()=>{
  const p=await phone();p.backlog(24);const moved={...p.c,mcp_url:'http://192.168.1.61/mcp'};
  const second=await p.f.load(modulePath('device')).connect(moved);assert.equal(second,p.tool);
  await Promise.all([p.tool('_sync_records'),second('_sync_records')]);assert.equal(p.state.acks.length,1);
  await assert.rejects(p.f.load(modulePath('device')).connect({...moved,device_id:'another-device'}),/身份/);
});
test('release/renew lease and known earlier boot anchors',async()=>{
  const p=await phone();await p.tool('_sync_records');p.emit();await p.tool('_sync_records');
  const event=p.raw(9);p.state.boot='boot-next';p.state.seq=0;p.state.events=[];p.state.persistent=[{storage_id:1,boot_id:'boot-new',event}];
  await p.tool('_sync_records');const history=await p.archive.query();assert.ok(history.events.every(e=>Number.isFinite(e.at)));
  p.f.advance(31000);await p.tool('_sync_records');assert.ok(p.state.calls.some(x=>x.name==='renew_archive_lease'));
  await p.tool('_stop_record_sync');assert.equal(p.state.lease,null);
});
test('local dates filter across midnight independently of ingestion date',async()=>{
  const p=await phone();const midnight=new Date('2026-10-23T00:00:00').getTime();
  p.state.persistent=[{storage_id:1,boot_id:'old',event:p.raw(1,{device_time_ms:midnight-1000,time_quality:'device_clock'})},
    {storage_id:2,boot_id:'old',event:p.raw(2,{device_time_ms:midnight+1000,time_quality:'device_clock'})}];
  await p.tool('_sync_records');assert.equal((await p.archive.query({date:'2026-10-22'})).events.length,1);assert.equal((await p.archive.query({date:'2026-10-23'})).events.length,1);
});

test('calendar dates and explicit zero pagination are not silently normalized',async()=>{
  const p=await phone();
  for(const date of ['2026-02-29','2026-02-30','2026-04-31'])
    await assert.rejects(p.archive.query({date}),/日期/);
  assert.equal((await p.archive.query({date:'2028-02-29'})).events.length,0);
  await assert.rejects(p.archive.query({limit:0}),/页大小/);
  await assert.rejects(p.archive.query({after:false}),/游标/);
});
exports.phone=phone;
test('append cost stays bounded; checkpoints and restart retain the committed tail',async()=>{
  const p=await phone();let reads=0,dailyWrites=0;const read=p.f.tools.Files.read,write=p.f.tools.Files.write;
  p.f.tools.Files.read=async(...args)=>{reads++;return await read(...args);};
  p.f.tools.Files.write=async(name,...args)=>{if(name.includes('_history_'))dailyWrites++;return await write(name,...args);};
  const costs={};
  for(let seq=1;seq<=251;seq++){
    const before=reads;
    await p.archive.ingest({boot_id:'boot-new',uptime_ms:seq*100,next_cursor:seq,events:[p.raw(seq,{uptime_ms:seq*100})]},{live:true});
    if([11,101,251].includes(seq))costs[seq]=reads-before;
  }
  assert.ok(Math.max(...Object.values(costs))<=15,JSON.stringify(costs));assert.ok(dailyWrites<=3);
  const before=await p.archive.query({after:200,limit:100});assert.equal(before.events.length,51);
  p.f.disk.set('/managed/device_archive_test_events.json','{');p.f.resetModules();
  const restored=p.f.load(modulePath('archive')).create(p.c);
  assert.equal((await restored.all()).length,251);assert.equal((await restored.query({after:250})).events.length,1);
  console.log('Archive file reads at 10/100/250 prior batches: '+Object.values(costs).join('/'));
});
if(require.main===module)(async()=>{for(const [name,fn]of tests){await fn();console.log('PASS archive: '+name);}finished=true;console.log('PASS '+tests.length+' archive scenarios. No physical device, fsync guarantee or Android lock-screen claim.');})().catch(e=>{console.error(e);process.exitCode=1;});
