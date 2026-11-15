const flights=new Map();
const delays=[2000,5000,10000,30000,60000];
function recover(key,operation){
  if(flights.has(key))return flights.get(key);
  const task=Promise.resolve().then(operation).finally(()=>flights.delete(key));flights.set(key,task);return task;
}
function delay(attempt){return delays[Math.min(Math.max(0,attempt),delays.length-1)];}
function failure(code,message){return Object.assign(Error(message),{code});}
function fatal(error){return ['device_identity_changed','direct_upload_enabled'].includes(error?.code);}
function retryable(error){
  if(error?.code==='device_restarted')return true;
  const message=String(error?.message||error);
  return !fatal(error)&&/offline|unreachable|network|timeout|timed out|ECONN|fetch failed|Socket|MCP HTTP (408|429|5\d\d)|设备.*(不可达|未连接|已重启)|暂未找到|连接.*超时|网络|超时|Collector offline|Archive (occupied|lease)|归档租约/.test(message);
}
exports.recover=recover;exports.delay=delay;exports.fatal=fatal;exports.retryable=retryable;
exports.failure=failure;
