"""Validate the unified phone modules over the declared MCP SDK, not old wheels."""
import asyncio
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from operit_demo import DemoBackend
from remote_mcp import create_private_remote
from operit_service import lan_addresses


class UnifiedSDKTests(unittest.IsolatedAsyncioTestCase):
    async def test_unified_configuration_probe_and_simulated_touch(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            demo = DemoBackend(folder / 'demo', delay=.1)
            try:
                with patch('companion_mcp.call', side_effect=demo.call):
                    with socket.socket() as sock:
                        host = next(iter(lan_addresses()), '127.0.0.1')
                        sock.bind((host, 0))
                        port = sock.getsockname()[1]
                    _, app, store = create_private_remote(folder / 'mcp', port=port, listen_host=host)
                    url = store.local_url(host, port)
                    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port,
                                                          log_level='critical', access_log=False))
                    thread = threading.Thread(target=server.run, daemon=True)
                    thread.start()
                    try:
                        for _ in range(100):
                            if server.started:
                                break
                            await asyncio.sleep(.05)
                        self.assertTrue(server.started)
                        async with streamable_http_client(url) as (reader, writer, _):
                            async with ClientSession(reader, writer) as sdk:
                                await sdk.initialize()
                                self.assertEqual(len((await sdk.list_tools()).tools), 19)
                        process = await asyncio.to_thread(subprocess.run, [
                            'node', str(Path(__file__).with_name('operit_unified_sdk_runner.cjs')), url],
                            capture_output=True, text=True, encoding='utf-8', timeout=25)
                        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                        self.assertIsNone(demo.c.active())
                        self.assertFalse(demo.c.experience.context('operit-sdk-chat')['events'])
                        self.assertTrue(demo.c.experience.context('other-chat')['events'])
                        records = [json.loads(line) for line in (folder / 'mcp/calls.jsonl').read_text().splitlines()]
                        self.assertTrue(any(row['tool'] == 'acknowledge_chat_context' and row['completed'] for row in records))
                    finally:
                        server.should_exit = True
                        await asyncio.to_thread(thread.join, 10)
            finally:
                demo.close()


if __name__ == '__main__':
    unittest.main()
