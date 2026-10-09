/* Explicitly requested device-lab check. Creates/ends only this test's sessions.
 * Reads a local Bearer token without printing it; never enables sensors or outputs. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
require('./bridge_client.js');
const root=path.resolve(__dirname,'..'),work=path.join(root,'build','device-lab');
const token=JSON.parse(fs.readFileSync(path.join(work,'companion-private.json'),'utf8')).token;
const baseUrl='http://127.0.0.1:8768';
const tool=async(name,arguments={})=>{
 const response=await fetch(baseUrl+'/companion/tool',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({name,arguments})});
 const result=await response.json();if(!response.ok)throw Error('Device lab request failed');return result;
};
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve}};
function client(){return new DollBridgeClient({baseUrl,token,targetId:'lifecycle-test:'+crypto.randomUUID(),onInteraction:()=>assert.fail('Unexpected input; no model configured')})}
(async()=>{
 assert.equal((await tool('get_interaction_status')).active_session,null,'Another chat is active; do not run');
 const before=await tool('doll_get_status');assert.equal(before.sensor_mode,'simulation');assert.equal(before.physical_outputs_enabled,false);
 const checks=[];let current=null;
 try{
   current=client();const [first,second]=await Promise.all([current.start(),current.start()]);
   assert.equal(first.id,second.id);assert.equal((await tool('get_interaction_status')).active_session.chat_id,current.target);
   await current.stop();assert.equal((await tool('get_interaction_status')).active_session,null);
   checks.push('real HTTP double start reuses one session and stop ends it');

   current=client();const originalApi=current.api.bind(current),subscribed=deferred(),release=deferred();
   current.api=async(route,args,signal)=>{
     const result=await originalApi(route,args,signal);
     if(route==='/bridge/subscriptions'){subscribed.resolve(result);await release.promise}
     return result;
   };
   const start=current.start(),cancelled=assert.rejects(start,{name:'AbortError'});
   await subscribed.promise;const stop=current.stop();release.resolve();await cancelled;await stop;
   assert.equal(current.running,false);assert.equal((await tool('get_interaction_status')).active_session,null);
   const state=await originalApi('/bridge/status');
   assert.equal(state.subscriptions.some(row=>row.target_id===current.target&&row.active),false);
   checks.push('real created subscription cleaned after stop during delayed response');

   current=client();await current.start();const regular=current.api.bind(current);let fail=true;
   current.api=async(route,args,signal)=>{if(route==='/bridge/unsubscribe'&&fail)throw Error('explicit network test double');return regular(route,args,signal)};
   await assert.rejects(current.stop(),/服务器清理尚未完成/);
   assert.equal((await tool('get_interaction_status')).active_session,null);
   assert.equal(current.cleanupRequired,true);fail=false;await current.stop();
   assert.equal(current.cleanupRequired,false);assert.equal(current.sub,null);
   checks.push('failed unsubscribe still ends real session; explicit retry clears old subscription');
 }finally{if(current)await current.stop()}
 const after=await tool('doll_get_status');assert.equal(after.sensor_mode,'simulation');assert.equal(after.physical_outputs_enabled,false);
 assert.equal((await tool('get_interaction_status')).active_session,null);
 const report={passed:true,scope:'real local collector and paired device status; delayed response/failure injection is explicit',firmware:after.firmware,checks,physical_inputs_outputs:false,active_session:false,model_called:false,owner_history_deleted:false};
 fs.writeFileSync(path.join(work,'bridge-lifecycle-device-test.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
})().catch(error=>{console.error(error);process.exitCode=1});
