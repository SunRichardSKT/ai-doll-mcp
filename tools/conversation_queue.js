/* Share this queue with the host application's ordinary message handler.
 * It serializes work for an existing chat; it does not own models or messages. */
class DollConversationQueue {
  constructor({maxPending=64}={}) {
    if(!Number.isInteger(maxPending)||maxPending<1||maxPending>512)throw Error('maxPending must be 1..512');
    this.maxPending=maxPending;this.chats=new Map();
  }
  run(chatId,operation,{signal}={}) {
    if(typeof chatId!=='string'||!chatId.trim()||chatId.length>256)throw Error('Stable chatId required');
    if(typeof operation!=='function')throw Error('operation callback required');
    if(signal?.aborted)return Promise.reject(this.abortError());
    let queue=this.chats.get(chatId);
    if(!queue){queue={items:[],running:false};this.chats.set(chatId,queue)}
    if(queue.items.length+Number(queue.running)>=this.maxPending)return Promise.reject(Error('Conversation queue is full'));
    return new Promise((resolve,reject)=>{
      const task={operation,signal,resolve,reject,started:false};
      task.abort=()=>{
        if(task.started)return; // Active work must settle before another task can enter.
        const index=queue.items.indexOf(task);if(index<0)return;
        queue.items.splice(index,1);signal.removeEventListener('abort',task.abort);
        reject(this.abortError());this.cleanup(chatId,queue);
      };
      queue.items.push(task);signal?.addEventListener('abort',task.abort,{once:true});
      this.drain(chatId,queue);
    });
  }
  abortError(){const error=Error('Conversation task cancelled');error.name='AbortError';return error}
  cleanup(chatId,queue){if(!queue.running&&!queue.items.length&&this.chats.get(chatId)===queue)this.chats.delete(chatId)}
  drain(chatId,queue) {
    if(queue.running)return;
    const task=queue.items.shift();if(!task){this.cleanup(chatId,queue);return}
    queue.running=true;task.started=true;
    Promise.resolve().then(()=>{
      if(task.signal?.aborted)throw this.abortError();
      return task.operation({signal:task.signal});
    }).then(task.resolve,task.reject).finally(()=>{
      task.signal?.removeEventListener('abort',task.abort);queue.running=false;this.drain(chatId,queue);
    });
  }
  pending(chatId){const queue=this.chats.get(chatId);return queue?queue.items.length+Number(queue.running):0}
}
globalThis.DollConversationQueue=DollConversationQueue;
