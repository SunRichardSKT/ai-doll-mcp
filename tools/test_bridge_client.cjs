/* Client races: do not render until ACK, and never render cancelled generations. */
const assert=require('assert');require('./bridge_client.js');
const message={subscription_id:'s',lease:'lease1',event:{eventId:'event1',data:{events:[]}}};
function client(onInteraction,onReply){const c=new DollBridgeClient({targetId:'test',onInteraction,onReply});c.sub={id:'s'};return c}
(async()=>{
 let models=0,renders=0,acks=0;
 const c=client(async()=>{models++;return {text:'model answer',source:'model'}},()=>renders++);
 c.api=async path=>{assert.equal(path,'/bridge/ack');acks++;return {acknowledged:true}};
 await c.handle(message,new AbortController().signal);
 await c.handle({...message,lease:'lease2'},new AbortController().signal);
 assert.equal(models,1);assert.equal(renders,1);assert.equal(acks,2);
 let resolveModel;const pending=new Promise(resolve=>resolveModel=resolve);
 const cancelled=client(()=>pending,()=>{throw Error('Cancelled reply rendered')});
 cancelled.api=async()=>{throw Error('Cancelled reply ACKed')};
 const controller=new AbortController(),handling=cancelled.handle(message,controller.signal);
 controller.abort();resolveModel({text:'late reply',source:'model'});
 await assert.rejects(handling,/Delivery stopped/);
 let failure=true,rendered=0,calls=0;
 const retry=client(async()=>{calls++;return {text:'cached answer',source:'model'}},()=>rendered++);
 retry.api=async()=>{if(failure)throw Error('expired lease');return {acknowledged:true}};
 await assert.rejects(retry.handle(message,new AbortController().signal),/expired lease/);assert.equal(rendered,0);
 failure=false;await retry.handle({...message,lease:'new lease'},new AbortController().signal);
 assert.equal(calls,1);assert.equal(rendered,1);
 console.log('Client duplicate reuse, ACK-before-render, cancelled generation and expired lease retry PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
