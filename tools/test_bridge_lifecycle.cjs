/* Startup/stop races in an existing chat. No device/model is contacted. */
const assert=require('node:assert/strict');require('./bridge_client.js');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve}};
function fixture({pauseAt,existing=null,failSubscribe=false}={}){
 const paused=deferred(),calls=[],notices=[];let listeners=0;
 const c=new DollBridgeClient({targetId:'original-chat',onInteraction:()=>assert.fail('unexpected model'),onStatus:text=>notices.push(text)});
 c.listen=async()=>{listeners++};
 c.tool=async(name,args)=>{
   calls.push(name);
   if(name===pauseAt)await paused.promise;
   if(name==='get_interaction_status')return {active_session:existing};
   if(name==='doll_get_status')return {device_id:'device'};
   if(name==='start_interaction')return existing||{id:'session',chat_id:'original-chat'};
   if(name==='end_interaction'){assert.equal(args.session_id,(existing||{id:'session'}).id);return {ended:true}}
   assert.fail('unexpected tool '+name);
 };
 c.api=async(path,args)=>{
   calls.push(path);
   if(path===pauseAt)await paused.promise;
   if(path==='/bridge/subscriptions'){
     if(failSubscribe)throw Error('subscription failed');
     return {id:'subscription',expires:Date.now()/1000+300};
   }
   if(path==='/bridge/unsubscribe'){assert.equal(args.subscription_id,'subscription');return {unsubscribed:true}}
   assert.fail('unexpected API '+path);
 };
 return {c,calls,notices,paused,listeners:()=>listeners};
}
(async()=>{
 const checks=[];
 const multi=fixture({pauseAt:'doll_get_status'});
 const first=multi.c.start(),second=multi.c.start();await tick();
 assert.equal(multi.calls.filter(n=>n==='get_interaction_status').length,1);
 multi.paused.resolve();const [a,b]=await Promise.all([first,second]);assert.equal(a.id,b.id);
 assert.equal(multi.calls.filter(n=>n==='start_interaction').length,1);assert.equal(multi.listeners(),1);
 await multi.c.stop();assert.equal(multi.c.running,false);
 checks.push('double start uses one bootstrap, session and event listener');

 for(const pauseAt of ['get_interaction_status','doll_get_status','start_interaction','/bridge/subscriptions']){
   const f=fixture({pauseAt});const start=f.c.start(),rejected=assert.rejects(start,{name:'AbortError'});
   await tick();const stop=f.c.stop(),again=f.c.stop();assert.equal(f.c.running,false);
   f.paused.resolve();await rejected;await Promise.all([stop,again]);
   assert.equal(f.listeners(),0);assert.equal(f.c.session,null);assert.equal(f.c.sub,null);
   assert.equal(f.c.cleanupRequired,false);
   if(['start_interaction','/bridge/subscriptions'].includes(pauseAt))assert.equal(f.calls.filter(n=>n==='end_interaction').length,1);
   else assert.equal(f.calls.filter(n=>n==='start_interaction').length,0);
   if(pauseAt==='/bridge/subscriptions')assert.equal(f.calls.filter(n=>n==='/bridge/unsubscribe').length,1);
 }
 checks.push('stop at every awaited bootstrap stage prevents late monitoring and clears created IDs');

 const failed=fixture({failSubscribe:true});await assert.rejects(failed.c.start(),/subscription failed/);
 assert.equal(failed.calls.filter(n=>n==='end_interaction').length,1);assert.equal(failed.c.session,null);
 const existing={id:'original-session',chat_id:'original-chat'};
 const resume=fixture({existing,failSubscribe:true});await assert.rejects(resume.c.start(),/subscription failed/);
 assert.equal(resume.calls.includes('end_interaction'),false);assert.equal(resume.c.session,null);
 const owned=fixture({existing,pauseAt:'/bridge/subscriptions'});
 const ownedStart=owned.c.start(),ownedReject=assert.rejects(ownedStart,{name:'AbortError'});await tick();
 const ownedStop=owned.c.stop();owned.paused.resolve();await ownedReject;await ownedStop;
 assert.equal(owned.calls.filter(n=>n==='end_interaction').length,1);
 const foreign=fixture({existing:{id:'foreign',chat_id:'another-chat'}});
 await assert.rejects(foreign.c.start(),/另一个聊天/);assert.deepEqual(foreign.calls,['get_interaction_status']);
 checks.push('startup failure rolls back only new sessions; explicit stop closes resumed ownership; foreign chat untouched');

 const recovery=fixture();await recovery.c.start();let unsubscribeFailed=true;
 const ordinaryApi=recovery.c.api;
 recovery.c.api=async(path,args)=>{if(path==='/bridge/unsubscribe'&&unsubscribeFailed){recovery.calls.push(path);throw Error('network offline')}return ordinaryApi(path,args)};
 await assert.rejects(recovery.c.stop(),/服务器清理尚未完成/);
 assert.equal(recovery.c.running,false);assert.equal(recovery.c.controller.signal.aborted,true);
 assert.equal(recovery.c.session,null);assert.ok(recovery.c.sub);assert.equal(recovery.c.cleanupRequired,true);
 assert.equal(recovery.calls.includes('end_interaction'),true);
 // Starting cannot reopen until failed remote cleanup succeeds.
 const bootstrapCount=recovery.calls.filter(n=>n==='start_interaction').length;
 await assert.rejects(recovery.c.start(),/服务器清理尚未完成/);
 assert.equal(recovery.calls.filter(n=>n==='start_interaction').length,bootstrapCount);
 unsubscribeFailed=false;await recovery.c.stop();assert.equal(recovery.c.sub,null);assert.equal(recovery.c.cleanupRequired,false);
 await recovery.c.start();await recovery.c.stop();
 checks.push('unsubscribe failure still ends session, stops local listener, retains cleanup IDs and gates restart');

 const endFailure=fixture();await endFailure.c.start();let endFailed=true;
 const originalTool=endFailure.c.tool;
 endFailure.c.tool=async(name,args)=>{if(name==='end_interaction'&&endFailed){endFailure.calls.push(name);throw Error('end offline')}return originalTool(name,args)};
 await assert.rejects(endFailure.c.stop(),/服务器清理尚未完成/);
 assert.equal(endFailure.c.sub,null);assert.ok(endFailure.c.session);assert.equal(endFailure.c.cleanupRequired,true);
 endFailed=false;await endFailure.c.stop();assert.equal(endFailure.c.session,null);
 checks.push('end-session failure keeps only the unfinished session ID for retry');

 const restart=fixture({pauseAt:'start_interaction'});
 const cancelled=restart.c.start(),cancelledReject=assert.rejects(cancelled,{name:'AbortError'});await tick();
 const stopping=restart.c.stop(),newStart=restart.c.start();restart.paused.resolve();
 await cancelledReject;await stopping;await newStart;assert.equal(restart.listeners(),1);assert.equal(restart.c.running,true);
 assert.equal(restart.calls.filter(n=>n==='start_interaction').length,2);await restart.c.stop();
 checks.push('new start waits for cancelled bootstrap and remote stop before reopening');

 // A delayed 404 from an old fetch must not stop the replacement listener.
 const originalFetch=global.fetch,lateResponse=deferred();const stale=fixture();
 stale.c.sub={id:'old',expires:Date.now()/1000+300};stale.c.running=true;
 const old=new AbortController();stale.c.controller=old;
 global.fetch=()=>lateResponse.promise;
 try{
   const oldLoop=DollBridgeClient.prototype.listen.call(stale.c,old.signal);await tick();
   old.abort();stale.c.controller=new AbortController();stale.c.running=true;
   lateResponse.resolve({status:404});await oldLoop;
   assert.equal(stale.c.running,true);assert.equal(stale.c.controller.signal.aborted,false);
 }finally{global.fetch=originalFetch}
 checks.push('late old-stream 404 cannot cancel replacement interaction');
 console.log(JSON.stringify({passed:true,scope:'existing-chat lifecycle using HTTP/tool test doubles',checks}));
})().catch(error=>{console.error(error);process.exitCode=1});
