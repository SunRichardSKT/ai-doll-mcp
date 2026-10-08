"""Real ESP32 + collector + official MCP stdio client end-to-end test."""
import asyncio
import datetime
import json
import pathlib
import site
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SDK = ROOT/'.tools/mcp-test-sdk'
sys.path.insert(0, str(SDK)); site.addsitedir(str(SDK))
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    checks = []
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT/'tools/companion_mcp.py')])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=datetime.timedelta(seconds=50)) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) == 33
            checks.append('official SDK handshake and 33 tools')

            async def call(name, args=None, error=False):
                reply = await session.call_tool(name, args or {})
                if error:
                    assert reply.isError
                    return
                assert not reply.isError, reply
                return json.loads(reply.content[0].text)

            status = await call('doll_get_status')
            assert status['firmware'] == 'doll-lab-2.3.0'
            assert not (await call('get_interaction_status'))['active_session'], 'End your active session before running tests'
            assert not (await call('get_sensor_config'))['enabled']
            await call('set_sensor_config', {'enabled': False, 'press_threshold': 100, 'release_threshold': 200}, error=True)
            original = await call('get_body_map')
            persona = await call('get_persona')
            sid = None
            try:
                parts = [{'channel': i, 'name': '测试部位'+str(i)} for i in range(8)]
                assert (await call('set_body_map', {'parts': parts}))['parts'] == parts
                checks.append('device body map write/read')
                edge = [dict(p) for p in parts]; edge[0]['name'] += 'x'
                assert (await call('set_body_map', {'parts': edge}))['parts'] == edge
                assert (await call('get_body_map'))['parts'] == edge
                await call('set_body_map', {'parts': parts})
                checks.append('USB 64-byte boundary and Chinese response regression')
                await call('set_body_map', {'parts': [parts[0]]*8}, error=True)
                await call('doll_simulate_press', {'channel': 8, 'value': 1000}, error=True)
                checks.append('invalid channel and duplicate map rejected')
                await call('set_persona', {'persona': '测试人设：温柔，依据记录回答，不编造拥抱。'})
                await call('doll_simulate_press', {'channel': 0, 'value': 1700})
                await call('doll_simulate_press', {'channel': 0, 'value': 0})
                before = await call('query_touch_history', {'body_part': '测试部位0'})
                assert before['touches'][-1]['session_id'] is None
                assert '测试人设' in before['persona']
                checks.append('normal touch recorded without session; persona included')
                s = await call('start_interaction', {'chat_id': 'hardware-test'})
                sid = s['id']
                assert (await call('start_interaction', {'chat_id': 'hardware-test'}))['id'] == sid
                await call('start_interaction', {'chat_id': 'other-chat'}, error=True)
                assert not (await call('get_interaction_events', {'session_id': sid}))['touches']
                checks.append('session ownership/idempotency and old-event exclusion')
                await call('doll_simulate_press', {'channel': 1, 'value': 3200})
                await call('doll_simulate_press', {'channel': 2, 'value': 1500})
                parts[1]['name'] = '测试改名后'
                await call('set_body_map', {'parts': parts})
                events = await call('get_interaction_events', {'session_id': sid})
                assert len(events['touches']) == 2
                assert events['touches'][0]['body_part'] == '测试部位1'
                assert all(e['source'] == 'simulation' for e in events['touches'])
                after = events['next_cursor']
                assert not (await call('get_interaction_events', {'session_id': sid, 'after': after}))['touches']
                page = await call('get_interaction_events', {'session_id': sid, 'limit': 1})
                assert page['has_more']
                assert len((await call('get_interaction_events', {'session_id': sid, 'after': page['next_cursor']}))['touches']) == 1
                checks.append('two simultaneous channels; label snapshot; cursor dedup and pagination')
                await asyncio.sleep(5.5)
                ended = await call('get_interaction_events', {'session_id': sid})
                assert all(e['duration_ms'] is not None and e['duration_ms'] >= 4900 for e in ended['touches'])
                checks.append('automatic release duration archived')
                await call('end_interaction', {'session_id': sid})
                await call('doll_simulate_press', {'channel': 3, 'value': 1200})
                await call('doll_simulate_press', {'channel': 3, 'value': 0})
                after_end = await call('query_touch_history', {'body_part': '测试部位3'})
                assert after_end['touches'][-1]['session_id'] is None
                checks.append('after session ends, touches return to ordinary history')
            finally:
                if sid:
                    await call('end_interaction', {'session_id': sid})
                await call('set_body_map', original)
                await call('set_persona', persona)
                await call('doll_set_led', {'on': False})
    report = {'passed': True, 'firmware': status['firmware'], 'tested_at': datetime.datetime.now().astimezone().isoformat(), 'checks': checks}
    (ROOT/'build/device-lab/companion-device-test.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    asyncio.run(main())
