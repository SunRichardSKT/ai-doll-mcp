import unittest
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


if __name__=='__main__':unittest.main()
