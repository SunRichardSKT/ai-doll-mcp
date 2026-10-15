"""Real receiver HTTP, declared MCP SDK and unified phone modules; synthetic device uploads."""
import asyncio
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import unittest

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from direct_server import DirectServer, DirectHTTPServer, handler_for
from direct_mcp import start_mcp
from test_direct_server import packet


class OperitServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_phone_download_import_push_and_original_chat(self):
        with tempfile.TemporaryDirectory() as folder:
            app=DirectServer(folder)
            pairing=app.pair('手机服务器测试')
            app.receive(pairing['device_token'],packet())
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            # Local SDK fixture only; production installer supplies its HTTPS origin.
            app.public_url='http://127.0.0.1:'+str(port)
            server,worker=start_mcp(app,port=port)
            httpd=DirectHTTPServer(('127.0.0.1',0),handler_for(app))
            thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(httpd.server_port)
            try:
                async with httpx.AsyncClient(trust_env=False) as client:
                    route='/d/'+pairing['id']+'/operit-connection.json'
                    self.assertEqual((await client.get(base+route)).status_code,401)
                    self.assertEqual((await client.get(base+'/api/operit/toolpkg')).status_code,401)
                    client.headers['Authorization']='Bearer '+app.admin_token
                    result=await client.get(base+route);self.assertEqual(result.status_code,200)
                    self.assertIn('attachment',result.headers['content-disposition'])
                    self.assertEqual(result.headers['cache-control'],'no-store')
                    connection=result.json();self.assertEqual(connection['mode'],'server')
                    self.assertEqual(set(connection),{'schema','kind','mode','label','mcp_url'})
                    download=await client.get(base+'/api/operit/toolpkg')
                    self.assertEqual(download.content,(Path(__file__).resolve().parents[1]/'delivery/AI_Doll_Operit.toolpkg').read_bytes())
                    async with streamable_http_client(connection['mcp_url']) as (reader,writer,_):
                        async with ClientSession(reader,writer) as sdk:
                            await sdk.initialize();self.assertEqual(len((await sdk.list_tools()).tools),19)
                    proc=subprocess.Popen(['node',str(Path(__file__).with_name('operit_server_sdk_runner.cjs')),
                        json.dumps(connection)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
                    injected=False;deadline=time.monotonic()+22
                    try:
                        while proc.poll() is None and time.monotonic()<deadline:
                            device=app.resolve(pairing['id'])
                            if device.c.active() and not injected:
                                app.receive(pairing['device_token'],packet(1))
                                app.receive(pairing['device_token'],packet(2,phase='end'))
                                injected=True
                            await asyncio.sleep(.05)
                        stdout,stderr=await asyncio.to_thread(proc.communicate,timeout=3)
                        self.assertEqual(proc.returncode,0,stdout+stderr)
                        self.assertTrue(injected)
                    finally:
                        if proc.poll() is None:
                            proc.terminate();await asyncio.to_thread(proc.communicate,timeout=5)
                    device=app.resolve(pairing['id'])
                    self.assertIsNone(device.c.active())
                    self.assertFalse(device.c.experience.context('operit-server-chat')['events'])
                    self.assertTrue(device.c.experience.context('other-chat')['events'])
                    self.assertEqual(len(device.c.device_history()['events']),2)
                    app.mcp_info['profile']='history'
                    self.assertEqual((await client.get(base+route)).status_code,400)
                    app.mcp_info['profile']='interaction'
                    with app.lock,app.db:app.db.execute('UPDATE devices SET revoked=1')
                    self.assertEqual((await client.get(base+route)).status_code,400)
            finally:
                await asyncio.to_thread(httpd.shutdown);httpd.server_close();thread.join(5)
                server.should_exit=True;await asyncio.to_thread(worker.join,10);app.close()


if __name__=='__main__':unittest.main()
