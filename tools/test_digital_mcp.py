import pathlib
import site
import sys
import unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];SDK=ROOT/'.tools/mcp-test-sdk'
if SDK.exists():sys.path.insert(0,str(SDK));site.addsitedir(str(SDK))
import companion_mcp


class DigitalMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_scan_schema_rejects_uninstalled_protocol_and_wrong_pin(self):
        with patch.object(companion_mcp,'call') as forwarded:
            for args in ({'driver':'dht22'}, {'gpio':8}, {'gpio':'1'}, {'gpio':True}):
                with self.subTest(args=args),self.assertRaises(Exception):
                    await companion_mcp.mcp.call_tool('scan_input_devices',args)
            forwarded.assert_not_called()

    async def test_scan_defaults_are_read_only_and_do_not_assign_channels(self):
        with patch.object(companion_mcp,'call',return_value={'devices':[]}) as forwarded:
            await companion_mcp.mcp.call_tool('scan_input_devices',{})
            forwarded.assert_called_once_with('scan_input_devices',{'driver':'ds18b20','gpio':1})
        tools=await companion_mcp.mcp.list_tools()
        tool=next(t for t in tools if t.name=='scan_input_devices')
        self.assertTrue(tool.annotations.readOnlyHint)
        self.assertFalse(tool.annotations.destructiveHint)

    async def test_rom_binding_survives_adapter_and_bad_representation_is_rejected(self):
        channel=dict(channel=8,name='腹部温度',type='temperature',driver='ds18b20',gpio=1,rom='280102030405069e',options={})
        with patch.object(companion_mcp,'call',return_value={}) as forwarded:
            await companion_mcp.mcp.call_tool('set_channel_config',{'channels':[channel]})
            payload=forwarded.call_args.args[1]['channels'][0]
            self.assertEqual(payload['rom'],channel['rom'])
            self.assertEqual(payload['gpio'],1)
        with patch.object(companion_mcp,'call') as forwarded:
            for rom in ('not-a-rom',123, '00'*9):
                with self.subTest(rom=rom),self.assertRaises(Exception):
                    await companion_mcp.mcp.call_tool('set_channel_config',{'channels':[dict(channel,rom=rom)]})
            forwarded.assert_not_called()


if __name__=='__main__':unittest.main()
