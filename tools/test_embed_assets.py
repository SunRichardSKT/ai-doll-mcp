"""Generated C bytes must decompress exactly to the scripts edited and tested."""
import gzip
from pathlib import Path
import re
import tempfile
import unittest

from embed_channel_editor import build_assets

ROOT=Path(__file__).resolve().parents[1]


class EmbeddedAssetTests(unittest.TestCase):
    def test_compiled_gzip_assets_match_source_bytes_and_rebuild_stably(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'tools').mkdir()
            (root/'firmware/src').mkdir(parents=True)
            (root/'clients/operit/vendor').mkdir(parents=True)
            (root/'clients/operit/vendor/qrcodegen.js').write_bytes((ROOT/'clients/operit/vendor/qrcodegen.js').read_bytes())
            (root/'tools/pairing_connection.js').write_bytes((ROOT/'tools/pairing_connection.js').read_bytes())
            for name in ('channel_editor','ota_manager'):
                (root/'tools'/f'{name}.js').write_bytes((ROOT/'tools'/f'{name}.js').read_bytes())
            (root/'firmware/src/device_page.h').write_bytes((ROOT/'firmware/src/device_page.h').read_bytes())
            build_assets(root)
            for name in ('channel_editor','ota_manager','device_page','pairing'):
                header=root/'firmware/src'/f'{name}_asset.h'
                first=header.read_bytes()
                compressed=bytes(int(value,16) for value in re.findall(rb'0x([0-9a-f]{2})',first))
                source=((root/'firmware/src/device_page.h').read_bytes().split(b'R"HTML(',1)[1].split(b')HTML"',1)[0]
                        if name=='device_page' else
                        (root/'clients/operit/vendor/qrcodegen.js').read_bytes()+b'\n'+(root/'tools/pairing_connection.js').read_bytes()
                        if name=='pairing' else (root/'tools'/f'{name}.js').read_bytes())
                self.assertEqual(gzip.decompress(compressed),source)
                self.assertEqual(compressed[4:8],b'\x00'*4)  # No build-time timestamp.
                self.assertIn(b'unsigned char',first)
                build_assets(root)
                self.assertEqual(header.read_bytes(),first)


if __name__=='__main__':unittest.main()
