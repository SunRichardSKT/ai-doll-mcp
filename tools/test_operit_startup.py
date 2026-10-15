"""Run the delivered launcher in Windows PowerShell 5.1, including Unicode paths."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name=='nt','Windows PowerShell launcher')
class OperitStartupTests(unittest.TestCase):
    def test_both_modes_start_python_in_windows_powershell(self):
        with tempfile.TemporaryDirectory(prefix='Operit 启动 空格 ') as directory:
            root=Path(directory);tools=root/'tools';tools.mkdir()
            shutil.copyfile(ROOT/'tools/start_operit_prototype.ps1',tools/'start_operit_prototype.ps1')
            executable=str(Path(sys.executable)).replace("'","''")
            (tools/'runtime_python.ps1').write_text(
                "function Get-DollPython { param($Root) return '"+executable+"' }",encoding='utf-8-sig')
            fixture="import json,sys\nfrom pathlib import Path\nprint('OPERIT_FIXTURE:'+json.dumps({'script':Path(__file__).name,'args':sys.argv[1:]}))\n"
            for filename in ('operit_demo.py','remote_mcp.py'):
                (tools/filename).write_text(fixture,encoding='utf-8')
            for demo in (False,True):
                arguments=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                           str(tools/'start_operit_prototype.ps1'),'-ListenHost','192.168.1.23','-Port','18775']
                if demo:arguments.append('-Demo')
                process=subprocess.run(arguments,cwd=root,capture_output=True,timeout=20)
                output=process.stdout.decode('utf-8',errors='replace')
                self.assertEqual(process.returncode,0,output+process.stderr.decode('utf-8',errors='replace'))
                line=next(line for line in output.splitlines() if line.startswith('OPERIT_FIXTURE:'))
                value=json.loads(line.split(':',1)[1])
                self.assertEqual(value['script'],'operit_demo.py' if demo else 'remote_mcp.py')
                self.assertEqual(value['args'][:4],['--listen-host','192.168.1.23','--port','18775'])
                if not demo:
                    self.assertIn('--print-address',value['args'])
                    self.assertIn('interaction',value['args'])
                    self.assertIn(str(root/'build/device-lab/operit-mcp'),value['args'])


if __name__=='__main__':unittest.main()
