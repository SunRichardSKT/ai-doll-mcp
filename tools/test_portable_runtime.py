"""Offline extraction acceptance using only the Python shipped in the ZIP."""
import asyncio
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Windows portable distribution')
class PortableRuntimeTests(unittest.TestCase):
    def test_clean_package_without_system_python(self):
        package = ROOT / 'delivery/AI_Doll_Code_v2.21.0.zip'
        with tempfile.TemporaryDirectory(prefix='AI Doll 中文 ') as temp:
            root = Path(temp)
            with zipfile.ZipFile(package) as archive:
                archive.extractall(root)
            env = dict(os.environ, PATH=os.environ['SystemRoot'] + '\\System32;' +
                       os.environ['SystemRoot'] + '\\System32\\WindowsPowerShell\\v1.0')
            for name in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):
                env.pop(name, None)
            python = root / 'python/python.exe'
            result = subprocess.run([str(python), '-I', '-c',
                'import mcp,serial,httpx,sqlite3,ssl,win32api; from importlib.metadata import version; '
                'assert version("mcp")=="1.30.0"; print("OK")'], env=env,
                check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(), 'OK')
            try:
                subprocess.run(['cmd.exe', '/c', str(root / 'AI_Doll.cmd'), '-PanelPort', '8789', '-NoBrowser'],
                               env=env, cwd=root, check=True, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=20)
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                deadline = time.monotonic() + 25
                while True:
                    try:
                        with opener.open('http://127.0.0.1:8789/', timeout=2) as response:
                            html = response.read().decode('utf-8')
                        csrf = re.search(r"window.PANEL_CSRF='([0-9a-f]+)'", html)[1]
                        request = urllib.request.Request('http://127.0.0.1:8789/api/state',
                            headers={'X-CSRF-Token': csrf})
                        with opener.open(request, timeout=2) as response:
                            state = json.load(response)
                        break
                    except OSError:
                        if time.monotonic() >= deadline: raise
                        time.sleep(.3)
                self.assertTrue(state['environment_ready'])
                self.assertEqual(state['version'], '2.21.0')
                self.assertIn('operit', state)
                self.assertTrue((root/'src/ai_doll/core/interaction_bridge.py').is_file())
                self.assertTrue((root/'delivery/AI_Doll_Operit.toolpkg').is_file())
                self.assertFalse((root / '.venv').exists())
                # Configuration is created automatically on a fresh first launch.
                self.assertTrue((root/'build/device-lab/mcp-client-config.json').is_file())
                # Exercise a real worker subprocess, without pairing or hardware writes.
                worker = subprocess.run([str(python), '-X','utf8',str(root/'tools/control_panel.py'),
                    '--worker','client-config'], input='{}', env=env, cwd=root,
                    check=True, capture_output=True, text=True,encoding='utf-8')
                self.assertNotIn('error', json.loads(worker.stdout.splitlines()[-1]))
                config = json.loads((root/'build/device-lab/mcp-client-config.json').read_text())
                self.assertEqual(Path(config['mcpServers']['ai_doll']['command']), python)
                asyncio.run(self.discover(python, root, env))
                subprocess.run(['cmd.exe', '/c', str(root/'AI_Doll_Server.cmd'), '-Port','8792','-NoBrowser'],
                    env=env,cwd=root,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
                deadline=time.monotonic()+25
                while True:
                    try:
                        with opener.open('http://127.0.0.1:8792/healthz',timeout=2) as response:
                            self.assertTrue(json.load(response)['ready'])
                        break
                    except OSError:
                        if time.monotonic()>=deadline:raise
                        time.sleep(.3)
                server_root=root/'build/direct-server'
                owner=json.loads((server_root/'process-private.json').read_text())
                repeat=subprocess.run([str(python),'-X','utf8',str(root/'tools/start_direct_server.py'),
                    '--port','8792','--no-browser'],env=env,cwd=root,check=True,capture_output=True,text=True)
                self.assertTrue(json.loads(repeat.stdout)['running'])
                self.assertEqual(owner,json.loads((server_root/'process-private.json').read_text()))
                subprocess.run([str(python),'-X','utf8',str(root/'tools/start_direct_server.py'),
                    '--port','8792','--stop','--no-browser'],env=env,cwd=root,check=True,capture_output=True,timeout=10)
                report = dict(passed=True, no_system_python=True, no_venv=True,
                              root_cmd_start=True, worker=True, stdio_tools=51,
                              server_root_cmd_start=True, server_repeat_reuses_process=True,
                              automatic_client_config=True, python='3.14.8', path_with_spaces_and_chinese=True)
                folder = ROOT/'build/portable-acceptance';folder.mkdir(parents=True,exist_ok=True)
                (folder/'package.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            finally:
                # Match this test's exact executable path; never stop another install.
                command = '''param($exe)
Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -eq $exe} | ForEach-Object {Stop-Process -Id $_.ProcessId -Force}
'''
                stop = root/'stop-test.ps1';stop.write_text(command,encoding='utf-8-sig')
                subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                    str(stop), str(root/'python/pythonw.exe')], env=env, capture_output=True, timeout=15)
                subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                    str(stop), str(root/'python/python.exe')], env=env, capture_output=True, timeout=15)
                time.sleep(.5)

    async def discover(self, python, root, env):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        parameters = StdioServerParameters(command=str(python), args=[str(root/'tools/companion_mcp.py')], env=env)
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                self.assertEqual(len(tools.tools), 51)


if __name__ == '__main__':
    unittest.main()
