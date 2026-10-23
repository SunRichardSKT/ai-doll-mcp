"""Compile the production flash catalog and validate the wire result with MCP SDK."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from mcp.types import ListToolsResult
from embed_channel_editor import build_tool_catalog

ROOT=Path(__file__).resolve().parents[1]


class FirmwareToolTests(unittest.TestCase):
    def test_actual_json_serializer_preserves_all_tools_and_schemas(self):
        headers=ROOT/'firmware/.pio/libdeps/supermini-lab/ArduinoJson/src'
        if not (headers/'ArduinoJson.h').is_file():
            self.fail('Build the pinned firmware once before the native tool-catalog test')
        expected=json.loads((ROOT/'firmware/src/device_tools.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(prefix='aidoll-catalog-') as temporary:
            work=Path(temporary);(work/'firmware/src').mkdir(parents=True)
            for name in ('device_tools.json','channel_rpc.h'):
                shutil.copyfile(ROOT/'firmware/src'/name,work/'firmware/src'/name)
            build_tool_catalog(work)
            program=work/'catalog.cpp'
            program.write_text('#include <ArduinoJson.h>\n#include <iostream>\n#define PROGMEM\n#include "channel_rpc.h"\nint main(){JsonDocument out;listDeviceTools(out);serializeJson(out,std::cout);}\n',encoding='utf-8')
            command=['g++','-std=c++11','-I',str(headers),'-I',str(work/'firmware/src'),str(program),'-o',str(work/'catalog.exe')]
            subprocess.run(command,check=True,capture_output=True,timeout=40)
            actual=json.loads(subprocess.check_output([str(work/'catalog.exe')],timeout=10))['result']['tools']
        self.assertEqual(actual,expected)
        self.assertEqual(len(ListToolsResult.model_validate({'tools':actual}).tools),30)


if __name__=='__main__':unittest.main()
