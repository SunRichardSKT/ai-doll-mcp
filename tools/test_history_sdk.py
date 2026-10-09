"""Read-only owner archive acceptance with the official MCP client; never deletes."""
import asyncio
import datetime
import json
import pathlib
import site
import sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
SDK=ROOT/'.tools/mcp-test-sdk'
if SDK.exists():sys.path.insert(0,str(SDK));site.addsitedir(str(SDK))
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    checks=[]
    async with stdio_client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'tools/companion_mcp.py')])) as (r,w):
        async with ClientSession(r,w) as client:
            await client.initialize();tools={t.name:t for t in (await client.list_tools()).tools}
            assert len(tools)==45
            for name in ('export_history','get_history_statistics','preview_history_deletion','get_history_retention','preview_history_retention'):
                assert tools[name].annotations.readOnlyHint and not tools[name].annotations.destructiveHint
            for name in ('delete_history','set_history_retention'):
                assert tools[name].annotations.destructiveHint and not tools[name].annotations.readOnlyHint
            checks.append('Official SDK discovers 45 tools and correct history read/destructive annotations')
            async def call(name,args=None):
                result=await client.call_tool(name,args or {});assert not result.isError,name
                return json.loads(result.content[0].text)
            policy=await call('get_history_retention');assert policy['enabled'] is False
            status=await call('get_installation_status',dict(client_kind='stdio'))
            assert status['bridge']=='doll-bridge-2.12.1' and status['runtime']['tool_count']==45
            assert status['runtime']['transport']=='wifi' and status['device']['firmware']=='doll-lab-2.7.0'
            first=await call('export_history',dict(filters=dict(source='simulation',time_scope='all'),limit=2))
            assert first['count']<=2 and first['format']=='json'
            if first['has_more']:
                second=await call('export_history',dict(filters=dict(source='simulation',time_scope='all'),limit=2,
                    after=first['next_cursor'],max_id=first['max_id']))
                assert not set(e['id'] for e in first['records'])&set(e['id'] for e in second['records'])
                assert second['max_id']==first['max_id']
            csv=await call('export_history',dict(filters=dict(source='simulation'),format='csv',limit=1))
            assert csv['content'].startswith('id,device,boot_id') and csv['spreadsheet_text_escaped']
            summary=await call('get_history_statistics',dict(filters=dict(source='simulation')))
            assert summary['events']>=first['count'] and summary['unknown_time_events']>=0
            checks.append('Existing owner simulation archive is readable as paginated JSON/CSV and whole-scope statistics over Wi-Fi')
            preview=await call('preview_history_retention',dict(days=90,include_unknown=False))
            assert 'counts' in preview and (await call('get_history_retention'))==policy
            checks.append('Retention preview is read-only; owner policy remains disabled')
            assert not (await call('get_interaction_status'))['active_session']
    report=dict(passed=True,at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        bridge='2.12.1',firmware='2.7.0',checks=checks,owner_history_deleted=False,retention_enabled=False,
        limits=['Actual deletion/retention tested only against disposable archives; existing owner history preserved.',
                'Physical sensors, battery/power-failure and user model generation not tested.'])
    (ROOT/'build/device-lab/history-sdk-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':asyncio.run(main())
