"""Exercise the Windows launch script with a disconnected transport fixture."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Windows launch script')
class StartupTests(unittest.TestCase):
    def test_saved_port_is_used_and_explicit_port_can_override(self):
        with tempfile.TemporaryDirectory(prefix='AI Doll launch ') as folder:
            root = Path(folder);tools = root/'tools';tools.mkdir()
            shutil.copyfile(ROOT/'tools/start_companion.ps1',tools/'start_companion.ps1')
            executable=str(Path(sys.executable)).replace("'","''")
            (tools/'runtime_python.ps1').write_text("function Get-DollPython { param($Root) return '"+executable+"' }",encoding='utf-8-sig')
            config=root/'connection.json';config.write_text(json.dumps({'transport':'usb','serial_port':'COM88'}),encoding='utf-8')
            fixture="import sys,os,json\nfrom pathlib import Path\nsys.path.insert(0,"+repr(str(ROOT/'tools'))+")\nfrom device_transport import create_device_link\nlink,config=create_device_link(connection_path=Path(__file__).resolve().parents[1]/'connection.json')\nprint(json.dumps({'port':link.port,'transport':config['transport']}))\n"
            (tools/'device_setup_server.py').write_text(fixture,encoding='utf-8')
            def run(*arguments):
                result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(tools/'start_companion.ps1'),*arguments],cwd=root,check=True,capture_output=True,text=True,timeout=15)
                return json.loads(result.stdout.strip())
            self.assertEqual(run('-Transport','saved'),{'port':'COM88','transport':'usb'})
            self.assertEqual(run('-Transport','usb','-Port','COM99'),{'port':'COM99','transport':'usb'})


if __name__=='__main__':unittest.main()
