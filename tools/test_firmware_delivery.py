"""Reject a shrinking data partition and an app that consumes the OTA reserve."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

from check_firmware import check, ROOT, APP_BYTES, MIN_FREE_BYTES


class FirmwareDeliveryTests(unittest.TestCase):
    def prepare(self, root):
        shutil.copytree(ROOT/'firmware/prebuilt', root/'firmware/prebuilt')
        (root/'firmware/src').mkdir()
        shutil.copyfile(ROOT/'firmware/src/lab_main.cpp', root/'firmware/src/lab_main.cpp')

    def update_hash(self, root, name):
        folder=root/'firmware/prebuilt'
        manifest=json.loads((folder/'FLASH_MANIFEST.json').read_text(encoding='utf-8'))
        raw=(folder/name).read_bytes()
        image=next(i for i in manifest['images'] if i['file']==name)
        image.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        (folder/'FLASH_MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')

    def test_valid_image_cannot_silently_consume_ota_reserve(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.prepare(root);check(root)
            image=root/'firmware/prebuilt/firmware.bin'
            image.write_bytes(image.read_bytes().ljust(APP_BYTES-MIN_FREE_BYTES+1,b'\xff'))
            self.update_hash(root, 'firmware.bin')
            with self.assertRaisesRegex(ValueError, 'OTA reserve'):check(root)

    def test_correct_hash_cannot_hide_reduced_archive_partition(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.prepare(root)
            table=root/'firmware/prebuilt/partitions.bin';raw=bytearray(table.read_bytes())
            for offset in range(0,len(raw),32):
                if raw[offset+12:offset+28].rstrip(b'\0')==b'spiffs':
                    struct.pack_into('<I',raw,offset+8,0x150000);break
            else:self.fail('missing archive partition')
            table.write_bytes(raw);self.update_hash(root, 'partitions.bin')
            with self.assertRaisesRegex(ValueError, 'Partition layout'):check(root)

    def test_candidate_cannot_ship_manifest_without_matching_feature_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.prepare(root)
            path=root/'firmware/prebuilt/FLASH_MANIFEST.json'
            manifest=json.loads(path.read_text(encoding='utf-8'));manifest.pop('feature_set',None)
            path.write_text(json.dumps(manifest),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Expansion source'):check(root)

    def test_network_candidate_requires_matching_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.prepare(root)
            path=root/'firmware/prebuilt/FLASH_MANIFEST.json'
            manifest=json.loads(path.read_text(encoding='utf-8'));manifest.pop('network_revision',None)
            path.write_text(json.dumps(manifest),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Network revision'):check(root)


if __name__=='__main__':unittest.main()
