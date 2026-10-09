/* Same-origin browser adapter. A custom API app supplies onInteraction to call
 * its own backend/model. MCP Events webhook delivery uses the Python adapter. */
class DollBridgeClient {
  constructor({baseUrl='',token=null,csrf=null,onInteraction,onReply=()=>{},onStatus=()=>{},onDeliveryState=()=>{},runDelivery=operation=>operation(),targetId}) {
    if(typeof onInteraction!=='function')throw Error('onInteraction callback required');
    this.base=baseUrl.replace(/\/$/,'');this.token=token;this.csrf=csrf;
    this.onInteraction=onInteraction;this.onReply=onReply;this.onStatus=onStatus;
    this.onDeliveryState=onDeliveryState;
    if(typeof runDelivery!=='function')throw Error('runDelivery callback required');
    this.runDelivery=runDelivery;
    this.target=targetId||'app:'+crypto.randomUUID();this.completed=new Map();this.rendered=new Set();
    this.running=false;this.sub=null;this.session=null;
  }
  async api(path,data,signal) {
    const headers={'Content-Type':'application/json'};
    if(this.token)headers.Authorization='Bearer '+this.token;
    if(this.csrf)headers['X-CSRF-Token']=this.csrf;
    const response=await fetch(this.base+path,{method:data===undefined?'GET':'POST',headers,body:data===undefined?undefined:JSON.stringify(data),signal});
    const result=await response.json();if(!response.ok)throw Error(result.error||'Bridge request failed');return result;
  }
  tool(name,args={}){return this.api('/companion/tool',{name,arguments:args})}
  async start() {
    if(this.running)return;
    const current=await this.tool('get_interaction_status');
    if(current.active_session&&current.active_session.chat_id!==this.target)throw Error('另一个聊天正在互动，请先在原窗口结束互动。');
    const status=await this.tool('doll_get_status');
    this.session=await this.tool('start_interaction',{chat_id:this.target,idle_timeout_sec:300});
    try{this.sub=await this.api('/bridge/subscriptions',{target_id:this.target,session_id:this.session.id,device_id:status.device_id,ttl_sec:300});}
    catch(error){if(!current.active_session)await this.tool('end_interaction',{session_id:this.session.id});throw error}
    this.controller=new AbortController();this.running=true;
    this.onStatus('已订阅当前互动，等待新的按压。');
    this.loop=this.listen(this.controller.signal);return this.sub;
  }
  async handle(message,signal) {
    if(signal.aborted)throw Error('Delivery stopped or lease expired');
    const {event,lease,subscription_id}=message;
    if(!event?.eventId||subscription_id!==this.sub.id)throw Error('Unexpected event target');
    const args={subscription_id,event_id:event.eventId,lease};
    const generation=new AbortController();
    const abort=()=>generation.abort();signal.addEventListener('abort',abort,{once:true});
    let lostLease=false;
    const renew=setInterval(()=>this.api('/bridge/renew',args,signal).catch(()=>{lostLease=true;generation.abort()}),4000);
    try{
      this.onDeliveryState(true,event);
      await this.runDelivery(async()=>{
        if(signal.aborted||generation.signal.aborted)throw Error('Delivery stopped or lease expired');
        let answer=this.completed.get(event.eventId);
        if(!answer){
          answer=await this.onInteraction(event,{signal:generation.signal,idempotencyKey:event.eventId,
            subscriptionId:subscription_id,lease});
          if(typeof answer==='string')answer={text:answer,source:'model'};
          if(answer!=null&&(!answer.text||!['model','demo'].includes(answer.source)))throw Error('Return {text,source:"model"} or null');
          this.completed.set(event.eventId,answer||{});
          if(this.completed.size>128)this.completed.delete(this.completed.keys().next().value);
        }
        if(signal.aborted||lostLease)throw Error('Delivery stopped or lease expired');
        await this.api('/bridge/ack',{...args,...(answer?.text?{reply:answer.text,source:answer.source}:{})},signal);
        clearInterval(renew); // ACK releases the lease; insertion no longer renews it.
        if(answer?.text&&!signal.aborted&&!this.rendered.has(event.eventId)){
          await this.onReply(answer,event,{signal,idempotencyKey:event.eventId,subscriptionId:subscription_id});this.rendered.add(event.eventId);
          if(this.rendered.size>128)this.rendered.delete(this.rendered.values().next().value);
        }
      },{signal:generation.signal,event});
    }finally{clearInterval(renew);signal.removeEventListener('abort',abort);this.onDeliveryState(false,event)}
  }
  async listen(signal) {
    while(this.running&&!signal.aborted){
      try{
        if(Date.now()/1000>=this.sub.expires){this.onStatus('订阅已到期，停止主动反馈。');await this.stop();return}
        const headers={};if(this.token)headers.Authorization='Bearer '+this.token;if(this.csrf)headers['X-CSRF-Token']=this.csrf;
        const response=await fetch(this.base+'/bridge/events?subscription_id='+encodeURIComponent(this.sub.id),{headers,signal});
        if(response.status===404){this.running=false;this.controller.abort();this.onStatus('互动或订阅已结束，普通记录继续。');return}
        if(!response.ok)throw Error('订阅暂不可用');
        const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
        try{
          while(!signal.aborted){
            const {value,done}=await reader.read();if(done)break;
            buffer+=decoder.decode(value,{stream:true});buffer=buffer.replace(/\r\n/g,'\n');
            if(buffer.length>262144)throw Error('Event stream frame too large');
            let split;
            while((split=buffer.indexOf('\n\n'))>=0){
              const frame=buffer.slice(0,split);buffer=buffer.slice(split+2);
              if(frame.split('\n').includes('event: interaction')){
                const data=frame.split('\n').filter(s=>s.startsWith('data:')).map(s=>s.slice(5).trimStart()).join('\n');
                await this.handle(JSON.parse(data),signal);
              }
            }
          }
        }finally{await reader.cancel().catch(()=>{})}
      }catch(error){if(signal.aborted)return;this.onStatus(error.message+'；连接会自动恢复，事件按 ID 去重。')}
      if(!signal.aborted)await new Promise(resolve=>setTimeout(resolve,500));
    }
  }
  async stop() {
    this.running=false;this.controller?.abort();
    if(this.sub)await this.api('/bridge/unsubscribe',{subscription_id:this.sub.id});
    if(this.session)await this.tool('end_interaction',{session_id:this.session.id});
    this.sub=null;this.session=null;this.onStatus('已结束主动反馈，普通历史记录继续。');
  }
}
globalThis.DollBridgeClient=DollBridgeClient;
