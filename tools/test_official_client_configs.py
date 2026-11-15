import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import install_companion_mcp as installer
from install_companion_mcp import client_config


class OfficialClientConfigs(unittest.TestCase):
    def test_native_shapes_and_arguments(self):
        server=dict(command='C:/My Doll/python/python.exe',args=['C:/My Doll/tools/companion_mcp.py'])
        for client in ('gemini','claude','local'):
            self.assertEqual(client_config(client,server)['mcpServers']['ai_doll'],server)
        dsh=client_config('deepseek',server)[0]
        self.assertEqual(dsh['name'],'@deepseek-ai/dsh-mcp-client')
        self.assertEqual(dsh['config'],dict(serverName='ai_doll',transport='stdio',**server))
        with self.assertRaises(ValueError):client_config('unknown',server)

    def test_claude_code_export_keeps_absolute_paths_and_other_client_formats(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'娃娃 core';root.mkdir()
            with patch.object(installer,'ROOT',root),patch('sys.argv',['install_companion_mcp.py','--client','claude_code']),contextlib.redirect_stdout(io.StringIO()):
                installer.main()
            work=root/'build/device-lab'
            exported=json.loads((work/'AI_Doll_Claude_Code.json').read_text(encoding='utf-8'))
            self.assertEqual(exported,json.loads((work/'mcp-client-config.json').read_text(encoding='utf-8')))
            entry=exported['mcpServers']['ai_doll']
            self.assertEqual(entry['type'],'stdio')
            self.assertTrue(Path(entry['command']).is_absolute())
            self.assertEqual(entry['args'],[str(root/'tools/companion_mcp.py')])
            self.assertFalse((root/'.mcp.json').exists())
            self.assertEqual(client_config('claude',{'command':'python','args':[]}),{'mcpServers':{'ai_doll':{'command':'python','args':[]}}})


if __name__=='__main__':unittest.main()
