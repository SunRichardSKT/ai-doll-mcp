"""Official MCP SDK transport checks against isolated archives, not real hardware."""
import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from companion_experience import TOOLS
from test_chat_gateway import ChatGatewayTests
from test_direct_mcp import DirectMCPTests
from test_companion_experience import ExperienceTests
from chat_mcp_gateway import create_gateway


async def exercise(client):
    listing = await client.list_tools()
    tools = {t.name:t for t in listing.tools}
    assert set(TOOLS) <= set(tools)
    assert not tools['update_body_part'].annotations.readOnlyHint
    assert tools['get_chat_context'].annotations.readOnlyHint
    async def call(name,args=None):
        reply=await client.call_tool(name,args or {})
        assert not reply.isError,reply.content
        return reply.structuredContent or json.loads(reply.content[0].text)
    await call('get_settings_entry',{'section':'feedback'})
    await call('get_device_overview')
    await call('update_body_part',{'channel':0,'changes':{'aliases':['脑袋'],'feedback_level':'light'}})
    await call('update_companion_preferences',{'changes':{'feedback':{'preferred_address':'朋友'}}})
    ctx=await call('get_chat_context',{'chat_id':'sdk-chat'})
    assert ctx['events'] and ctx['receipt_id']
    assert ctx['persona_priority']=='current_chat'
    bad=await client.call_tool('acknowledge_chat_context',{'chat_id':'other','receipt_id':ctx['receipt_id']})
    assert bad.isError
    await call('acknowledge_chat_context',{'chat_id':'sdk-chat','receipt_id':ctx['receipt_id']})
    assert not (await call('get_chat_context',{'chat_id':'sdk-chat'}))['events']
    await call('update_companion_preferences',{'changes':{'persona_source':'doll','doll_persona':'SDK保存的角色'}})
    assert (await call('get_chat_context',{'chat_id':'sdk-chat'}))['persona_priority']=='saved_doll'
    if 'set_channel_state' in tools:
        assert len(tools)==52
        assert tools['set_channel_state'].annotations.readOnlyHint is False
        result=await call('set_channel_state',{'channel':0,'mode':'off'})
        assert result['channels'][0]['mode']=='off'


class LocalSDKTests(ChatGatewayTests):
    async def test_new_tools_through_http_sdk(self):
        fixture=ExperienceTests();fixture.setUp();fixture.event(1)
        try:
            with patch('companion_mcp.call',side_effect=fixture.c.call):
                gateway=create_gateway('interaction',folder=fixture.temp.name)
                async with self.connect(gateway) as (client,_):await exercise(client)
        finally:fixture.tearDown()

    async def test_stdio_new_tools(self):
        parameters=StdioServerParameters(command=sys.executable,args=['-X','utf8',str(Path(__file__).resolve()),'--stdio-fixture'])
        async with stdio_client(parameters) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize();await exercise(client)


class DirectExperienceSDKTests(DirectMCPTests):
    async def test_new_tools_on_linux_transport_and_read_only_profiles(self):
        self.app.receive(self.pair['device_token'],__import__('test_direct_server').packet(1))
        async with __import__('mcp.client.streamable_http',fromlist=['streamable_http_client']).streamable_http_client(self.url) as (read,write,_):
            async with ClientSession(read,write) as client:
                await client.initialize();await exercise(client)


if __name__=='__main__':
    if '--stdio-fixture' in sys.argv:
        fixture=ExperienceTests();fixture.setUp();fixture.event(1)
        fixture.port_states=True
        for ch in fixture.channels:ch['mode']='connected'
        fixture.save_config()
        import companion_mcp
        companion_mcp.call=fixture.c.call
        try:companion_mcp.mcp.run()
        finally:fixture.tearDown()
    else:unittest.main()
