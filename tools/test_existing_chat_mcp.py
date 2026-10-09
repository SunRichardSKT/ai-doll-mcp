"""The SDK exposes existing-conversation guidance without starting a new chat or calling models."""
import asyncio
import unittest
from unittest.mock import patch
import companion_mcp


class ExistingChatTests(unittest.TestCase):
    def test_sdk_prompt_and_tools(self):
        async def check():
            with patch.object(companion_mcp,'call',side_effect=AssertionError('Prompt contacted device')):
                prompts=await companion_mcp.mcp.list_prompts()
                self.assertIn('doll_chat_companion',{p.name for p in prompts})
                result=await companion_mcp.mcp.get_prompt('doll_chat_companion',{})
            text='\n'.join(m.content.text for m in result.messages)
            tools={t.name for t in await companion_mcp.mcp.list_tools()}
            self.assertEqual(len(tools),45)
            for name in ('start_interaction','get_interaction_device_events','end_interaction',
                         'get_installation_status','get_persona','get_feedback_preferences'):
                self.assertIn(name,tools)
                self.assertIn(name,text)
            for phrase in ('当前对话','next_cursor','单次最多 20 秒','不能单独唤醒',
                           '不模拟键盘发送','不新建聊天产品','simulation'):
                self.assertIn(phrase,text)
        asyncio.run(check())


if __name__=='__main__':unittest.main()
