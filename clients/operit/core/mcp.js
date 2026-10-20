// Shared HTTP transport. Credentials stay in private phone settings, never in
// workflow parameters, prompts or returned diagnostics.
let requestId=0;
async function connect(url,token) {
  async function rpc(method,params,version) {
    const id=method==='notifications/initialized'?undefined:++requestId;
    const response=await Tools.Net.http({url,method:'POST',follow_redirects:false,ignore_ssl:false,
      headers:{'Content-Type':'application/json',Accept:'application/json, text/event-stream',
        ...(token?{Authorization:'Bearer '+token}:{}),...(version?{'MCP-Protocol-Version':version}:{})},
      body:JSON.stringify({jsonrpc:'2.0',...(id===undefined?{}:{id}),method,params}),
      connect_timeout:10000,read_timeout:30000});
    if(response.statusCode<200||response.statusCode>=300)throw Error('MCP HTTP '+response.statusCode+'，请检查连接地址、网络和设备 MCP 开关。');
    if(id===undefined)return null;
    const body=JSON.parse(response.content);
    if(body.id!==id||body.error||body.result?.isError)throw Error('MCP 调用未完成，请检查连接状态。');
    return body.result;
  }
  const hello=await rpc('initialize',{protocolVersion:'2025-11-25',capabilities:{},
    clientInfo:{name:'ai-doll-operit',version:'2.21.0'}});
  if(!hello?.protocolVersion)throw Error('MCP 未返回协议版本。');
  await rpc('notifications/initialized',{},hello.protocolVersion);
  return async(name,args={})=>{
    const reply=await rpc('tools/call',{name,arguments:args},hello.protocolVersion);
    if(reply.structuredContent)return reply.structuredContent;
    const content=reply.content?.find(x=>x.type==='text');
    if(!content)throw Error('MCP 没有返回可读数据。');
    return JSON.parse(content.text);
  };
}
exports.connect=connect;
