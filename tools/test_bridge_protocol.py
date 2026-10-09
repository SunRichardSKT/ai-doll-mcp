"""Live local bridge protocol and official legacy SDK compatibility checks."""
import asyncio
import json
import pathlib
import site
import sys
import urllib.request
import urllib.error
import datetime as dt

ROOT=pathlib.Path(__file__).resolve().parents[1]
SDK=ROOT/'.tools/mcp-test-sdk'
if SDK.exists():sys.path.insert(0,str(SDK));site.addsitedir(str(SDK))
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

def main_http():
    token=json.loads((ROOT/'build/device-lab/companion-private.json').read_text(encoding='utf-8'))['token']
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    checks=[]
    def rpc(method,params=None,auth=True,header=None):
        args=dict(params or {})
        if method!='server/discover':args['_meta']={'io.modelcontextprotocol/protocolVersion':'2026-07-28'}
        headers={'Content-Type':'application/json'}
        if auth:headers['Authorization']='Bearer '+token
        if header:headers['MCP-Protocol-Version']=header
        req=urllib.request.Request('http://127.0.0.1:8768/bridge/mcp',data=json.dumps(dict(jsonrpc='2.0',id=1,method=method,params=args)).encode(),headers=headers)
        return json.load(opener.open(req,timeout=15))
    try:rpc('server/discover',auth=False);raise AssertionError('Missing token accepted')
    except urllib.error.HTTPError as ex:assert ex.code in (401,403)
    discover=rpc('server/discover')['result'];assert discover['supportedVersions']==['2026-07-28'] and 'events' in discover['capabilities']
    tools=rpc('tools/list')['result']['tools'];assert len(tools)==45
    status=rpc('tools/call',dict(name='doll_get_status',arguments={}))['result'];assert not status['isError']
    assert status['structuredContent']['firmware']=='doll-lab-2.7.0'
    assert rpc('tools/call',dict(name='doll_simulate_press',arguments=dict(channel='invalid',value=3200)))['result']['isError']
    assert rpc('events/list')['result']['events'][0]['name']=='doll.interaction'
    assert rpc('events/list',header='2025-11-25')['error']['code']==-32020
    invalid=dict(name='doll.interaction',arguments=dict(device_id=status['structuredContent']['device_id'],session_id='missing'),delivery=dict(mode='webhook',url='https://127.0.0.1/private',secret='fake'))
    assert rpc('events/subscribe',invalid)['error']['code']==-32602
    checks.extend(['Bearer required for native MCP endpoint','MCP 2.0 discovery, 45 tools and events catalog','Typed tool schema validation','Protocol metadata/header mismatch rejected','Private callback rejected before network access'])
    return checks

async def main():
    checks=main_http()
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'tools/companion_mcp.py')])
    async with stdio_client(params) as (r,w):
        async with ClientSession(r,w) as session:
            await session.initialize();listed=await session.list_tools();assert len(listed.tools)==45
            for name in ['get_feedback_preferences','get_reply_bridge_status','doll_get_status']:
                result=await session.call_tool(name);assert not result.isError
            checks.append('Official SDK legacy STDIO handshake, 45 tools and bridge preference/status calls')
    report=dict(passed=True,at=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),bridge='2.12.2',firmware='2.7.0',checks=checks,
                not_tested=['Remote ChatGPT Work subscription','User model API call','Real motor or sensor input'])
    (ROOT/'build/device-lab/bridge-protocol-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');asyncio.run(main())
