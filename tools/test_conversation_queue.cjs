/* Existing-chat ordering and cancellation. Model callbacks are explicit test doubles. */
const assert=require('node:assert/strict');
require('./conversation_queue.js');require('./bridge_client.js');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve}};
const message={subscription_id:'sub',lease:'lease',event:{eventId:'press-1',data:{events:[{body_part:'头顶',source:'simulation'}]}}};
function bridge(queue,onInteraction,onReply=()=>{}){
 const c=new DollBridgeClient({targetId:'original-chat',onInteraction,onReply,
   runDelivery:(operation,{signal})=>queue.run('original-chat',operation,{signal})});
 c.sub={id:'sub'};c.api=async()=>({acknowledged:true});return c;
}
(async()=>{
 const checks=[];
 // Keep generation, ACK and async insertion under one lock shared with normal messages.
 const q=new DollConversationQueue(),normal=deferred(),render=deferred(),history=[],order=[];
 const first=q.run('original-chat',async()=>{order.push('normal begin');await normal.promise;history.push('normal reply');order.push('normal end')});
 const c=bridge(q,async()=>{assert.deepEqual(history,['normal reply']);order.push('event model');return {text:'explicit model test double',source:'model'}},async answer=>{order.push('insert begin');await render.promise;history.push(answer.text);order.push('insert end')});
 c.api=async()=>{order.push('ack');return {acknowledged:true}};
 const delivery=c.handle(message,new AbortController().signal);
 const next=q.run('original-chat',async()=>{assert.deepEqual(history,['normal reply','explicit model test double']);order.push('next normal')});
 await tick();assert.deepEqual(order,['normal begin']);normal.resolve();await first;await tick();
 assert.deepEqual(order,['normal begin','normal end','event model','ack','insert begin']);
 render.resolve();await Promise.all([delivery,next]);await tick();
 assert.deepEqual(order,['normal begin','normal end','event model','ack','insert begin','insert end','next normal']);
 assert.equal(q.pending('original-chat'),0);assert.equal(q.chats.size,0);
 checks.push('ordinary reply then event model then ACK/insertion then next ordinary reply');

 // End interaction while waiting: never invoke the model or block subsequent normal work.
 const hold=deferred(),q2=new DollConversationQueue();let calls=0;
 const active=q2.run('original-chat',()=>hold.promise);
 const stopped=bridge(q2,async()=>{calls++;return 'unexpected'}),cancel=new AbortController();
 const pending=stopped.handle(message,cancel.signal);
 const rejected=assert.rejects(pending,{name:'AbortError'});cancel.abort();await rejected;
 assert.equal(calls,0);assert.equal(q2.pending('original-chat'),1);
 const later=q2.run('original-chat',async()=>{calls++;return 'normal continues'});
 hold.resolve();await active;assert.equal(await later,'normal continues');assert.equal(calls,1);
 checks.push('queued interaction cancellation preserves normal conversation');

 // Cancellation cannot release the lock while an uncooperative generation still runs.
 const q3=new DollConversationQueue(),model=deferred();let started=false,nextStarted=false;
 const late=bridge(q3,async()=>{started=true;return model.promise},()=>assert.fail('late reply inserted'));
 late.api=async()=>assert.fail('cancelled generation acknowledged');
 const cancelActive=new AbortController(),running=late.handle(message,cancelActive.signal);
 const runningRejected=assert.rejects(running,/Delivery stopped/);
 await tick();assert.equal(started,true);cancelActive.abort();
 const after=q3.run('original-chat',async()=>{nextStarted=true});
 await tick();assert.equal(nextStarted,false);model.resolve({text:'late test double',source:'model'});
 await runningRejected;await after;assert.equal(nextStarted,true);
 checks.push('active cancellation holds queue until operation settles and discards late answer');

 // Host insertion receives the original stop signal even after the delivery lease was ACKed.
 const insertion=deferred(),qInsert=new DollConversationQueue(),stopInsert=new AbortController();
 let insertionEntered=false,inserted=false;
 const insertClient=bridge(qInsert,async()=>({text:'test double',source:'model'}),async(answer,event,ctx)=>{
   assert.equal(ctx.idempotencyKey,event.eventId);assert.equal(ctx.subscriptionId,'sub');
   insertionEntered=true;await insertion.promise;
   if(ctx.signal.aborted)return;inserted=true;
 });
 const inserting=insertClient.handle(message,stopInsert.signal);await tick();assert.equal(insertionEntered,true);
 stopInsert.abort();insertion.resolve();await inserting;assert.equal(inserted,false);
 checks.push('original application can cancel async message insertion after ACK');

 // Waiting for a slow normal message renews the event lease. Lost leases remove the queued task.
 const realInterval=global.setInterval,realClear=global.clearInterval;
 const q4=new DollConversationQueue(),blocked=deferred(),normalWork=q4.run('original-chat',()=>blocked.promise);
 let renewCallback,renewals=0;
 global.setInterval=fn=>{renewCallback=fn;return 'fixture-timer'};global.clearInterval=()=>{};
 try{
   const waiting=bridge(q4,()=>assert.fail('expired queued event generated'));
   waiting.api=async path=>{assert.equal(path,'/bridge/renew');renewals++;throw Error('lease expired')};
   const work=waiting.handle(message,new AbortController().signal),rejected=assert.rejects(work,{name:'AbortError'});
   renewCallback();await rejected;assert.equal(renewals,1);assert.equal(q4.pending('original-chat'),1);
 }finally{global.setInterval=realInterval;global.clearInterval=realClear;blocked.resolve();await normalWork}
 checks.push('lease renewal remains active while waiting for original chat queue');

 const q5=new DollConversationQueue({maxPending:2}),busy=deferred();
 const a=q5.run('a',()=>busy.promise),cancelQueued=new AbortController();
 const b=q5.run('a',()=>assert.fail('cancelled pending task ran'),{signal:cancelQueued.signal});
 const bRejected=assert.rejects(b,{name:'AbortError'});
 await assert.rejects(q5.run('a',()=>{}),/queue is full/);
 assert.equal(await q5.run('b',async()=>42),42);cancelQueued.abort();await bRejected;
 busy.resolve();await a;await tick();assert.equal(q5.chats.size,0);
 const aborted=new AbortController();aborted.abort();
 await assert.rejects(q5.run('a',()=>{}, {signal:aborted.signal}),{name:'AbortError'});
 const failure=q5.run('a',async()=>{throw Error('normal model failed')});await assert.rejects(failure,/normal model failed/);
 assert.equal(await q5.run('a',async()=>7),7);
 checks.push('separate chat isolation, capacity limit, early cancellation, cleanup and failure recovery');
 console.log(JSON.stringify({passed:true,model:'explicit callback test doubles; no actual AI inference',checks}));
})().catch(error=>{console.error(error);process.exitCode=1});
