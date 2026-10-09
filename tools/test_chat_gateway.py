"""Protocol and concurrency checks with explicit collector fixtures, no hardware."""
import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from chat_mcp_gateway import create_gateway, INTERACTION_TOOLS, STATUS_TOOLS
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import httpx


class ChatGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_origin_accepts_only_exact_status_host(self):
        with tempfile.TemporaryDirectory() as folder, patch('companion_mcp.call', return_value={'device_id': 'fixture'}):
            with self.assertRaises(ValueError):
                create_gateway('interaction', folder=folder, public_origin='https://fixture.example')
            for invalid in ('http://fixture.example', 'https://*.example', 'https://fixture.example/mcp',
                            'https://user:password@fixture.example', 'https://fixture.example?key=value'):
                with self.assertRaises(ValueError):
                    create_gateway(folder=folder, public_origin=invalid)
            gateway = create_gateway(folder=folder, public_origin='https://fixture.example:18443')
            async with self.connect(gateway) as (client, http):
                response = await http.post('/mcp', json={'jsonrpc': '2.0', 'id': 9, 'method': 'tools/list'},
                    headers={'host': 'fixture.example:18443', 'accept': 'application/json, text/event-stream'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual({tool['name'] for tool in response.json()['result']['tools']}, set(STATUS_TOOLS))
                rejected = await http.post('/mcp', json={}, headers={'host': 'fixture.example:18444'})
                self.assertEqual(rejected.status_code, 421)

    @asynccontextmanager
    async def connect(self, gateway):
        app = gateway.streamable_http_app()
        async with gateway.session_manager.run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                        base_url='http://127.0.0.1:8771') as http:
                async with streamable_http_client('http://127.0.0.1:8771/mcp', http_client=http) as (read, write, _):
                    async with ClientSession(read, write) as client:
                        await client.initialize()
                        yield client, http

    async def test_status_profile_filters_private_fields_and_audits_actual_calls(self):
        sentinel = 'PRIVATE-FIXTURE-TOKEN-HISTORY'
        device = dict(device_id='fixture', firmware='fixture', wifi_connected=True,
                      sensor_mode='simulation', physical_outputs_enabled=False,
                      token=sentinel, ssid=sentinel, ip=sentinel, history=[sentinel])
        def backend(name, args):
            if name == 'doll_get_status':
                return device
            return dict(device=device, bridge='fixture', python='fixture', database_open=True,
                        runtime={'transport': 'wifi', 'tool_count': 45, 'private': sentinel},
                        persona=sentinel, device_error=sentinel, collector_error=sentinel)
        with tempfile.TemporaryDirectory() as folder, patch('companion_mcp.call', side_effect=backend):
            gateway = create_gateway(folder=folder)
            async with self.connect(gateway) as (client, http):
                tools = await client.list_tools()
                self.assertEqual({tool.name for tool in tools.tools}, set(STATUS_TOOLS))
                self.assertTrue(all(tool.annotations.readOnlyHint for tool in tools.tools))
                responses = [await client.call_tool(name, {}) for name in STATUS_TOOLS]
                self.assertTrue(all(not result.isError for result in responses))
                payloads = [result.structuredContent for result in responses]
                self.assertNotIn(sentinel, json.dumps(payloads))
                self.assertEqual(payloads[0]['device_error'], 'Device status unavailable')
                self.assertTrue((await client.call_tool('set_input_enabled', {'enabled': True})).isError)
                self.assertTrue((await client.call_tool('get_persona', {})).isError)
                denied = await http.post('/mcp', json={}, headers={'host': 'untrusted.example'})
                self.assertEqual(denied.status_code, 421)
            logs = [json.loads(line) for line in (Path(folder) / 'calls.jsonl').read_text().splitlines()]
            ids = {value['verification']['call_id'] for value in payloads}
            self.assertEqual(len(ids), 2)
            self.assertEqual(ids, {entry['call_id'] for entry in logs})
            self.assertTrue(all(entry['completed'] for entry in logs))
            self.assertNotIn(sentinel, (Path(folder) / 'calls.jsonl').read_text())

    async def test_interaction_profile_uses_existing_tools_with_typed_filters(self):
        calls = []
        def backend(name, args):
            calls.append((name, args))
            return {'fixture': True, 'id': 'fixture-session'}
        with tempfile.TemporaryDirectory() as folder, patch('companion_mcp.call', side_effect=backend):
            gateway = create_gateway('interaction', folder=folder)
            async with self.connect(gateway) as (client, _):
                tools = await client.list_tools()
                self.assertEqual({tool.name for tool in tools.tools}, set(INTERACTION_TOOLS))
                self.assertEqual(len(tools.tools), 13)
                self.assertTrue((await client.call_tool('start_interaction', {})).isError)
                self.assertTrue((await client.call_tool('start_interaction', {'chat_id': 'main'})).isError)
                self.assertEqual(calls, [])
                start = await client.call_tool('start_interaction', {'chat_id': 'fixture-chat'})
                self.assertFalse(start.isError)
                filters = await client.call_tool('get_history_statistics', {'filters': {'source': 'simulation'}})
                self.assertFalse(filters.isError)
                self.assertEqual(calls[-1], ('get_history_statistics', {'filters': {'source': 'simulation', 'time_scope': 'all'}}))
                self.assertTrue((await client.call_tool('set_vibration', {'channel': 8, 'intensity': 20})).isError)
                self.assertTrue((await client.call_tool('doll_simulate_press', {'channel': 0, 'value': 1800})).isError)
                prompts = await client.list_prompts()
                self.assertEqual([p.name for p in prompts.prompts], ['doll_chat_companion'])
                prompt = await client.get_prompt('doll_chat_companion', {})
                self.assertIn('get_installation_status()', prompt.messages[0].content.text)

    async def test_wait_does_not_block_status_or_end_on_same_http_server(self):
        entered, release = threading.Event(), threading.Event()
        active = {'id': 'fixture-session'}
        def backend(name, args):
            if name == 'get_interaction_device_events':
                entered.set()
                if not release.wait(3):
                    raise AssertionError('Concurrent end call could not run')
                return {'events': [], 'next_cursor': 0}
            if name == 'get_interaction_status':
                return {'active_session': active}
            if name == 'end_interaction':
                active.clear()
                release.set()
                return {'ended': True}
            if name == 'doll_get_status':
                return {'device_id': 'fixture', 'sensor_mode': 'simulation'}
            raise AssertionError(name)
        with tempfile.TemporaryDirectory() as folder, patch('companion_mcp.call', side_effect=backend):
            gateway = create_gateway('interaction', folder=folder)
            async with self.connect(gateway) as (client, _):
                waiting = asyncio.create_task(client.call_tool('get_interaction_device_events',
                    {'session_id': 'fixture-session', 'wait_seconds': 20}))
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                    status = await asyncio.wait_for(client.call_tool('doll_get_status', {}), 1)
                    self.assertFalse(status.isError)
                    ended = await asyncio.wait_for(client.call_tool('end_interaction', {'session_id': 'fixture-session'}), 1)
                    self.assertFalse(ended.isError)
                    events = await asyncio.wait_for(waiting, 2)
                    self.assertFalse(events.isError)
                finally:
                    release.set()
                    await asyncio.gather(waiting, return_exceptions=True)

    async def test_cancelled_clients_keep_capacity_until_issued_operations_finish(self):
        release = threading.Event()
        entered = 0
        lock = threading.Lock()
        def backend(name, args):
            nonlocal entered
            with lock:
                entered += 1
            release.wait(5)
            return {'device_id': 'fixture'}
        with tempfile.TemporaryDirectory() as folder, patch('companion_mcp.call', side_effect=backend):
            gateway = create_gateway(folder=folder)
            pending = [asyncio.create_task(gateway.call_tool('doll_get_status', {})) for _ in range(4)]
            try:
                for _ in range(100):
                    if entered == 4:
                        break
                    await asyncio.sleep(.01)
                self.assertEqual(entered, 4)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                with self.assertRaisesRegex(Exception, 'Local doll operation failed'):
                    await asyncio.wait_for(gateway.call_tool('doll_get_status', {}), 3)
                self.assertEqual(entered, 4, 'A fifth collector operation started after client cancellation')
            finally:
                release.set()
                await asyncio.gather(*pending, return_exceptions=True)
                await asyncio.sleep(.1)
            result = await gateway.call_tool('doll_get_status', {})
            self.assertTrue(result)
            records = [json.loads(line) for line in (Path(folder) / 'calls.jsonl').read_text().splitlines()]
            self.assertEqual(sum(bool(row.get('execution_may_continue')) for row in records), 4)
            self.assertEqual(sum(row['completed'] for row in records), 1)


if __name__ == '__main__':
    unittest.main()
