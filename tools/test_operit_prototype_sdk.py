"""Declared MCP SDK and real Node HTTP against a private isolated archive."""
import asyncio
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from remote_mcp import create_private_remote
from operit_demo import DemoBackend


class OperitPrototypeSDKTests(unittest.IsolatedAsyncioTestCase):
    async def test_workflow_against_real_mcp_transport_and_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            demo=DemoBackend(Path(folder)/'demo',delay=.1)
            try:
              with patch('companion_mcp.call',side_effect=demo.call):
                sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
                _,app,store=create_private_remote(folder,port=port)
                url=store.local_url('127.0.0.1',port)
                server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='critical',access_log=False))
                thread=threading.Thread(target=server.run,daemon=True);thread.start()
                try:
                    for _ in range(100):
                        if server.started:break
                        await asyncio.sleep(.05)
                    self.assertTrue(server.started)
                    async with streamable_http_client(url) as (read,write,_):
                        async with ClientSession(read,write) as sdk:
                            await sdk.initialize()
                            self.assertEqual(len((await sdk.list_tools()).tools),19)
                    # JS requires an Android-style absolute path; Windows temp paths
                    # are supplied as /C:/... and translated only by the test runner.
                    state_path=Path(folder)/'host-state.json'
                    runner=Path(__file__).with_name('operit_prototype_sdk_runner.cjs')
                    process=await asyncio.to_thread(subprocess.run,
                        ['node',str(runner),url,state_path.as_posix()],capture_output=True,text=True,timeout=25,
                        encoding='utf-8')
                    self.assertEqual(process.returncode,0,process.stdout+process.stderr)
                    self.assertIsNone(demo.c.active())
                    self.assertFalse(demo.c.experience.context('operit-sdk-chat')['events'])
                    self.assertTrue(demo.c.experience.context('another-chat')['events'])
                    calls=[json.loads(line) for line in (Path(folder)/'calls.jsonl').read_text().splitlines()]
                    self.assertTrue(any(c['tool']=='acknowledge_chat_context' and c['completed'] for c in calls))
                finally:
                    server.should_exit=True
                    await asyncio.to_thread(thread.join,10)
                    self.assertFalse(thread.is_alive())
            finally:demo.close()


if __name__=='__main__':unittest.main()
