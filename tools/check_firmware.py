"""Check manifest, source version and the unchanged 4MB layout before delivery."""
import json
from pathlib import Path
import re
import struct

from flash_esp32 import validate_images

ROOT = Path(__file__).resolve().parents[1]
APP_BYTES = 0x140000
MIN_FREE_BYTES = 8192


def check(root=ROOT):
    folder = root/'firmware/prebuilt'
    manifest, _ = validate_images(folder)
    source = (root/'firmware/src/lab_main.cpp').read_text(encoding='utf-8')
    version = re.search(r'VERSION="([^"]+)"', source)[1]
    image = (folder/'firmware.bin').read_bytes()
    if manifest['firmware'] != version or version.encode() not in image:
        raise ValueError('Source, image and manifest versions differ; rebuild and export first')
    entries = {}
    table = (folder/'partitions.bin').read_bytes()
    for offset in range(0, len(table), 32):
        if table[offset:offset+2] != b'\xaa\x50':
            continue
        _, kind, subtype, start, size, label, _ = struct.unpack('<HBBII16sI', table[offset:offset+32])
        entries[label.rstrip(b'\0').decode('ascii')] = (kind, subtype, start, size)
    expected = {'nvs':(1, 2, 0x9000, 0x5000), 'otadata':(1, 0, 0xe000, 0x2000),
                'app0':(0, 0x10, 0x10000, APP_BYTES), 'app1':(0, 0x11, 0x150000, APP_BYTES),
                'spiffs':(1, 0x82, 0x290000, 0x160000), 'coredump':(1, 3, 0x3f0000, 0x10000)}
    if entries != expected:
        raise ValueError('Partition layout changed; do not shrink archive storage or OTA slots')
    free = APP_BYTES-len(image)
    if free < MIN_FREE_BYTES:
        raise ValueError(f'OTA reserve below {MIN_FREE_BYTES} bytes: {free}')
    return dict(firmware=version, app_bytes=len(image), slot_bytes=APP_BYTES, free_bytes=free,
                warning='OTA headroom below 32 KiB' if free < 32768 else None, passed=True)


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
