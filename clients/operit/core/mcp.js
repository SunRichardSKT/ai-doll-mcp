// Shared HTTP transport. Credentials stay in private phone settings, never in
// workflow parameters, prompts or returned diagnostics.
let requestId=0;
async function connect(url,token,options={}) {
  let limits=options;
  async function rpc(method,params,version) {
    const remaining=limits.deadline?limits.deadline-Date.now():Infinity;
    if(remaining<=0)throw Error('设备连接检查超时，请稍后重试或从热点获取地址。');
    const id=method==='notifications/initialized'?undefined:++requestId;
    const response=await Tools.Net.http({url,method:'POST',follow_redirects:false,ignore_ssl:false,
      headers:{'Content-Type':'application/json',Accept:'application/json, text/event-stream',
        ...(token?{Authorization:'Bearer '+token}:{}),...(version?{'MCP-Protocol-Version':version}:{})},
      body:JSON.stringify({jsonrpc:'2.0',...(id===undefined?{}:{id}),method,params}),
      connect_timeout:Math.min(limits.connect_timeout??10000,remaining),read_timeout:Math.min(limits.read_timeout??30000,remaining)});
    if(response.statusCode<200||response.statusCode>=300)throw Error('MCP HTTP '+response.statusCode+'，请检查连接地址、网络和设备 MCP 开关。');
    if(id===undefined)return null;
    const body=JSON.parse(response.content);
    if(body.id!==id)throw Error('MCP 返回编号不匹配，请检查连接状态。');
    if(body.error||body.result?.isError){
      const detail=body.error?.message||body.result?.content?.find(x=>x.type==='text')?.text;
      throw Error('MCP 调用未完成'+(detail?'：'+String(detail).slice(0,400):'，请检查连接状态。'));
    }
    return body.result;
  }
  const hello=await rpc('initialize',{protocolVersion:'2025-11-25',capabilities:{},
    clientInfo:{name:'ai-doll-operit',version:'2.25.1'}});
  if(!hello?.protocolVersion)throw Error('MCP 未返回协议版本。');
  await rpc('notifications/initialized',{},hello.protocolVersion);
  const call=async(name,args={})=>{
    const reply=await rpc('tools/call',{name,arguments:args},hello.protocolVersion);
    if(reply.structuredContent)return reply.structuredContent;
    const content=reply.content?.find(x=>x.type==='text');
    if(!content)throw Error('MCP 没有返回可读数据。');
    return JSON.parse(content.text);
  };
  call.setTimeouts=value=>{limits=value;};return call;
}
exports.connect=connect;
