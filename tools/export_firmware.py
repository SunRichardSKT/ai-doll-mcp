"""Publish the exact PlatformIO build to the verified prebuilt image set."""
import hashlib
import json
from pathlib import Path
import re
import shutil
from flash_esp32 import ROOT, validate_images


def main():
    built=ROOT/'firmware/.pio/build/supermini-lab'
    out=ROOT/'firmware/prebuilt'
    source=(ROOT/'firmware/src/lab_main.cpp').read_text(encoding='utf-8')
    version=re.search(r'VERSION="([^"]+)"',source)[1]
    manifest=json.loads((out/'FLASH_MANIFEST.json').read_text(encoding='utf-8'))
    for name in ('bootloader.bin','partitions.bin','firmware.bin'):
        shutil.copyfile(built/name,out/name)
    if version.encode() not in (out/'firmware.bin').read_bytes():
        raise ValueError('Build does not contain the source firmware version; rebuild first')
    manifest['firmware']=version
    for item in manifest['images']:
        data=(out/item['file']).read_bytes()
        item.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    (out/'FLASH_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    validate_images(out)
    print('Exported and verified four images:',version)


if __name__=='__main__':main()
