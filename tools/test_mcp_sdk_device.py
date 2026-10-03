"""Interoperability test with the official MCP Python client, over real Wi-Fi HTTP."""
import sys,pathlib,json,asyncio,datetime,site
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.tools/mcp-test-sdk'))
site.addsitedir(str(ROOT/'.tools/mcp-test-sdk'))
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main(host):
    work=ROOT/'build/device-lab';cfg=json.loads((work/'device-private.json').read_text(encoding='utf-8'))
    async with httpx.AsyncClient(headers={'Authorization':'Bearer '+cfg['mcp_token']},trust_env=False,timeout=15) as client:
        async with streamable_http_client('http://'+host+'/mcp',http_client=client) as (read,write,_):
            async with ClientSession(read,write,read_timeout_seconds=datetime.timedelta(seconds=15)) as session:
                initialized=await session.initialize();listed=await session.list_tools()
                assert {"doll_get_status","doll_set_led","doll_simulate_press"}.issubset({t.name for t in listed.tools})
                replies=[]
                for name,args in [('doll_get_status',{}),('doll_set_led',{'on':True}),('doll_set_led',{'on':False}),('doll_simulate_press',{'channel':0,'value':1800})]:
                    r=await session.call_tool(name,args);assert not r.isError
                    data=json.loads(r.content[0].text)
                    if name=='doll_set_led':assert data['led_gpio_level']==(0 if args['on'] else 1)
                    replies.append(dict(tool=name,arguments=args,result=data))
                report=dict(passed=True,sdk='mcp 1.30.0',host=host,negotiated=initialized.protocolVersion,tools=[t.name for t in listed.tools],replies=replies)
                (work/'official-sdk-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');asyncio.run(main(sys.argv[1]))
