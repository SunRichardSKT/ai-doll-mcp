"""Actual Streamable HTTP SDK checks against the push archive, not a PC collector."""
import asyncio
import json
import socket
import tempfile
import time
import unittest

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from direct_server import DirectServer
from direct_mcp import start_mcp, PROFILES
from test_direct_server import packet


class DirectMCPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = DirectServer(self.tmp.name)
        self.pair = self.app.pair('测试娃娃')
        self.app.receive(self.pair['device_token'], packet())
        sock = socket.socket(); sock.bind(('127.0.0.1', 0))
        self.port = sock.getsockname()[1]; sock.close()
        self.server, self.thread = start_mcp(self.app, port=self.port)
        self.url = self.app.mcp_connection(self.pair['id'])

    async def asyncTearDown(self):
        self.app.stop.set(); self.server.should_exit = True
        await asyncio.to_thread(self.thread.join, 10)
        self.assertFalse(self.thread.is_alive())
        self.app.close(); self.tmp.cleanup()

    async def call(self, session, name, arguments=None):
        result = await session.call_tool(name, arguments or {})
        self.assertFalse(result.isError, result.content)
        data = result.structuredContent
        return data if data is not None else json.loads(result.content[0].text)

    async def test_sdk_tools_history_offline_restart_and_session_isolation(self):
        async with streamable_http_client(self.url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {tool.name for tool in (await session.list_tools()).tools}
                self.assertEqual(names, set(PROFILES['interaction']))
                a = await self.call(session, 'get_installation_status')
                self.assertEqual(a['server_instance_id'], self.app.server_instance_id)
                self.assertEqual(a['pairing_id'], self.pair['id'])
                b = await self.call(session, 'doll_get_status')
                self.assertNotEqual(a['verification']['call_id'], b['verification']['call_id'])
                self.assertTrue(b['online'])
                channels = await self.call(session, 'get_channel_config')
                self.assertEqual(channels['channels'][0]['name'], '头')
                self.assertEqual(channels['configuration_source'], 'server_sqlite')
                started = await self.call(session, 'start_interaction', {'chat_id':'chat-a','duration_sec':60})
                self.app.receive(self.pair['device_token'], packet(1))
                values = {'chat_id':'chat-a','session_id':started['id'],'wait_seconds':0}
                events = await self.call(session, 'get_interaction_device_events', values)
                self.assertEqual(len(events['events']), 1)
                self.assertEqual(events['events'][0]['source'], 'simulation')
                repeated = await self.call(session, 'get_interaction_device_events', dict(values, after=events['next_cursor']))
                self.assertEqual(repeated['events'], [])
                bad = await session.call_tool('end_interaction', {'chat_id':'chat-b','session_id':started['id']})
                self.assertTrue(bad.isError)
                negative = await session.call_tool('get_interaction_device_events', dict(values, wait_seconds=21))
                self.assertTrue(negative.isError)
                await self.call(session, 'end_interaction', {'chat_id':'chat-a','session_id':started['id']})
                ended = await self.call(session, 'get_interaction_device_events', values)
                self.assertTrue(ended['session_closed']); self.assertEqual(ended['events'], [])
                self.app.resolve(self.pair['id']).c.last_sync = time.time()-30
                history = await self.call(session, 'query_device_history')
                self.assertEqual(len(history['events']), 1)
                self.assertEqual(history['history_source'], 'server_sqlite')
                self.assertEqual(history['collector_error'], 'device_offline')
                await self.call(session, 'summarize_interactions')
                await self.call(session, 'get_history_statistics')
                await self.call(session, 'get_persona')
                await self.call(session, 'get_feedback_preferences')
                await self.call(session, 'get_channel_capabilities')
        token = self.app.mcp_token
        self.app.close()
        self.app = DirectServer(self.tmp.name)
        self.assertEqual(token, self.app.mcp_token)
        self.assertEqual(len(self.app.resolve(self.pair['id']).c.device_history()['events']), 1)
        # The running endpoint still holds the old app: restart it too.
        self.server.should_exit = True
        await asyncio.to_thread(self.thread.join, 10)
        self.server, self.thread = start_mcp(self.app, port=self.port)
        self.assertEqual(self.url, self.app.mcp_connection(self.pair['id']))
        async with streamable_http_client(self.url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self.assertEqual(len((await self.call(session, 'query_device_history'))['events']), 1)

    async def test_invalid_url_origin_revocation_and_bearer(self):
        async with httpx.AsyncClient() as client:
            for url in (self.url.replace(self.app.mcp_token, '0'*64),
                        f'http://127.0.0.1:{self.port}/mcp'):
                self.assertEqual((await client.post(url,json={})).status_code,404)
            self.assertEqual((await client.post(self.url,json={},headers={'Origin':'https://other.example'})).status_code,404)
        bearer_url = f'http://127.0.0.1:{self.port}/d/{self.pair["id"]}/mcp'
        async with httpx.AsyncClient(headers={'Authorization':'Bearer '+self.app.mcp_token}) as client:
            async with streamable_http_client(bearer_url, http_client=client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self.assertTrue((await self.call(session,'doll_get_status'))['online'])
        with self.app.lock, self.app.db:
            self.app.db.execute('UPDATE devices SET revoked=1')
        async with httpx.AsyncClient() as client:
            self.assertEqual((await client.post(self.url,json={})).status_code,404)

    async def test_profile_and_expiry(self):
        self.server.should_exit = True
        await asyncio.to_thread(self.thread.join,10)
        self.server,self.thread = start_mcp(self.app,port=self.port,profile='history')
        async with streamable_http_client(self.url) as (read,write,_):
            async with ClientSession(read,write) as session:
                await session.initialize()
                self.assertEqual({t.name for t in (await session.list_tools()).tools},set(PROFILES['history']))
                self.assertTrue((await session.call_tool('start_interaction',{'chat_id':'a'})).isError)
        self.server.should_exit = True
        await asyncio.to_thread(self.thread.join,10)
        self.server,self.thread = start_mcp(self.app,port=self.port)
        async with streamable_http_client(self.url) as (read,write,_):
            async with ClientSession(read,write) as session:
                await session.initialize()
                started=await self.call(session,'start_interaction',{'chat_id':'expiry','duration_sec':1})
                result=await self.call(session,'get_interaction_device_events',{'chat_id':'expiry','session_id':started['id'],'wait_seconds':2})
                self.assertTrue(result['session_closed'])
                self.assertEqual(result['session']['reason'],'duration_expired')


if __name__ == '__main__':
    unittest.main()
